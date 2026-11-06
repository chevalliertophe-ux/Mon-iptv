import json
from pathlib import Path
from collections import Counter

root = Path(__file__).resolve().parents[1]
candidates = json.loads((root/"sources/tv_candidates.json").read_text())
report = json.loads((root/"sources/tv_playback_report.json").read_text())

tested = {x["url"]: x for x in report["results"]}
catalog = []

for item in candidates["channels"]:
    result = tested.get(item["url"])
    if not result:
        continue

    entry = dict(item)
    entry["video_detected"] = result.get("video_detected", False)
    entry["playback_detail"] = result.get("detail", "")
    entry["rights_status"] = item.get("rights_status", "not_verified")
    catalog.append(entry)

catalog.sort(key=lambda x: (
    x.get("country", "Autre").casefold(),
    x.get("group", "Autre").casefold(),
    x.get("name", "").casefold()
))

out = {
    "version": 1,
    "total": len(catalog),
    "video_detected": sum(x["video_detected"] for x in catalog),
    "notice": "Détection vidéo distincte de l'autorisation de diffusion.",
    "channels": catalog
}

path = root/"sources/tv_catalog_review.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=2))

print("CATALOGUE PREPARE :", len(catalog))
print("VIDEOS DETECTEES :", out["video_detected"])
print("\nPAR PAYS :")

for country, count in Counter(
    x["country"] for x in catalog if x["video_detected"]
).most_common():
    print(country, ":", count)

print("\nFICHIER :", path)
print("PLAYLISTS ACTUELLES : NON MODIFIEES")
