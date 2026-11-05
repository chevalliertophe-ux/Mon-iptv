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
    match = re.search(
        rf'(?:^|\s){re.escape(key)}="([^"]*)"',
        line
    )
    return match.group(1).strip() if match else ""


def extract_name(line):
    quoted = False

    for index, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == "," and not quoted:
            return line[index + 1:].strip()

    return ""


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
        old = {}
        for item in data.get("channels", []):
            original_url = str(item.get("url", "")).strip()
            name = str(item.get("name", "")).strip()

            if not original_url or not name or "like Gecko)" in name:
                continue

            key = original_url.split("|", 1)[0].strip().lower()
            if key:
                old[key] = item

    updated = {}

    for code, country in COUNTRIES.items():
        try:
            content = download(code)
            (IMPORTS / f"{country.lower()}.m3u").write_text(
                content, encoding="utf-8"
            )

            metadata = None
            count = 0

            for raw_line in content.splitlines():
                line = raw_line.strip()

                if line.startswith("#EXTINF"):
                    metadata = line
                    continue

                if line and not line.startswith("#") and metadata:
                    original_url = line
                    url = line.split("|", 1)[0].strip()
                    name = extract_name(metadata)

                    if url.startswith(("http://", "https://")) and name:
                        key = url.lower()

                        updated[key] = {
                            "name": name,
                            "url": original_url,
                            "country": country,
                            "group": parse_attr(
                                metadata, "group-title"
                            ) or country,
                            "logo": parse_attr(metadata, "tvg-logo"),
                            "status": "candidate_to_verify",
                            "rights_status": "not_verified"
                        }
                        count += 1

                    metadata = None

            print(country, ":", count, "chaînes candidates")

        except Exception as error:
            print(country, "ERREUR :", error)

    # Conserver les anciennes entrées uniquement si leur nom est propre.
    preserved = 0
    rejected = 0

    for url, item in old.items():
        name = str(item.get("name", "")).strip()

        if not name or "like Gecko)" in name:
            rejected += 1
            continue

        if url not in updated:
            updated[url] = item
            preserved += 1

    print("ANCIENNES ENTREES CONSERVEES :", preserved)
    print("ANCIENNES ENTREES ECARTEES :", rejected)

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
