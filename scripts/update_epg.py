import gzip
import json
import os
import tempfile
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
MAP_FILE = ROOT / "sources/epg_channel_map.json"

COUNTRIES = ["fr", "ch", "it", "es"]
BASE_URL = "https://iptv-epg.org/files/epg-{}.xml"
USER_AGENT = "MON-IPTV/1.0"

NOW = datetime.now(timezone.utc)
LIMIT = NOW + timedelta(days=7)


def parse_xmltv_date(value):
    value = str(value or "").strip()
    if not value:
        return None

    try:
        if len(value) > 14:
            result = datetime.strptime(value, "%Y%m%d%H%M%S %z")
        else:
            result = datetime.strptime(value[:14], "%Y%m%d%H%M%S")
            result = result.replace(tzinfo=timezone.utc)

        return result.astimezone(timezone.utc)
    except ValueError:
        return None



def clean_xml_whitespace(elem):
    """Supprime uniquement les espaces de mise en forme XML."""
    if elem.tail is not None and not elem.tail.strip():
        elem.tail = None

    for child in elem:
        clean_xml_whitespace(child)


def download(country):
    url = BASE_URL.format(country)
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT}
    )

    response = urllib.request.urlopen(request, timeout=240)
    return response


def main():
    PUBLIC.mkdir(exist_ok=True)

    mapping = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    selected = {}

    for item in mapping.get("channels", []):
        country = item["country"].lower()
        tvg_id = item["tvg_id"]

        if country not in COUNTRIES or not tvg_id:
            raise ValueError(f"Correspondance EPG invalide : {item}")

        selected.setdefault(country, set()).add(tvg_id)

    if not selected:
        raise ValueError("Aucune chaîne EPG configurée")

    fd, temp_xml = tempfile.mkstemp(
        prefix="guide-", suffix=".xml", dir=PUBLIC
    )
    os.close(fd)

    fd, temp_gz = tempfile.mkstemp(
        prefix="guide-", suffix=".xml.gz", dir=PUBLIC
    )
    os.close(fd)

    total_channels = 0
    total_programmes = 0
    failed = []

    try:
        with open(temp_xml, "wb") as output:
            output.write(
                b'<?xml version="1.0" encoding="UTF-8"?>\n'
                b'<tv generator-info-name="MON IPTV">\n'
            )

            for country in COUNTRIES:
                wanted = selected.get(country, set())

                if not wanted:
                    continue

                print(f"\n=== EPG {country.upper()} ===")

                try:
                    with download(country) as response:
                        with tempfile.NamedTemporaryFile(
                            mode="wb", suffix=".xml", delete=False
                        ) as source:
                            source_path = source.name
                            while True:
                                chunk = response.read(1024 * 1024)
                                if not chunk:
                                    break
                                source.write(chunk)

                    try:
                        found = set()

                        # Première lecture : définitions des chaînes.
                        for _, elem in ET.iterparse(
                            source_path, events=("end",)
                        ):
                            if elem.tag == "channel":
                                channel_id = elem.get("id")

                                if channel_id in wanted:
                                    output.write(
                                        ET.tostring(
                                            elem,
                                            encoding="utf-8"
                                        ) + b"\n"
                                    )
                                    found.add(channel_id)
                                    total_channels += 1

                                elem.clear()

                        print("Chaînes trouvées :", len(found), "/", len(wanted))

                        # Deuxième lecture : programmes des chaînes retenues.
                        count = 0

                        for _, elem in ET.iterparse(
                            source_path, events=("end",)
                        ):
                            if elem.tag == "programme":
                                channel_id = elem.get("channel")

                                if channel_id in found:
                                    start = parse_xmltv_date(elem.get("start"))
                                    stop = parse_xmltv_date(elem.get("stop"))

                                    if start and stop and start < LIMIT and stop > NOW:
                                        output.write(
                                            ET.tostring(
                                                elem,
                                                encoding="utf-8"
                                            ) + b"\n"
                                        )
                                        count += 1

                                elem.clear()

                        total_programmes += count
                        print("Programmes retenus :", count)

                    finally:
                        os.unlink(source_path)

                except Exception as error:
                    failed.append(country)
                    print("ERREUR :", country, repr(error))

            output.write(b"</tv>\n")

        # Ne pas remplacer le guide public si une source configurée échoue.
        required = [c for c in COUNTRIES if selected.get(c)]

        if failed or any(
            not selected.get(c) for c in required
        ):
            raise RuntimeError(
                "EPG incomplet : " + ", ".join(failed)
            )

        # Créer le fichier compressé avant publication.
        with open(temp_xml, "rb") as source:
            with gzip.open(temp_gz, "wb", compresslevel=9) as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)

        # Validation XML finale.
        ET.parse(temp_xml)

        os.replace(temp_xml, PUBLIC / "guide.xml")
        os.replace(temp_gz, PUBLIC / "guide.xml.gz")

        print("\n========== EPG TERMINE ==========")
        print("Chaînes :", total_channels)
        print("Programmes :", total_programmes)
        print("Période :", NOW.isoformat(), "->", LIMIT.isoformat())
        print("Fichier :", PUBLIC / "guide.xml")
        print("Compression :", PUBLIC / "guide.xml.gz")

    except Exception:
        for path in (temp_xml, temp_gz):
            if os.path.exists(path):
                os.unlink(path)
        raise


if __name__ == "__main__":
    main()
