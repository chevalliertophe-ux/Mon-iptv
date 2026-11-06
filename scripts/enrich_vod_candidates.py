import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sources/vod_candidates.json"
BACKUP = ROOT / "backups"
BACKUP.mkdir(exist_ok=True)

data = json.loads(SOURCE.read_text(encoding="utf-8"))
items = data.get("items", [])

def get_metadata(identifier):
    url = "https://archive.org/metadata/" + urllib.parse.quote(identifier)
    req = urllib.request.Request(
        url, headers={"User-Agent": "MON-IPTV-catalogue/1.0"}
    )
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response)

def choose_video(files):
    candidates = []
    for f in files:
        name = f.get("name", "")
        fmt = str(f.get("format", "")).lower()
        if not name.lower().endswith(".mp4"):
            continue
        if f.get("private") == "true":
            continue
        if f.get("source") == "metadata":
            continue
        score = 0
        if "mpeg4" in fmt or "h.264" in fmt:
            score += 10
        if "512kb" in name.lower():
            score -= 5
        if "sample" in name.lower() or "trailer" in name.lower():
            score -= 20
        candidates.append((score, name))
    candidates.sort(reverse=True)
    return candidates[0][1] if candidates else None

updated = 0
failed = 0
found = 0

for index, item in enumerate(items, 1):
    identifier = item.get("identifier")
    if not identifier:
        continue

    # On conserve les URL déjà trouvées.
    if item.get("playback_url") and item.get("metadata_checked"):
        found += 1
        continue

    try:
        meta = get_metadata(identifier)
        metadata = meta.get("metadata", {})
        files = meta.get("files", [])

        filename = choose_video(files)
        license_url = (
            metadata.get("licenseurl")
            or metadata.get("license")
            or item.get("license_declared")
        )

        item["metadata_license"] = license_url
        item["metadata_checked"] = True
        item["metadata_checked_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        if filename:
            item["playback_url"] = (
                "https://archive.org/download/"
                + urllib.parse.quote(identifier, safe="")
                + "/"
                + urllib.parse.quote(filename, safe="/")
            )
            item["playback_filename"] = filename
            item["playback_status"] = "DIRECT_FILE_FOUND"
            found += 1
        else:
            item["playback_status"] = "NO_MP4_FOUND"

        # Une URL trouvée ne valide jamais les droits.
        item["review_status"] = "rights_and_playback_review_required"
        updated += 1

        print(
            f"[{index}/{len(items)}] {identifier} : "
            f"{item['playback_status']}"
        )

    except Exception as error:
        failed += 1
        item["metadata_error"] = str(error)[:250]
        print(f"[{index}/{len(items)}] ERREUR {identifier}: {error}")

    if index < len(items):
        time.sleep(1)

data["updated_at"] = datetime.now(timezone.utc).isoformat()
data["total_candidates"] = len(items)
data["metadata_enriched"] = updated
data["metadata_errors"] = failed
data["direct_files_found"] = found

SOURCE.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)

print("\n========== BILAN ENRICHISSEMENT VOD ==========")
print("Candidats :", len(items))
print("Métadonnées traitées :", updated)
print("Fichiers MP4 trouvés :", found)
print("Erreurs :", failed)
print("Droits toujours à vérifier.")
print("Fichier :", SOURCE)
