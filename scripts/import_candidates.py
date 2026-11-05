import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ROOT / "sources/imports"
OUTPUT = ROOT / "sources/candidates.json"

countries = {
    "france": "France",
    "suisse": "Suisse",
    "italie": "Italie",
    "espagne": "Espagne"
}

def attr(line, key):
    m = re.search(rf'{re.escape(key)}="([^"]*)"', line)
    return m.group(1).strip() if m else ""

items = []
seen = set()
duplicates = 0

for filename, country in countries.items():
    path = IMPORTS / f"{filename}.m3u"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    metadata = None

    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            metadata = line
        elif line and not line.startswith("#") and metadata:
            url = line
            name = metadata.split(",", 1)[-1].strip()
            if url.startswith(("http://", "https://")) and name:
                key = url.split("|", 1)[0].lower()
                if key in seen:
                    duplicates += 1
                else:
                    seen.add(key)
                    items.append({
                        "name": name,
                        "url": url,
                        "country": country,
                        "group": attr(metadata, "group-title") or country,
                        "logo": attr(metadata, "tvg-logo"),
                        "status": "candidate_to_verify"
                    })
            metadata = None

OUTPUT.write_text(
    json.dumps({"version": 1, "channels": items}, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("CANDIDATS IMPORTÉS :", len(items))
print("DOUBLONS ÉCARTÉS :", duplicates)
for country in countries.values():
    print(country + " :", sum(x["country"] == country for x in items))
print("Fichier :", OUTPUT)
