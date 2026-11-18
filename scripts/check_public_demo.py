"""Execute a real saved ETL job and retain its result; no credentials required."""
import argparse
import csv
import io
import json
import time
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('base_url')
parser.add_argument('--output', default='demo-evidence')
args = parser.parse_args()
base = args.base_url.rstrip('/')
headers = {'Content-Type': 'application/json'}
def request(path, data=None, raw=False):
    req = urllib.request.Request(base+path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as response:
        content = response.read().decode()
        return content if raw else json.loads(content)

assert request('/health/ready')['status'] == 'ready'
session = request('/api/demo/session', {})
headers['Authorization'] = 'Bearer '+session['token']
schedules = request('/api/schedules')
schedule = next(s for s in schedules if s['pipeline_slug'] == 'regional_revenue' and s['status'] == 'active')
request('/api/demo/run-schedule/'+str(schedule['id']), {})
result = None
for attempt in range(20):
    logs = request(f"/api/schedules/{schedule['id']}/logs")
    if logs and logs[0]['status'] in {'success', 'failed'}:
        result = logs[0]
        break
    time.sleep(2)
assert result and result['status'] == 'success', f'ETL run failed or timed out: {result}'
content = request('/api/demo/output', raw=True)
rows = list(csv.DictReader(io.StringIO(content)))
assert len(rows) == 4 and {row['region'] for row in rows} == {'North','South','East','West'}
assert all(float(row['amount']) > 0 for row in rows)
output = Path(args.output)
output.mkdir(parents=True, exist_ok=True)
(output/'regional-revenue.csv').write_text(content)
report = {'base_url':base, 'status':result['status'], 'run_id':result['id'], 'rows_written':result['rows_written'], 'finished_at':result['finished_at'], 'regions':len(rows)}
(output/'run.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report))
