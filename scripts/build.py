import json
from pathlib import Path
from urllib.parse import urlparse
from xml.etree.ElementTree import Element, SubElement, ElementTree

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def valid_url(url):
    p = urlparse(url)
    return p.scheme in ("http", "https") and bool(p.netloc)

def make_playlist(items, filename, kind):
    lines = ["#EXTM3U"]
    for item in items:
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not valid_url(url):
            continue
        group = str(item.get("group", kind)).replace(",", " ")
        attrs = f'group-title="{group}"'
        logo = item.get("logo", "")
        if logo and valid_url(logo):
            attrs += f' tvg-logo="{logo}"'
        lines.extend([f"#EXTINF:-1 {attrs},{name}", url])
    (PUBLIC / filename).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

def main():
    PUBLIC.mkdir(exist_ok=True)
    channels = load(ROOT / "sources/channels.json")
    vod = load(ROOT / "sources/vod.json")

    make_playlist(channels.get("channels", []), "live.m3u", "Direct")
    make_playlist(vod.get("movies", []), "films.m3u", "Films")
    make_playlist(vod.get("series", []), "series.m3u", "Series")

    all_items = (
        channels.get("channels", [])
        + vod.get("movies", [])
        + vod.get("series", [])
    )
    make_playlist(all_items, "mon-iptv.m3u", "MON IPTV")

    tv = Element("tv")
    ElementTree(tv).write(
        PUBLIC / "guide.xml", encoding="utf-8", xml_declaration=True
    )
    print("MON IPTV : génération terminée")
    print("Chaînes :", len(channels.get("channels", [])))
    print("Films :", len(vod.get("movies", [])))
    print("Séries :", len(vod.get("series", [])))

if __name__ == "__main__":
    main()
