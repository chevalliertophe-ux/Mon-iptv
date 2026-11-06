import json
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sources/tv_candidates.json"
OUTPUT = ROOT / "sources/tv_playback_report.json"

data = json.loads(SOURCE.read_text(encoding="utf-8"))
channels = data.get("channels", [])

def test(item):
    url = item.get("url", "").split("|", 1)[0].strip()
    if not url.startswith(("http://", "https://")):
        return item, False, "URL invalide"

    cmd = [
        "ffprobe", "-v", "error",
        "-rw_timeout", "12000000",
        "-user_agent", "MON-IPTV/1.0",
        "-analyzeduration", "3000000",
        "-probesize", "3000000",
        "-show_entries", "stream=codec_type,codec_name",
        "-of", "json",
        url
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0:
            return item, False, result.stderr[:250]

        streams = json.loads(result.stdout).get("streams", [])
        video = any(s.get("codec_type") == "video" for s in streams)
        audio = any(s.get("codec_type") == "audio" for s in streams)

        if video:
            codecs = ",".join(s.get("codec_name", "?") for s in streams)
            return item, True, f"VIDEO OK | AUDIO={audio} | {codecs}"

        return item, False, "Aucun flux vidéo détecté"

    except Exception as e:
        return item, False, str(e)[:250]

results = []

print("TEST FFPROBE :", len(channels), "chaînes")

with ThreadPoolExecutor(max_workers=4) as pool:
    futures = [pool.submit(test, item) for item in channels]
    for i, future in enumerate(as_completed(futures), 1):
        item, ok, detail = future.result()
        results.append({
            "name": item.get("name"),
            "url": item.get("url"),
            "country": item.get("country"),
            "video_detected": ok,
            "detail": detail
        })
        if i % 25 == 0:
            print("Progression :", i, "/", len(channels))

valid = sum(x["video_detected"] for x in results)

OUTPUT.write_text(json.dumps({
    "total": len(results),
    "video_detected": valid,
    "failed": len(results) - valid,
    "notice": "Détection FFprobe, pas une garantie de lecture continue ni de droits.",
    "results": results
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("\nTOTAL :", len(results))
print("VIDEO DETECTEE :", valid)
print("ECHECS :", len(results) - valid)
print("RAPPORT :", OUTPUT)
