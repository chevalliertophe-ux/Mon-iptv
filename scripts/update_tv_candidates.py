import json
import re
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ROOT / "sources/imports"
OUTPUT = ROOT / "sources/tv_candidates.json"

COUNTRIES = {
    "fr": "France",
    "ch": "Suisse",
    "it": "Italie",
    "es": "Espagne"
}

def parse_attr(line, key):
    match = re.search(rf'{re.escape(key)}="([^"]*)"', line)
    return match.group(1).strip() if match else ""

def download(country_code):
    url = f"https://iptv-org.github.io/iptv/countries/{country_code}.m3u"
    request = urllib.request.Request(
        url, headers={"User-Agent": "MON-IPTV/1.0"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8", "replace")

def main():
    old = {}
    if OUTPUT.exists():
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        old = {
            x["url"]: x
            for x in data.get("channels", [])
            if x.get("url")
        }

    updated = {}
    for code, country in COUNTRIES.items():
        try:
            content = download(code)
            (IMPORTS / f"{country.lower()}.m3u").write_text(
                content, encoding="utf-8"
            )
            metadata = None
            count = 0

            for line in content.splitlines():
                line = line.strip()
                if line.startswith("#EXTINF"):
                    metadata = line
                elif line and not line.startswith("#") and metadata:
                    url = line.split("|", 1)[0]
                    name = metadata.split(",", 1)[-1].strip()

                    if url.startswith(("http://", "https://")) and name:
                        key = url.lower()
                        updated[key] = {
                            "name": name,
                            "url": line,
                            "country": country,
                            "group": parse_attr(metadata, "group-title") or country,
                            "logo": parse_attr(metadata, "tvg-logo"),
                            "status": "candidate_to_verify",
                            "rights_status": "not_verified"
                        }
                        count += 1
                    metadata = None

            print(country, ":", count, "chaînes candidates")
        except Exception as error:
            print(country, "ERREUR :", error)

    # Preserve prior candidates if a source is temporarily unavailable.
    for url, item in old.items():
        updated.setdefault(url, item)

    result = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_candidates": len(updated),
        "channels": list(updated.values()),
        "notice": "Flux candidats : droits et lecture à vérifier."
    }

    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print("TOTAL :", len(updated))
    print("FICHIER :", OUTPUT)

if __name__ == "__main__":
    main()
