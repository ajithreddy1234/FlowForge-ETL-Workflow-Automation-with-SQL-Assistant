"""Evaluate FlowForge's SQL guardrails and NL-to-SQL assistant.

    python -m eval.run_eval guardrails                 # 47 attack statements, no LLM needed
    python -m eval.run_eval accuracy [--connection "Demo retail (PostgreSQL)"]

`accuracy` sends each of the 60 questions through the real assistant pipeline (catalog-based
schema context -> LLM -> guardrails -> EXPLAIN -> self-correction), runs the accepted SQL on the
source database, and compares the result set with hand-written gold SQL (order-insensitive,
numbers rounded to 2 dp). Results, including every failure, are saved to eval/results/.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent
logging.getLogger("sqlglot").setLevel(logging.ERROR)


def _norm(v):
    if isinstance(v, (float, Decimal)):
        return round(float(v), 2)
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    return v


def _rows(conn, sql):
    from sqlalchemy import text

    return Counter(tuple(_norm(x) for x in r) for r in conn.execute(text(sql)).fetchall())


def guardrails() -> dict:
    from api.sql_guardrails import SqlPolicyError, validate_read_only_statement

    attacks = json.loads((HERE / "adversarial.json").read_text())
    out = {}
    for dialect in ("postgresql", "mysql"):
        leaked = []
        for sql in attacks:
            try:
                validate_read_only_statement(sql, dialect)
                leaked.append(sql)
            except SqlPolicyError:
                pass
        out[dialect] = {"total": len(attacks), "blocked": len(attacks) - len(leaked), "leaked": leaked}
    return out


def accuracy(connection_name: str) -> dict:
    from sqlalchemy import create_engine

    from api.catalog_service import latest_catalog, sync_catalog
    from api.connection_profiles import profile_uri
    from api.database import ConnectionProfile, SessionLocal, User
    from api.sql_assistant_service import SqlAssistantUnavailable, generate_candidate
    from api.sql_guardrails import SqlPolicyError
    from src.config import LLM_MODEL, SQL_ASSISTANT_MAX_ATTEMPTS, SQL_ASSISTANT_PROVIDER

    questions = json.loads((HERE / "questions.json").read_text())
    with SessionLocal() as db:
        profile = db.query(ConnectionProfile).filter_by(name=connection_name).first()
        if not profile:
            raise SystemExit(f"No connection named {connection_name!r}; run scripts.bootstrap_local first")
        user = db.get(User, profile.created_by_user_id)
        snapshot = latest_catalog(db, profile.id) or sync_catalog(db, profile)
        engine = create_engine(profile_uri(profile))
        details, latencies = [], []
        for q in questions:
            with engine.connect() as conn:
                gold = _rows(conn, q["gold"])
            t0 = time.perf_counter()
            sql, status, error, drafts = None, "ok", None, None
            try:
                cand = generate_candidate(db, user, profile, snapshot, q["q"])
                sql = cand.generated_sql
                drafts = 1 if "after" not in (cand.explanation or "") else int(cand.explanation.split("after ")[1].split()[0])
                with engine.connect() as conn:
                    got = _rows(conn, sql)
                ok = got == gold
            except SqlAssistantUnavailable as e:
                raise SystemExit(f"Assistant unavailable: {e}")
            except SqlPolicyError as e:
                ok, status, error = False, "rejected", str(e)
            except Exception as e:  # noqa: BLE001
                ok, status, error = False, "error", str(e)[:300]
            latencies.append(time.perf_counter() - t0)
            details.append({"id": q["id"], "question": q["q"], "correct": ok, "status": status, "sql": sql,
                            "drafts": drafts, "error": error})
            print(f"[{'PASS' if ok else 'FAIL'}] {q['id']:>2} {q['q'][:72]}")
    n = len(details)
    correct = sum(d["correct"] for d in details)
    first = sum(d["correct"] and d["drafts"] == 1 for d in details)
    latencies.sort()
    return {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provider": SQL_ASSISTANT_PROVIDER, "model": LLM_MODEL, "max_drafts": SQL_ASSISTANT_MAX_ATTEMPTS,
        "connection": connection_name, "questions": n,
        "execution_accuracy": round(correct / n, 4), "correct": correct,
        "correct_on_first_draft": first, "recovered_by_self_correction": correct - first,
        "p50_latency_s": round(latencies[n // 2], 2), "p95_latency_s": round(latencies[int(n * 0.95) - 1], 2),
        "details": details,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("suite", choices=["guardrails", "accuracy"])
    ap.add_argument("--connection", default="Demo retail (PostgreSQL)")
    a = ap.parse_args()
    res = guardrails() if a.suite == "guardrails" else accuracy(a.connection)
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"{a.suite}.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps({k: v for k, v in res.items() if k != "details"}, indent=2, default=str))


if __name__ == "__main__":
    main()
