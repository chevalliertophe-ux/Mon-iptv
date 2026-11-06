import json
import re
from pathlib import Path
from collections import defaultdict, Counter
from urllib.parse import urlparse

ROOT = Path(".")
DRAFT = ROOT / "public" / "bouquets-draft"
DRAFT.mkdir(parents=True, exist_ok=True)

COUNTRIES = {
    "FRANCE": "sources/tv_france_test_report.json",
    "ITALIE": "sources/tv_country_test_report.json",
    "SUISSE": "sources/tv_country_test_report.json",
    "ESPAGNE": "sources/tv_country_test_report.json",
}

CATEGORY_MAP = {
    "general": "GENERALISTES",
    "public": "GENERALISTES",
    "news": "INFORMATION",
    "information": "INFORMATION",
    "sports": "SPORT",
    "sport": "SPORT",
    "movies": "CINEMA",
    "movie": "CINEMA",
    "series": "SERIES",
    "kids": "JEUNESSE",
    "children": "JEUNESSE",
    "animation": "ANIMATION",
    "documentary": "DOCUMENTAIRES",
    "documentaries": "DOCUMENTAIRES",
    "music": "MUSIQUE",
    "lifestyle": "LIFESTYLE",
    "culture": "CULTURE",
    "comedy": "DIVERTISSEMENT",
    "entertainment": "DIVERTISSEMENT",
    "legislative": "INSTITUTIONS",
    "religious": "RELIGION",
    "cooking": "CUISINE",
    "travel": "VOYAGES",
    "weather": "METEO",
    "classic": "CULTURE",
}

def read_json(path):
    p = Path(path)
    if not p.exists():
        print("Fichier absent :", path)
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        print("Erreur JSON :", path, exc)
        return {}

def safe_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)

def normalize_group(raw):
    tags = [x.strip().lower() for x in str(raw or "").split(";") if x.strip()]
    mapped = []
    for tag in tags:
        category = CATEGORY_MAP.get(tag)
        if category and category not in mapped:
            mapped.append(category)
    return mapped[0] if mapped else "A_CLASSER"

def extract_group(item, country):
    if country == "FRANCE":
        return normalize_group(item.get("category", ""))
    info = item.get("source_info", "")
    match = re.search(r'group-title="([^"]*)"', info)
    if match:
        return normalize_group(match.group(1))
    return "A_CLASSER"

def country_results(country):
    path = COUNTRIES[country]
    data = read_json(path)
    if country == "FRANCE":
        return data.get("results", [])
    return data.get("countries", {}).get(country, {}).get("results", [])

summary = {}
all_drafts = []
seen_global = set()

for country in COUNTRIES:
    results = country_results(country)
    groups = defaultdict(list)
    seen_country = set()

    for item in results:
        if item.get("technical_status") != "VIDEO_OK":
            continue
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not safe_url(url) or url in seen_country:
            continue

        seen_country.add(url)
        group = extract_group(item, country)
        groups[group].append({
            "name": name,
            "url": url,
            "category": group,
            "country": country,
            "rights_status": item.get("rights_status", "NOT_VERIFIED"),
            "technical_status": "VIDEO_OK",
        })

    country_dir = DRAFT / country.lower()
    country_dir.mkdir(parents=True, exist_ok=True)

    country_total = 0
    for group, items in sorted(groups.items()):
        filename = group.lower() + ".m3u"
        lines = ["#EXTM3U"]
        for item in sorted(items, key=lambda x: x["name"].lower()):
            display = item["name"].replace(",", " ")
            lines.append(
                f'#EXTINF:-1 group-title="{group}",{display}'
            )
            lines.append(item["url"])
            country_total += 1
            if item["url"] not in seen_global:
                seen_global.add(item["url"])
                all_drafts.append(item)

        (country_dir / filename).write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    summary[country] = {
        "video_ok_unique": country_total,
        "categories": {k: len(v) for k, v in sorted(groups.items())},
        "rights_status": "NOT_VERIFIED",
        "publication_status": "DRAFT_ONLY",
    }

# Bouquet international de travail : dédoublonné, non publiable en l'état.
international = ["#EXTM3U"]
for item in sorted(all_drafts, key=lambda x: (x["country"], x["name"].lower())):
    international.extend([
        f'#EXTINF:-1 group-title="{item["country"]} - {item["category"]}",{item["name"].replace(",", " ")}',
        item["url"],
    ])
(DRAFT / "INTERNATIONAL_TEST.m3u").write_text(
    "\n".join(international) + "\n", encoding="utf-8"
)

# Inventaire VOD : les URLs du rapport sont conservées comme candidates,
# jamais présentées comme des liens validés pour SmartOne.
license_report = read_json("sources/vod_movies_license_report.json")
vod_candidates = read_json("sources/vod_candidates.json").get("items", [])
candidate_by_id = {x.get("identifier"): x for x in vod_candidates}

vod_review = []
license_counts = Counter()

for entry in license_report if isinstance(license_report, list) else []:
    identifier = entry.get("identifier")
    candidate = candidate_by_id.get(identifier, {})
    license_url = entry.get("licenseurl") or candidate.get("license_declared")
    license_counts[license_url or "LICENCE_NON_RENSEIGNEE"] += 1

    vod_review.append({
        "title": entry.get("title") or candidate.get("title"),
        "identifier": identifier,
        "year": entry.get("date") or candidate.get("year"),
        "source": "Internet Archive",
        "item_url": candidate.get("item_url"),
        "candidate_file_url": entry.get("url"),
        "license_url": license_url,
        "rights_description": entry.get("rights"),
        "metadata_status": entry.get("metadata_status"),
        "playback_status": "NOT_REVALIDATED",
        "review_status": "RIGHTS_AND_PLAYBACK_REVIEW_REQUIRED",
    })

(ROOT / "sources" / "vod_review_catalog.json").write_text(
    json.dumps({
        "version": 1,
        "total": len(vod_review),
        "notice": "Inventaire de contrôle. Aucun élément n'est approuvé pour publication.",
        "items": vod_review,
    }, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

report = {
    "created_from": "local test reports",
    "countries": summary,
    "international_unique_test_streams": len(all_drafts),
    "vod_review_candidates": len(vod_review),
    "vod_license_distribution": dict(license_counts),
    "rights_status": "NOT_VERIFIED",
    "publication_status": "DRAFT_ONLY",
    "series_count_in_vod_json": len(read_json("sources/vod.json").get("series", [])),
}

(ROOT / "sources" / "final_catalog_report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("\n========== MON IPTV — CONSTRUCTION ==========")
for country, data in summary.items():
    print(f"\n{country}: {data['video_ok_unique']} flux")
    for category, count in data["categories"].items():
        print(f"  {category}: {count}")

print("\nInternational dédoublonné :", len(all_drafts))
print("Candidats VOD inventoriés :", len(vod_review))
print("Séries enregistrées :", report["series_count_in_vod_json"])
print("\nRapports : sources/final_catalog_report.json")
print("VOD : sources/vod_review_catalog.json")
print("Bouquets brouillons : public/bouquets-draft/")
print("\nDROITS NON VERIFIES : aucune playlist publique modifiée.")
