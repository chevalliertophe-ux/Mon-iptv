import json
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

source = Path("sources/vod_movies_playable_candidates.json")
output = Path("sources/vod_movies_license_report.json")

films = json.loads(source.read_text(encoding="utf-8"))
results = []

for i, film in enumerate(films, 1):
    parts = urlparse(film["url"]).path.split("/")
    identifier = parts[2] if len(parts) > 2 else ""

    result = {
        "title": film["title"],
        "url": film["url"],
        "identifier": identifier,
        "licenseurl": None,
        "rights": None,
        "creator": None,
        "date": None,
        "metadata_status": "unknown",
    }

    try:
        api = f"https://archive.org/metadata/{identifier}"
        req = urllib.request.Request(
            api,
            headers={"User-Agent": "MON-IPTV-Catalogue/1.0"}
        )

        with urllib.request.urlopen(req, timeout=25) as response:
            metadata = json.loads(response.read())

        meta = metadata.get("metadata", {})
        result.update({
            "licenseurl": meta.get("licenseurl"),
            "rights": meta.get("rights"),
            "creator": meta.get("creator"),
            "date": meta.get("date"),
            "metadata_status": "retrieved",
        })

    except Exception as exc:
        result["metadata_status"] = "error"
        result["error"] = str(exc)

    results.append(result)

    output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"[{i}/{len(films)}] {film['title']} => {result['metadata_status']}")
    time.sleep(2)

print("\nTERMINÉ :", len(results))
print("Rapport :", output)
