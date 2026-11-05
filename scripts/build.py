import json
from pathlib import Path
from urllib.parse import urlparse
from xml.etree.ElementTree import Element, ElementTree

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SOURCES = ROOT / "sources"


def load(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def valid_url(url):
    p = urlparse(str(url or ""))
    return p.scheme in ("http", "https") and bool(p.netloc)


def make_playlist(items, filename, default_group):
    lines = ["#EXTM3U"]
    count = 0

    for item in items:
        name = str(item.get("name", item.get("title", ""))).strip()
        url = str(item.get("url", item.get("playback_url", ""))).strip()

        if not name or not valid_url(url):
            continue

        group = str(item.get("group", item.get("category", default_group)))
        group = group.replace(",", " ").replace('"', "")

        attrs = f'group-title="{group}"'
        logo = item.get("logo", "")

        if valid_url(logo):
            attrs += f' tvg-logo="{logo}"'

        lines.extend([f"#EXTINF:-1 {attrs},{name}", url])
        count += 1

    (PUBLIC / filename).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return count


def main():
    PUBLIC.mkdir(exist_ok=True)

    channels_data = load(SOURCES / "channels.json")
    vod_data = load(SOURCES / "vod.json")
    tv_data = load(SOURCES / "tv_candidates.json")
    vod_candidates = load(SOURCES / "vod_candidates.json")

    # Sources fixes conservées, plus candidats explicitement validés.
    channels = list(channels_data.get("channels", []))

    for item in tv_data.get("channels", []):
        if (
            item.get("status") == "verified"
            and item.get("rights_status") == "authorized"
        ):
            channels.append(item)

    # Les contenus VOD nécessitent une validation explicite.
    movies = []
    series = []

    for item in vod_data.get("movies", []):
        if item.get("review_status") == "approved":
            movies.append(item)

    for item in vod_data.get("series", []):
        if item.get("review_status") == "approved":
            series.append(item)

    for item in vod_candidates.get("items", []):
        if (
            item.get("review_status") == "approved"
            and valid_url(item.get("playback_url"))
        ):
            category = str(item.get("category", "")).lower()

            entry = {
                "name": item.get("title", ""),
                "url": item.get("playback_url", ""),
                "group": item.get("category", "VOD")
            }

            if "série" in category or "series" in category:
                series.append(entry)
            else:
                movies.append(entry)

    live_count = make_playlist(channels, "live.m3u", "Direct")
    movie_count = make_playlist(movies, "films.m3u", "Films")
    series_count = make_playlist(series, "series.m3u", "Series")

    make_playlist(
        channels + movies + series,
        "mon-iptv.m3u",
        "MON IPTV"
    )

    tv = Element("tv")
    ElementTree(tv).write(
        PUBLIC / "guide.xml",
        encoding="utf-8",
        xml_declaration=True
    )

    print("MON IPTV : génération terminée")
    print("TV validées :", live_count)
    print("Films validés :", movie_count)
    print("Séries validées :", series_count)
    print("Candidats TV en attente :", len(tv_data.get("channels", [])))
    print("Candidats VOD en attente :", len(vod_candidates.get("items", [])))


if __name__ == "__main__":
    main()
