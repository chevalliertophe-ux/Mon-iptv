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


def load_old():
    if not OUTPUT.exists():
        return {}

    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    result = {}

    for item in data.get("channels", []):
        url = str(item.get("url", "")).strip().split("|", 1)[0].lower()
        if url and item.get("name"):
            result[url] = item

    return result


def parse_attr(line, key):
    match = re.search(rf'(?:^|\s){re.escape(key)}="([^"]*)"', line)
    return match.group(1).strip() if match else ""


def extract_name(line):
    quoted = False
    for index, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == "," and not quoted:
            return line[index + 1:].strip()
    return ""


def download(code):
    url = f"https://iptv-org.github.io/iptv/countries/{code}.m3u"
    request = urllib.request.Request(
        url, headers={"User-Agent": "MON-IPTV/1.0"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8", "replace")


def main():
    IMPORTS.mkdir(parents=True, exist_ok=True)
    old = load_old()
    updated = {}
    successful_countries = 0

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
                        previous = old.get(key, {})

                        fresh = {
                            "name": name,
                            "url": original_url,
                            "country": country,
                            "group": parse_attr(metadata, "group-title") or country,
                            "logo": parse_attr(metadata, "tvg-logo"),
                        }

                        # Préserver les décisions et contrôles déjà enregistrés.
                        item = {**previous, **fresh}
                        item["status"] = previous.get(
                            "status", "candidate_to_verify"
                        )
                        item["rights_status"] = previous.get(
                            "rights_status", "not_verified"
                        )

                        updated[key] = item
                        count += 1

                    metadata = None

            successful_countries += 1
            print(country, ":", count, "chaînes récupérées")

        except Exception as error:
            print(country, "ERREUR :", error)

    # Conserver les anciennes entrées absentes des nouvelles sources.
    preserved = 0
    for key, item in old.items():
        if key not in updated:
            updated[key] = item
            preserved += 1

    result = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_candidates": len(updated),
        "channels": list(updated.values()),
        "successful_country_sources": successful_countries,
        "notice": "Flux candidats : droits et lecture à vérifier."
    }

    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print("Anciennes entrées conservées :", preserved)
    print("Sources pays récupérées :", successful_countries, "/", len(COUNTRIES))
    print("TOTAL :", len(updated))


if __name__ == "__main__":
    main()
