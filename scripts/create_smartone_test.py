import json
from pathlib import Path

S = Path("sources")
P = Path("public")
P.mkdir(exist_ok=True)

films = json.loads(
    (S / "vod_movies_playback_report.json").read_text(encoding="utf-8")
)
tv = json.loads(
    (S / "hls-segment-sample-report.json").read_text(encoding="utf-8")
)

films = [x for x in films if x.get("playable_video") is True]
tv = [x for x in tv if x.get("segment_ok") is True]

def make(items, filename, group):
    lines = ["#EXTM3U"]
    seen = set()
    count = 0

    for x in items:
        url = (x.get("url") or "").strip()
        name = (x.get("title") or "Sans titre").replace(",", " ").strip()

        if not url.startswith(("http://", "https://")) or url in seen:
            continue

        seen.add(url)
        lines.append(f'#EXTINF:-1 group-title="{group}",{name}')
        lines.append(url)
        count += 1

    (P / filename).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return count

f = make(films, "films-test.m3u", "Films - test technique")
t = make(tv, "live-test-validated-sample.m3u", "TV - test technique")

combined = [
    (P / "live-test-validated-sample.m3u").read_text(encoding="utf-8").strip(),
    (P / "films-test.m3u").read_text(encoding="utf-8").split("\n", 1)[1].strip()
]
(P / "mon-iptv-test.m3u").write_text(
    combined[0] + "\n" + combined[1] + "\n",
    encoding="utf-8"
)

print("=== PLAYLISTS SMARTONE DE TEST ===")
print("Films :", f)
print("TV :", t)
print("TOTAL :", f + t)
print("Fichiers créés dans public/")
print("Publication GitHub : NON")
print("Playlists originales : CONSERVÉES")
