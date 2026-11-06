import json
import re
import subprocess
import urllib.request
from pathlib import Path
from collections import defaultdict, deque
from datetime import datetime, timezone

SOURCE = "https://iptv-org.github.io/iptv/countries/fr.m3u"
MAX_TESTS = 100
TIMEOUT = 12

EXCLUDED = re.compile(
    r"canal\\+|bein.?sport|sky.?sport|dazn|"
    r"adult|xxx|hbo",
    re.I
)

def download():
    req = urllib.request.Request(
        SOURCE, headers={"User-Agent": "MON-IPTV-France-Tester/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")

def parse_playlist(content):
    entries = []
    info = None

    for line in content.splitlines():
        line = line.strip()

        if line.startswith("#EXTINF"):
            info = line
            continue

        if line.startswith("http") and info:
            name = info.rsplit(",", 1)[-1].strip()
            group = re.search(r'group-title="([^"]+)"', info)
            category = group.group(1) if group else "Non classé"

            if (
                line.startswith("https://")
                and name
                and not EXCLUDED.search(name)
                and not re.search(r"geo.?blocked|not 24.?7", info, re.I)
            ):
                entries.append({
                    "name": name,
                    "category": category,
                    "url": line
                })

            info = None

    return entries

def balanced_selection(entries):
    groups = defaultdict(deque)
    order = []

    for item in entries:
        group = item["category"]
        if group not in groups:
            order.append(group)
        groups[group].append(item)

    selected = []
    while len(selected) < MAX_TESTS:
        added = False
        for group in order:
            if groups[group] and len(selected) < MAX_TESTS:
                selected.append(groups[group].popleft())
                added = True
        if not added:
            break

    return selected

def test_stream(url):
    command = [
        "ffprobe", "-v", "error",
        "-rw_timeout", "8000000",
        "-read_intervals", "%+5",
        "-show_entries", "stream=codec_type",
        "-of", "json", url
    ]

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=TIMEOUT
        )
        data = json.loads(result.stdout or "{}")
        types = [
            stream.get("codec_type")
            for stream in data.get("streams", [])
        ]

        if result.returncode == 0 and "video" in types:
            return "VIDEO_OK", types
        return "ECHEC", types

    except subprocess.TimeoutExpired:
        return "TIMEOUT", []
    except Exception:
        return "ECHEC", []

print("Téléchargement de la playlist française...")
try:
    candidates = parse_playlist(download())
except Exception as error:
    raise SystemExit(f"Erreur de téléchargement : {error}")

selected = balanced_selection(candidates)

print("Candidats français trouvés :", len(candidates))
print("Candidats sélectionnés pour test :", len(selected))

results = []

for index, item in enumerate(selected, 1):
    print(f"[{index}/{len(selected)}] {item['name']} ({item['category']})",
          flush=True)

    status, streams = test_stream(item["url"])
    results.append({
        **item,
        "technical_status": status,
        "streams": streams,
        "rights_status": "NOT_VERIFIED"
    })

    print("   ->", status, flush=True)

ok = [x for x in results if x["technical_status"] == "VIDEO_OK"]

report = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "source": SOURCE,
    "candidates_found": len(candidates),
    "tested": len(results),
    "video_ok": len(ok),
    "rights_status": "NOT_VERIFIED",
    "results": results
}

Path("sources").mkdir(exist_ok=True)
output = Path("sources/tv_france_test_report.json")
output.write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("\n========== BILAN FRANCE ==========")
print("Candidats trouvés :", len(candidates))
print("Chaînes testées :", len(results))
print("Flux vidéo fonctionnels :", len(ok))
print("Rapport :", output)
print("Aucune playlist publiée modifiée.")
