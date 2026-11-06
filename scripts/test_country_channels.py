import json
import re
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

COUNTRIES = {
    "ITALIE": "it",
    "SUISSE": "ch",
    "ESPAGNE": "es",
}

MAX_TESTS = 20
TIMEOUT = 18

EXCLUDED = re.compile(
    r"canal\+|bein.?sport|sky.?sport|dazn|ocs|"
    r"eurosport|tnt.?sports|hbo|adult|xxx",
    re.I
)

def download(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "MON-IPTV-Candidate-Tester/1.0"}
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")

def parse_m3u(content):
    entries = []
    name = None
    info = ""

    for line in content.splitlines():
        line = line.strip()

        if line.startswith("#EXTINF"):
            info = line
            name = line.split(",")[-1].strip()

        elif line.startswith("http") and name:
            if EXCLUDED.search(name):
                name = None
                continue

            if re.search(r"geo.?blocked|not 24.?7", info, re.I):
                name = None
                continue

            if line.lower().startswith("https://"):
                entries.append({
                    "name": name,
                    "url": line,
                    "source_info": info
                })

            name = None

    return entries

def test_stream(url):
    command = [
        "ffprobe", "-v", "error",
        "-rw_timeout", "10000000",
        "-read_intervals", "%+8",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        url
    ]

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=TIMEOUT
        )
        streams = result.stdout.lower()
        if result.returncode == 0 and "video" in streams:
            return "VIDEO_OK"
        return "ECHEC"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as error:
        return "ERREUR: " + str(error)

report = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "source": "iptv-org public country playlists",
    "rights_status": "NOT_VERIFIED",
    "countries": {}
}

for country, code in COUNTRIES.items():
    print(f"\n===== {country} =====")

    url = f"https://iptv-org.github.io/iptv/countries/{code}.m3u"

    try:
        candidates = parse_m3u(download(url))
    except Exception as error:
        print("Téléchargement impossible :", error)
        report["countries"][country] = {"error": str(error)}
        continue

    print("Candidats trouvés :", len(candidates))
    tested = []

    for item in candidates[:MAX_TESTS]:
        print("Test :", item["name"], flush=True)
        status = test_stream(item["url"])

        tested.append({
            **item,
            "technical_status": status,
            "rights_status": "NOT_VERIFIED"
        })

        print("  ->", status, flush=True)

    report["countries"][country] = {
        "candidates_found": len(candidates),
        "tested": len(tested),
        "video_ok": sum(
            x["technical_status"] == "VIDEO_OK" for x in tested
        ),
        "results": tested
    }

Path("sources").mkdir(exist_ok=True)
output = Path("sources/tv_country_test_report.json")
output.write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("\n================================")
print("TEST TERMINÉ")
for country, data in report["countries"].items():
    if "error" not in data:
        print(
            country,
            "| testés :", data["tested"],
            "| vidéo OK :", data["video_ok"]
        )
print("Rapport :", output)
print("Aucune playlist publique modifiée.")
