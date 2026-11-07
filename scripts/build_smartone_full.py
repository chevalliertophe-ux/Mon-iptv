import json
import re
import urllib.request
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
CACHE = ROOT / "sources/cache/smartone"

FREECAST_URL = (
    "https://raw.githubusercontent.com/freecasthub/"
    "public-iptv/main/playlist.m3u"
)
BISKYT_URL = (
    "https://biskyt.github.io/legalFreeIPTVplaylist/playlist.m3u"
)

SAFE_MOVIE_GROUPS = {
    "Movies: World Classics",
    "Movies: Shorts",
    "Movies: Open Movies",
    "Documentaries: Wikimedia Commons",
}

def download(url, timeout=60):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "MON-IPTV-SmartOne/1.0"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8-sig", "replace")

def obtain(url, cache_file, fallbacks=()):
    try:
        content = download(url)
        if "#EXTM3U" not in content:
            raise ValueError("Réponse reçue sans en-tête M3U")
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(content, encoding="utf-8")
        print("Source actualisée :", url)
        return content
    except Exception as error:
        print("Source distante indisponible :", url, "-", error)

    if cache_file.exists():
        print("Utilisation de la dernière copie :", cache_file)
        return cache_file.read_text(encoding="utf-8", errors="replace")

    for fallback in fallbacks:
        if fallback.exists():
            print("Utilisation de la copie locale :", fallback)
            return fallback.read_text(encoding="utf-8", errors="replace")

    raise RuntimeError("Aucune copie disponible pour " + url)

def parse_m3u(content, source):
    entries = []
    meta = None
    options = []

    for raw in content.splitlines():
        line = raw.strip()

        if line.startswith("#EXTINF:"):
            meta = line
            options = []
            continue

        if meta and line.startswith("#EXTVLCOPT:"):
            options.append(line)
            continue

        if meta and line.startswith(("http://", "https://")):
            prefix, sep, name = meta.partition(",")
            duration_match = re.match(r"#EXTINF:([^\s]+)", prefix)
            duration = duration_match.group(1) if duration_match else "-1"

            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', prefix))
            entries.append({
                "duration": duration,
                "attrs": attrs,
                "name": name.strip() if sep else "Sans nom",
                "url": line,
                "options": options[:],
                "source": source,
            })
            meta = None
            options = []

    return entries

def clean(value):
    return re.sub(r"[\r\n,]+", " ", str(value or "")).strip()

def render(entry, kind, group):
    attrs = dict(entry["attrs"])
    attrs["tvg-type"] = kind
    attrs["group-title"] = group
    attrs["tvg-name"] = attrs.get("tvg-name") or clean(entry["name"])

    attr_text = " ".join(
        f'{key}="{str(value).replace(chr(34), chr(39)).replace(chr(10), " ")}"'
        for key, value in attrs.items()
        if value is not None and value != ""
    )

    lines = [
        f'#EXTINF:{entry["duration"]} {attr_text},{clean(entry["name"])}'
    ]
    lines.extend(entry["options"])
    lines.append(entry["url"])
    return "\n".join(lines)

def url_key(url):
    return url.split("|", 1)[0].strip().rstrip("/").lower()

