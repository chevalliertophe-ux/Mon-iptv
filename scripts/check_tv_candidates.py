import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sources/tv_candidates.json"
OUTPUT = ROOT / "sources/tv_check_report.json"

data = json.loads(SOURCE.read_text(encoding="utf-8"))
channels = data.get("channels", [])

def check(item):
    url = item.get("url", "").split("|", 1)[0].strip()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "MON-IPTV/1.0"},
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            return item, status, content_type
    except Exception as error:
        return item, 0, str(error)[:180]

results = []

with ThreadPoolExecutor(max_workers=10) as pool:
    futures = [pool.submit(check, item) for item in channels]
    for future in as_completed(futures):
        results.append(future.result())

report = []

for item, status, detail in results:
    report.append({
        "name": item.get("name"),
        "url": item.get("url"),
        "country": item.get("country"),
        "http_status": status,
        "detail": detail,
        "accessible": 200 <= status < 300,
        "playback_verified": False,
        "rights_verified": False
    })

accessible = sum(x["accessible"] for x in report)

OUTPUT.write_text(
    json.dumps({
        "total": len(report),
        "accessible": accessible,
        "failed": len(report) - accessible,
        "notice": "HTTP accessible ne signifie ni lecture vérifiée ni droits autorisés.",
        "results": report
    }, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)

print("TOTAL :", len(report))
print("HTTP ACCESSIBLES :", accessible)
print("ERREURS :", len(report) - accessible)
print("LECTURE TV : non vérifiée")
print("DROITS : non vérifiés")
print("RAPPORT :", OUTPUT)
