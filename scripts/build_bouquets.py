import json
from pathlib import Path

root = Path(".")
channels = json.loads(
    (root / "sources/channels.json").read_text(encoding="utf-8")
)["channels"]

bouquets = {
    "FRANCE": [],
    "INTERNATIONAL": [],
    "DOCUMENTAIRES": [],
    "CINEMA": [],
    "SERIES": [],
    "ACTION": [],
    "JEUNESSE": [],
}

for c in channels:
    name = c["name"]
    url = c["url"]

    entry = {
        "name": name,
        "url": url,
        "group": c.get("group", "France"),
    }

    if name == "France 24 Français":
        bouquets["FRANCE"].append(entry)
        bouquets["INTERNATIONAL"].append(entry)

    elif name == "ARTE":
        bouquets["FRANCE"].append(entry)
        bouquets["DOCUMENTAIRES"].append(entry)

    elif name == "TV5MONDE Info":
        bouquets["FRANCE"].append(entry)
        bouquets["INTERNATIONAL"].append(entry)

out = root / "public/bouquets-draft"

for bouquet, entries in bouquets.items():
    lines = ["#EXTM3U"]

    for c in entries:
        lines.append(
            f'#EXTINF:-1 group-title="{bouquet}",{c["name"]}'
        )
        lines.append(c["url"])

    (out / f"{bouquet}.m3u").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )

platforms = {
    "notice": "Plateformes officielles externes : ces liens ne sont pas des flux M3U.",
    "platforms": [
        {
            "name": "France.tv",
            "url": "https://www.france.tv/",
            "categories": ["Films", "Séries", "Documentaires"],
            "access": "Gratuit avec publicité selon les programmes"
        },
        {
            "name": "ARTE",
            "url": "https://www.arte.tv/fr/",
            "categories": ["Cinéma", "Séries", "Documentaires"],
            "access": "Gratuit"
        },
        {
            "name": "TF1+",
            "url": "https://www.tf1.fr/",
            "categories": ["Films", "Séries"],
            "access": "Offre gratuite avec publicité et compte selon contenus"
        },
        {
            "name": "M6+",
            "url": "https://www.m6.fr/",
            "categories": ["Films", "Séries", "Jeunesse"],
            "access": "Offre gratuite avec publicité"
        },
        {
            "name": "Pluto TV",
            "url": "https://pluto.tv/fr/",
            "categories": ["Cinéma", "Séries", "Chaînes thématiques"],
            "access": "Gratuit avec publicité"
        }
    ]
}

(root / "public/bouquets-draft/vod-platforms.json").write_text(
    json.dumps(platforms, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("=== BOUQUETS CRÉÉS ===")
for name, entries in bouquets.items():
    print(f"{name}: {len(entries)} chaîne(s)")

print("Plateformes VOD répertoriées :", len(platforms["platforms"]))
print("Dossier : public/bouquets-draft/")
print("Playlists originales : conservées")
print("Publication : aucune")
