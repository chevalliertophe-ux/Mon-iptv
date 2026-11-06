import urllib.request
import subprocess
import json
import time
import re
from pathlib import Path

URL = "https://biskyt.github.io/legalFreeIPTVplaylist/movies.m3u"
USER_AGENT = "Mozilla/5.0"
DELAY_SECONDS = 3
MAX_RETRIES = 3

req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})

with urllib.request.urlopen(req, timeout=40) as response:
    data = response.read().decode("utf-8", "replace")

entries = []
title = None

for line in data.splitlines():
    line = line.strip()
    if line.startswith("#EXTINF:"):
        title = line.split(",", 1)[-1].strip()
    elif line.startswith("http") and title:
        entries.append({"title": title, "url": line})
        title = None


def test(item):
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            p = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-rw_timeout", "20000000",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name,width,height",
                    "-of", "json",
                    item["url"],
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = p.stdout or "{}"
            try:
                streams = json.loads(output).get("streams", [])
            except json.JSONDecodeError:
                streams = []

            error = (p.stderr or "")[-500:]

            if streams:
                return {
                    **item,
                    "status": "playable",
                    "playable_video": True,
                    "video": streams[0],
                    "attempts": attempt,
                    "error": None,
                }

            if re.search(r"\b429\b|Too Many Requests", error, re.I):
                last_error = error
                if attempt < MAX_RETRIES:
                    wait = 15 * attempt
                    print(f"429 : nouvelle tentative dans {wait}s — {item['title']}")
                    time.sleep(wait)
                    continue

                return {
                    **item,
                    "status": "rate_limited",
                    "playable_video": False,
                    "video": None,
                    "attempts": attempt,
                    "error": error,
                }

            last_error = error or f"ffprobe exit code {p.returncode}"

            return {
                **item,
                "status": "unavailable",
                "playable_video": False,
                "video": None,
                "attempts": attempt,
                "error": last_error,
            }

        except subprocess.TimeoutExpired:
            last_error = "FFprobe timeout"
        except Exception as exc:
            last_error = str(exc)

        if attempt < MAX_RETRIES:
            time.sleep(10 * attempt)

    return {
        **item,
        "status": "unavailable",
        "playable_video": False,
        "video": None,
        "attempts": MAX_RETRIES,
        "error": last_error,
    }


print("FILMS A TESTER :", len(entries))
results = []

for index, item in enumerate(entries, 1):
    print(f"[{index}/{len(entries)}] Test : {item['title']}")
    result = test(item)
    results.append(result)
    time.sleep(DELAY_SECONDS)

playable = [x for x in results if x["status"] == "playable"]
limited = [x for x in results if x["status"] == "rate_limited"]
unavailable = [x for x in results if x["status"] == "unavailable"]

Path("sources").mkdir(exist_ok=True)
Path("sources/vod_movies_playback_report.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("\nTOTAL :", len(results))
print("VIDEOS DETECTEES :", len(playable))
print("LIMITATIONS 429 :", len(limited))
print("INDISPONIBLES :", len(unavailable))
print("RAPPORT : sources/vod_movies_playback_report.json")
