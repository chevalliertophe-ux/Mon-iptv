import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sources/vod_candidates.json"

LICENSE = "https://creativecommons.org/publicdomain/mark/1.0/"

COLLECTIONS = [
    ("feature_films", "Films"),
    ("opensource_movies", "Films indépendants"),
    ("documentaryfilms", "Documentaires"),
    ("animationandcartoons", "Dessins animés")
]

def search(collection):
    query = (
        f'mediatype:movies AND collection:{collection} '
        f'AND licenseurl:"{LICENSE}"'
    )

    params = [
        ("q", query),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "year"),
        ("fl[]", "licenseurl"),
        ("fl[]", "publicdate"),
        ("rows", "100"),
        ("sort[]", "publicdate desc"),
        ("output", "json")
    ]

    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"User-Agent": "MON-IPTV-catalogue/1.0"}
    )

    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)["response"]["docs"]

def main():
    existing = {}

    if OUT.exists():
        old = json.loads(OUT.read_text(encoding="utf-8"))
        existing = {
            x["identifier"]: x
            for x in old.get("items", [])
            if x.get("identifier")
        }

    discovered = 0

    for collection, category in COLLECTIONS:
        try:
            docs = search(collection)
            print(category, ":", len(docs), "résultats")

            for doc in docs:
                identifier = str(doc.get("identifier", "")).strip()
                title = str(doc.get("title", "")).strip()

                if not identifier or not title:
                    continue
                if doc.get("licenseurl") != LICENSE:
                    continue

                existing[identifier] = {
                    "identifier": identifier,
                    "title": title,
                    "year": doc.get("year"),
                    "publicdate": doc.get("publicdate"),
                    "category": category,
                    "license_declared": LICENSE,
                    "source": "Internet Archive",
                    "review_status": "rights_and_playback_review_required",
                    "metadata_url": f"https://archive.org/metadata/{identifier}",
                    "item_url": f"https://archive.org/details/{identifier}",
                    "playback_url": None
                }
                discovered += 1

        except Exception as error:
            print("ERREUR", category, str(error))

    result = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_candidates": len(existing),
        "new_or_refreshed": discovered,
        "items": list(existing.values()),
        "notice": "Candidats uniquement : aucune licence ni lecture n'est certifiée."
    }

    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print("TOTAL CANDIDATS :", len(existing))
    print("FICHIER :", OUT)

if __name__ == "__main__":
    main()
