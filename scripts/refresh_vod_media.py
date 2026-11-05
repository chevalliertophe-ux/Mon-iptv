import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "sources/vod_candidates.json"
REPORT = ROOT / "sources/vod_enrichment_report.json"

DECLARED_PD_CC0 = {
    "http://creativecommons.org/publicdomain/mark/1.0/",
    "https://creativecommons.org/publicdomain/mark/1.0/",
    "http://creativecommons.org/publicdomain/zero/1.0/",
    "https://creativecommons.org/publicdomain/zero/1.0/",
}

def fetch_json(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "MON-IPTV-VOD-Catalogue/1.0"}
    )
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.load(response)

def choose_video(files):
    candidates = []
    for f in files or []:
        name = str(f.get("name", ""))
        low = name.lower()
        if not low.endswith(".mp4"):
            continue
        if any(x in low for x in ("sample", "trailer", "preview", "thumbnail")):
            continue
        try:
            size = int(f.get("size", 0))
        except (TypeError, ValueError):
            size = 0
        if size >= 20_000_000:
            candidates.append((size, name))
    return max(candidates)[1] if candidates else None

def main():
    if not INPUT.exists():
        raise SystemExit("sources/vod_candidates.json introuvable")
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    items = data.get("items", [])
    report = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(items), "metadata_ok": 0, "direct_mp4_found": 0,
        "declared_pd_or_cc0": 0, "errors": 0
    }

    for item in items:
        identifier = str(item.get("identifier", "")).strip()
        if not identifier:
            continue
        try:
            metadata = fetch_json(
                "https://archive.org/metadata/" + quote(identifier, safe="")
            )
            meta = metadata.get("metadata", {})
            license_url = str(meta.get("licenseurl") or item.get("license_declared") or "")
            filename = choose_video(metadata.get("files", []))

            item["metadata_license"] = license_url or None
            item["metadata_rights"] = meta.get("rights")
            item["metadata_url"] = f"https://archive.org/metadata/{identifier}"
            item["item_url"] = f"https://archive.org/details/{identifier}"
            item["last_metadata_check"] = datetime.now(timezone.utc).isoformat()
            report["metadata_ok"] += 1

            if filename:
                item["playback_url"] = (
                    "https://archive.org/download/" + quote(identifier, safe="")
                    + "/" + quote(filename, safe="/")
                )
                item["playback_format"] = "mp4"
                report["direct_mp4_found"] += 1
            else:
                item["playback_url"] = None
                item["playback_format"] = None

            if license_url in DECLARED_PD_CC0:
                item["rights_status"] = "source_declares_pd_or_cc0_unverified"
                report["declared_pd_or_cc0"] += 1
            else:
                item["rights_status"] = "not_verified"

            # Never grant approval automatically: uploader declarations alone
            # do not prove copyright ownership or territorial redistribution rights.
            if item.get("review_status") != "approved":
                item["review_status"] = "rights_review_required"

        except Exception as exc:
            item["enrichment_error"] = str(exc)[:300]
            report["errors"] += 1

        time.sleep(0.8)

    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["items"] = items
    data["total_candidates"] = len(items)
    INPUT.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report["approved_with_direct_link"] = sum(
        1 for x in items
        if x.get("review_status") == "approved" and x.get("playback_url")
    )
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("VOD ENRICHMENT:", json.dumps(report, ensure_ascii=False))

if __name__ == "__main__":
    main()
