"""Evaluate FlowForge's SQL guardrails and NL-to-SQL assistant.

    python -m eval.run_eval guardrails   # 40 write/DDL + 26 side-effect attacks x 3 dialects, no LLM/DB
    python -m eval.run_eval readonly     # live: the same 40 write/DDL sent to the read-only DB role
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


DIALECTS = ("postgresql", "mysql", "redshift")
APPROVED = {("public", t) for t in ("customers", "orders", "order_items", "products")}


def guardrails() -> dict:
    """Layer 1: every attack must be rejected by the SQLGlot AST policy, for both entry points
    (manual Extract SQL and assistant-generated SQL) in every source dialect. The 60 gold
    analytics queries are also checked so the policy is not just rejecting everything."""
    from api.sql_guardrails import SqlPolicyError, validate_read_only_sql, validate_read_only_statement

    suites = json.loads((HERE / "adversarial.json").read_text())
    gold = [q["gold"] for q in json.loads((HERE / "questions.json").read_text())]
    checks = {
        "manual_extract": lambda sql, d: validate_read_only_statement(sql, d),
        "assistant": lambda sql, d: validate_read_only_sql(sql, d, APPROVED),
    }
    out: dict = {"categories": {}, "false_positives": {}}
    for category, attacks in suites.items():
        out["categories"][category] = {}
        for dialect in DIALECTS:
            leaked = []
            for name, check in checks.items():
                for sql in attacks:
                    try:
                        check(sql, dialect)
                        leaked.append({"entry_point": name, "sql": sql})
                    except SqlPolicyError:
                        pass
            out["categories"][category][dialect] = {
                "queries": len(attacks), "blocked": len(attacks) - len({x["sql"] for x in leaked}),
                "leaked": leaked,
            }
    for dialect in DIALECTS:
        rejected = []
        for sql in gold:
            try:
                validate_read_only_sql(sql, dialect, APPROVED)
            except SqlPolicyError as exc:
                rejected.append({"sql": sql, "error": str(exc)})
        out["false_positives"][dialect] = {"safe_queries": len(gold), "wrongly_rejected": rejected}
    return out


def readonly(connection_name: str) -> dict:
    """Layer 2: send every write/DDL attack straight to the source database through the
    connection's read-only role, bypassing the AST policy, and check the database refuses it.
    Each statement runs in its own transaction that is always rolled back."""
    from sqlalchemy import create_engine, text

    from api.connection_profiles import profile_uri
    from api.database import ConnectionProfile, SessionLocal

    attacks = json.loads((HERE / "adversarial.json").read_text())["write_ddl"]
    with SessionLocal() as db:
        profile = db.query(ConnectionProfile).filter_by(name=connection_name).first()
        if not profile:
            raise SystemExit(f"No connection named {connection_name!r}; run scripts.bootstrap_local first")
        engine = create_engine(profile_uri(profile))
    executed = []
    for sql in attacks:
        conn = engine.connect()
        trans = conn.begin()
        try:
            conn.execute(text(sql))
            executed.append(sql)
        except Exception:  # noqa: BLE001 - any refusal (permission, read-only txn, syntax) counts
            pass
        finally:
            trans.rollback()
            conn.close()
    engine.dispose()
    print(f"read-only role refused {len(attacks) - len(executed)}/{len(attacks)} write/DDL statements")
    return {"connection": connection_name, "dialect": profile.db_type, "queries": len(attacks),
            "refused_by_database": len(attacks) - len(executed), "executed": executed}


def accuracy(connection_name: str, limit: int | None = None) -> dict:
    """Progress is saved after every question, so a run stopped by a free-tier daily limit
    resumes where it left off when the same command is run again."""
    from sqlalchemy import create_engine

    from api.catalog_service import latest_catalog, sync_catalog
    from api.connection_profiles import profile_uri
    from api.database import ConnectionProfile, SessionLocal, User
    from api.sql_assistant_service import SqlAssistantUnavailable, generate_candidate
    from api.sql_guardrails import SqlPolicyError
    from src.config import LLM_MODEL, SQL_ASSISTANT_MAX_ATTEMPTS, SQL_ASSISTANT_PROVIDER

    questions = json.loads((HERE / "questions.json").read_text())[:limit]
    progress_file = HERE / "results" / f".progress-{_slug(connection_name)}-{_slug(LLM_MODEL)}-{len(questions)}.json"
    progress_file.parent.mkdir(exist_ok=True)
    details = json.loads(progress_file.read_text()) if progress_file.exists() else []
    done = {d["id"] for d in details}
    if done:
        print(f"resuming: {len(done)}/{len(questions)} questions already answered with {LLM_MODEL}")
    with SessionLocal() as db:
        profile = db.query(ConnectionProfile).filter_by(name=connection_name).first()
        if not profile:
            raise SystemExit(f"No connection named {connection_name!r}; run scripts.bootstrap_local first")
        user = db.get(User, profile.created_by_user_id)
        snapshot = latest_catalog(db, profile.id) or sync_catalog(db, profile)
        engine = create_engine(profile_uri(profile))
        for q in questions:
            if q["id"] in done:
                continue
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
                progress_file.write_text(json.dumps(details, indent=2, default=str))
                raise SystemExit(f"Stopped after {len(details)}/{len(questions)} questions: {e}\n"
                                 "Progress is saved; run the same command again (e.g. after the daily limit resets "
                                 "at 00:00 UTC) to continue.")
            except SqlPolicyError as e:
                ok, status, error = False, "rejected", str(e)
            except Exception as e:  # noqa: BLE001
                ok, status, error = False, "error", str(e)[:300]
            details.append({"id": q["id"], "question": q["q"], "correct": ok, "status": status, "sql": sql,
                            "drafts": drafts, "error": error, "latency_s": round(time.perf_counter() - t0, 2)})
            progress_file.write_text(json.dumps(details, indent=2, default=str))
            print(f"[{'PASS' if ok else 'FAIL'}] {q['id']:>2} {q['q'][:72]}", flush=True)
    progress_file.unlink(missing_ok=True)
    details.sort(key=lambda d: d["id"])
    latencies = [d["latency_s"] for d in details]
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
        "p50_latency_s": round(latencies[n // 2], 2), "p95_latency_s": round(latencies[max(int(n * 0.95) - 1, 0)], 2),
        "details": details,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("suite", choices=["guardrails", "readonly", "accuracy"])
    ap.add_argument("--connection", default="Demo retail (PostgreSQL)")
    ap.add_argument("--limit", type=int, help="accuracy: only the first N questions (a quick model comparison)")
    a = ap.parse_args()
    res = {"guardrails": guardrails, "readonly": lambda: readonly(a.connection),
           "accuracy": lambda: accuracy(a.connection, a.limit)}[a.suite]()
    (HERE / "results").mkdir(exist_ok=True)
    name = a.suite if a.suite == "guardrails" else f"{a.suite}-{_slug(a.connection)}"
    if a.suite == "accuracy":
        name += f"-{_slug(res['model'])}" + (f"-first{a.limit}" if a.limit else "")
    (HERE / "results" / f"{name}.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(_summary(res), indent=2, default=str))


def _slug(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _summary(res: dict) -> dict:
    if "categories" in res:
        return {
            "blocked": {c: {d: f"{r['blocked']}/{r['queries']}" for d, r in by_d.items()}
                        for c, by_d in res["categories"].items()},
            "false_positives": {d: len(r["wrongly_rejected"]) for d, r in res["false_positives"].items()},
        }
    return {k: v for k, v in res.items() if k != "details"}


if __name__ == "__main__":
    main()
