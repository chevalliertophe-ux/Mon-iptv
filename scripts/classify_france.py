import json
import re
from pathlib import Path
from collections import defaultdict

source = Path("sources/tv_france_test_report.json")
out = Path("public/bouquets-draft")
out.mkdir(parents=True, exist_ok=True)

data = json.loads(source.read_text(encoding="utf-8"))

categories = {
    "GENERALISTES": ["General", "Legislative"],
    "DIVERTISSEMENT": ["Entertainment", "Interactive"],
    "INFORMATION": ["News"],
    "CINEMA": ["Movies", "Comedy"],
    "SERIES": ["Series"],
    "SPORT": ["Sports"],
    "JEUNESSE": ["Kids", "Animation"],
    "DOCUMENTAIRES": ["Documentary"],
    "MUSIQUE": ["Music"],
    "LIFESTYLE": ["Lifestyle", "Cooking", "Travel"],
    "CULTURE": ["Culture", "Religious"],
}

manual = {
    "Generations TV": "MUSIQUE",
    "ILTV": "A_CLASSER",
    "RMC Story": "DIVERTISSEMENT",
    "ViaMatele": "GENERALISTES",
}

def classify(item):
    raw = item.get("category", "")
    tags = set(raw.split(";"))
    name = item.get("name", "")

    if "(Germany)" in name:
        return "INTERNATIONAL_TEST"

    for group, keywords in categories.items():
        if tags.intersection(keywords):
            return group

    return "A_CLASSER"

groups = defaultdict(list)

for item in data.get("results", []):
    if item.get("technical_status") != "VIDEO_OK":
        continue

    name = item.get("name", "").strip()
    url = item.get("url", "").strip()

    if not name or not url.startswith("https://"):
        continue

    name_key = item["name"].split(" (")[0]
    group = manual.get(name_key, classify(item))
    groups[group].append(item)

def write_playlist(filename, items):
    lines = ["#EXTM3U"]

    for item in sorted(items, key=lambda x: x["name"].lower()):
        name = item["name"].replace(",", " ")
        lines += [
            f'#EXTINF:-1 group-title="{filename}",{name}',
            item["url"]
        ]

    (out / filename).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

for group, items in groups.items():
    write_playlist(group + ".m3u", items)

all_items = [
    item
    for items in groups.values()
    for item in items
]
write_playlist("FRANCE_COMPLET_TEST.m3u", all_items)

report = {
    "total": len(all_items),
    "groups": {k: len(v) for k, v in groups.items()},
    "rights_status": "NOT_VERIFIED",
    "publication_status": "DRAFT_ONLY"
}

Path("sources/france_classification_report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("\n=== CLASSEMENT FRANCE ===")
for group, items in sorted(groups.items()):
    print(group, ":", len(items))

print("TOTAL :", len(all_items))
print("Dossiers :", out)
print("Aucune playlist publiée modifiée.")
