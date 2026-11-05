import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

root = Path(__file__).resolve().parents[1]
data = json.loads((root / "sources/candidates.json").read_text(encoding="utf-8"))
items = data["channels"]

def check(item):
    url = item["url"].split("|", 1)[0]
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return item, response.status, response.headers.get("Content-Type", "")
    except Exception as e:
        return item, 0, str(e)[:180]

results = []
with ThreadPoolExecutor(max_workers=12) as pool:
    futures = [pool.submit(check, item) for item in items]
    for future in as_completed(futures):
        results.append(future.result())

report = []
for item, status, detail in results:
    report.append({
        **item,
        "http_status": status,
        "check_detail": detail,
        "accessible": 200 <= status < 300
    })

out = root / "sources/check_report.json"
out.write_text(json.dumps({
    "total": len(report),
    "accessible": sum(x["accessible"] for x in report),
    "failed": sum(not x["accessible"] for x in report),
    "results": report
}, ensure_ascii=False, indent=2), encoding="utf-8")

print("TOTAL :", len(report))
print("ACCESSIBLES :", sum(x["accessible"] for x in report))
print("À VÉRIFIER :", sum(not x["accessible"] for x in report))
print("RAPPORT :", out)