def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)

    freecast = obtain(
        FREECAST_URL,
        CACHE / "freecasthub.m3u",
        [ROOT / "sources/imports/review/public-iptv.m3u"]
    )

    try:
        biskyt = obtain(
            BISKYT_URL,
            CACHE / "biskyt.m3u"
        )
    except Exception:
        # Si le flux combiné est indisponible, récupérer les flux séparés.
        parts = []
        for name in ("live", "movies", "series"):
            parts.append(download(
                f"https://biskyt.github.io/legalFreeIPTVplaylist/{name}.m3u"
            ))
        biskyt = "\n".join(parts)
        (CACHE / "biskyt.m3u").write_text(biskyt, encoding="utf-8")
        print("Flux Biskyt séparés récupérés.")

    free_entries = parse_m3u(freecast, "FreeCastHub")
    biskyt_entries = parse_m3u(biskyt, "LegalFreeIPTV")

    channels = []

    # Chaînes déjà déclarées dans le catalogue officiel MON-IPTV.
    channels_file = ROOT / "sources/channels.json"
    if channels_file.exists():
        data = json.loads(channels_file.read_text(encoding="utf-8"))
        for item in data.get("channels", []):
            channels.append({
                "duration": "-1",
                "attrs": {
                    "tvg-id": item.get("tvg-id", ""),
                    "tvg-name": item.get("name", ""),
                },
                "name": item.get("name", ""),
                "url": item.get("url", ""),
                "options": [],
                "source": "MON-IPTV",
                "group": item.get("group", "France"),
            })

    # Chaînes diffusées par les propriétaires et retenues par le catalogue Biskyt.
    for item in biskyt_entries:
        if item["attrs"].get("tvg-type", "live").lower() == "live":
            channels.append(item)

    # Chaînes du catalogue FreeCastHub, annoncé comme regroupant
    # des flux gratuits de diffuseurs publics et officiels.
    channels.extend(free_entries)

    movies = []
    series = []

    for item in biskyt_entries:
        attrs = item["attrs"]
        kind = attrs.get("tvg-type", "live").lower()
        group = attrs.get("group-title", "").strip()

        if kind == "movie" and group in SAFE_MOVIE_GROUPS:
            movies.append(item)
        elif kind == "series":
            series.append(item)

    # Déduplication des chaînes et des VOD.
    def deduplicate(items):
        result = []
        seen = set()
        for item in items:
            url = item.get("url", "")
            if not url.startswith(("http://", "https://")):
                continue
            key = url_key(url)
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result

    channels = deduplicate(channels)
    movies = deduplicate(movies)
    series = deduplicate(series)

    # Protection contre une source distante incomplète.
    if len(channels) < 30:
        raise RuntimeError(
            f"Seulement {len(channels)} chaînes : publication annulée."
        )
    if len(movies) < 10:
        raise RuntimeError(
            f"Seulement {len(movies)} films libres identifiés : publication annulée."
        )

    def group_for_live(item):
        group = item.get("group") or item["attrs"].get("group-title") or "International"
        return "TV | " + group.replace("TV | ", "")

    def group_for_vod(item, default):
        group = item["attrs"].get("group-title", default)
        if group.startswith("Movies:"):
            return "Movies | " + group.split(":", 1)[1].strip()
        if group.startswith("Documentaries:"):
            return "Documentaries | " + group.split(":", 1)[1].strip()
        return group

    tv_lines = []
    for item in channels:
        tv_lines.append(render(item, "live", group_for_live(item)))

    vod_lines = []
    for item in movies:
        vod_lines.append(render(item, "movie", group_for_vod(item, "Films")))
    for item in series:
        series_name = item["attrs"].get("series-name", "Séries")
        vod_lines.append(render(item, "series", "Series | " + series_name))

    full_lines = tv_lines + vod_lines

    def write_playlist(filename, lines):
        path = PUBLIC / filename
        path.write_text(
            "#EXTM3U\n" + "\n".join(lines) + "\n",
            encoding="utf-8"
        )
        return path

    write_playlist("mon-iptv-smartone-tv.m3u", tv_lines)
    write_playlist("mon-iptv-smartone-vod.m3u", vod_lines)
    write_playlist("mon-iptv-smartone-full.m3u", full_lines)

    report = {
        "tv": len(tv_lines),
        "movies": len(movies),
        "series_episodes": len(series),
        "vod": len(vod_lines),
        "total": len(full_lines),
        "sources": ["MON-IPTV", "FreeCastHub", "LegalFreeIPTV"],
        "movie_groups_allowed": sorted(SAFE_MOVIE_GROUPS),
        "notice": (
            "TV: flux issus de catalogues de chaînes gratuites officielles. "
            "VOD: uniquement groupes Blender et Wikimedia Commons autorisés "
            "par la sélection de la source. Les séries ne sont incluses "
            "que si la source apporte une preuve de droits."
        )
    }

    report_path = CACHE / "build-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print("\n========== MON-IPTV SMARTONE ==========")
    print("Chaînes TV :", len(tv_lines))
    print("Films :", len(movies))
    print("Épisodes de séries :", len(series))
    print("TOTAL :", len(full_lines))
    print("Playlist complète :", PUBLIC / "mon-iptv-smartone-full.m3u")
    print("Rapport :", report_path)

if __name__ == "__main__":
    main()
