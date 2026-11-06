import json
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

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


def clean(value):
    return str(value or "").replace('"', "").replace(",", " ").strip()


def make_playlist(items, filename, default_group, epg_map):
    lines = ["#EXTM3U"]
    count = 0
    seen = set()

    for item in items:
        name = clean(item.get("name", item.get("title", "")))
        url = str(item.get("url", item.get("playback_url", ""))).strip()

        if not name or not valid_url(url):
            continue

        key = url.split("|", 1)[0].lower()
        if key in seen:
            continue
        seen.add(key)

        group = clean(item.get("group", item.get("category", default_group)))
        attrs = [f'group-title="{group}"']

        logo = item.get("logo", "")
        if valid_url(logo):
            attrs.append(f'tvg-logo="{logo}"')

        epg_id = epg_map.get(name.lower())
        if epg_id:
            attrs.append(f'tvg-id="{clean(epg_id)}"')

        lines.extend([
            f'#EXTINF:-1 {" ".join(attrs)},{name}',
            url
        ])
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
    epg_data = load(SOURCES / "epg_channel_map.json")

    epg_map = {
        item["name"].strip().lower(): item["tvg_id"]
        for item in epg_data.get("channels", [])
        if item.get("name") and item.get("tvg_id")
    }

    channels = list(channels_data.get("channels", []))

    for item in tv_data.get("channels", []):
        if (
            item.get("status") == "verified"
            and item.get("rights_status") == "authorized"
        ):
            channels.append(item)

    movies = [
        item for item in vod_data.get("movies", [])
        if item.get("review_status") == "approved"
    ]

    series = [
        item for item in vod_data.get("series", [])
        if item.get("review_status") == "approved"
    ]

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

    live_count = make_playlist(
        channels, "live.m3u", "Direct", epg_map
    )
    movie_count = make_playlist(
        movies, "films.m3u", "Films", {}
    )
    series_count = make_playlist(
        series, "series.m3u", "Series", {}
    )

    make_playlist(
        channels + movies + series,
        "mon-iptv.m3u",
        "MON IPTV",
        epg_map
    )

    # Ne jamais remplacer un véritable EPG par un XML vide.
    guide = PUBLIC / "guide.xml"

    if guide.exists():
        try:
            root = ET.parse(guide).getroot()
            if root.tag != "tv":
                raise ValueError("Racine XMLTV invalide")
            print("EPG conservé :", len(root.findall("programme")), "programmes")
        except Exception as error:
            raise RuntimeError(
                f"EPG existant invalide : publication interrompue : {error}"
            )
    else:
        print("ATTENTION : aucun guide EPG existant")

    print("MON IPTV : génération terminée")
    print("TV validées :", live_count)
    print("Films validés :", movie_count)
    print("Séries validées :", series_count)
    print("Candidats TV en attente :", len(tv_data.get("channels", [])))
    print("Candidats VOD en attente :", len(vod_candidates.get("items", [])))


if __name__ == "__main__":
    main()
