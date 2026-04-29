"""
Fix manuel des puuids non trouvés automatiquement.
Tags/gamenames spécifiques pour chaque joueur.
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.esports_player import EsportsPlayer
from models.esports_team import EsportsTeam
from models.pro_player import ProPlayer
from services.riot import get_account_by_riot_id

# Format : "SummonerName" : ("game_name", "tag", "region")
MANUAL_ENTRIES = {
    # LCK
    "Keria":     ("류민석",          "KR1",  "KR"),
    "Zeka":      ("Zeka",            "KR1",  "KR"),
    "Scout":     ("Scout",           "KR1",  "KR"),
    "Taeyoon":   ("Taeyoon",         "KR1",  "KR"),
    "Janus":     ("Janus",           "KR1",  "KR"),
    "SeTab":     ("SeTab",           "KR1",  "KR"),
    "Pleata":    ("Pleata",          "KR1",  "KR"),
    "Kemish":    ("Kemish",          "KR1",  "KR"),
    "SIRIUSS":   ("SIRIUSS",         "KR1",  "KR"),
    "MUDAI":     ("MUDAI",           "KR1",  "KR"),
    "Minous":    ("Minous",          "KR1",  "KR"),
    "AKaJe":    ("AKaJe",            "KR1",  "KR"),
    "Jiwoo":     ("Jiwoo",           "KR1",  "KR"),
    "Ucal":      ("Ucal",            "KR1",  "KR"),
    "Pyeonsik":  ("Pyeonsik",        "KR1",  "KR"),
    "Valiant":   ("Valiant",         "KR1",  "KR"),
    "Bluffing":  ("Bluffing",        "KR1",  "KR"),
    "Calix":     ("Calix",           "KR1",  "KR"),
    "Frog":      ("Frog",            "KR1",  "KR"),
    # LEC / LFL
    "Labrov":    ("Labrov",          "EUW",  "EUW"),
    "Caliste":   ("Caliste",         "EUW",  "EUW"),
    "kyeahoo":   ("kyeahoo",         "EUW",  "EUW"),
    "Lyncas":    ("Lyncas",          "EUW",  "EUW"),
    "Myrtus":    ("Myrtus",          "EUW",  "EUW"),
    "Rhilech":   ("Rhilech",         "EUW",  "EUW"),
    "SamD":      ("SamD",            "EUW",  "EUW"),
    "Kamiloo":   ("Kamiloo",         "EUW",  "EUW"),
    "MihawK":    ("MihawK",          "EUW",  "EUW"),
    "Gakgos":    ("Gakgos",          "EUW",  "EUW"),
    "Quad":      ("Quad",            "EUW",  "EUW"),
    "Pleata":    ("Pleata",          "EUW",  "EUW"),
    # LCS
    "Blaber":    ("Blaber",          "NA1",  "NA"),
    "Zven":      ("Zven",            "NA1",  "NA"),
    "Vulcan":    ("Vulcan",          "NA1",  "NA"),
    "Gryffinn":  ("Gryffinn",        "NA1",  "NA"),
    "Cryogen":   ("Cryogen",         "NA1",  "NA"),
    "Massu":     ("Massu",           "NA1",  "NA"),
    "Josedeodo": ("Josedeodo",       "NA1",  "NA"),
    "Photon":    ("Photon",          "NA1",  "NA"),
    "eXyu":      ("eXyu",            "NA1",  "NA"),
    "Palafox":   ("Palafox",         "NA1",  "NA"),
    "FBI":       ("FBI",             "NA1",  "NA"),
    "IgNar":     ("IgNar",           "NA1",  "NA"),
    "MISSING":   ("MISSING",         "NA1",  "NA"),
    "APA":       ("APA",             "NA1",  "NA"),
    "Thanatos":  ("Thanatos",        "NA1",  "NA"),
    "Gakgos":    ("Gakgos",          "NA1",  "NA"),
}

async def main():
    db = SessionLocal()
    found = 0
    not_found = []

    try:
        for summoner_name, (game_name, tag, region) in MANUAL_ENTRIES.items():
            ep = db.query(EsportsPlayer).filter(
                EsportsPlayer.summoner_name.ilike(summoner_name),
                EsportsPlayer.riot_puuid == None,
            ).first()

            if not ep:
                # Peut-être déjà lié
                continue

            print(f"  → {summoner_name:20} ({ep.team_code:6}) [{game_name}#{tag}] ", end="", flush=True)

            try:
                acc   = await get_account_by_riot_id(game_name, tag, region)
                puuid = acc["puuid"]

                # Doublon check
                existing = db.query(EsportsPlayer).filter(
                    EsportsPlayer.riot_puuid == puuid,
                    EsportsPlayer.id         != ep.id,
                ).first()
                if existing:
                    print(f"⚠️  déjà utilisé par {existing.summoner_name}")
                    continue

                ep.riot_puuid = puuid
                print(f"✅ {puuid[:20]}...")

                # Cascade ProPlayer
                pro = (
                    db.query(ProPlayer).filter(ProPlayer.riot_puuid == puuid).first() or
                    db.query(ProPlayer).filter(ProPlayer.name.ilike(summoner_name)).first() or
                    db.query(ProPlayer).filter(
                        ProPlayer.team.ilike(f"%{ep.team_code}%"),
                        ProPlayer.role == ep.role,
                    ).first()
                )
                if pro and not pro.riot_puuid:
                    pro.riot_puuid = puuid
                    pro.region     = region
                    if ep.photo_url and "default-headshot" not in (ep.photo_url or ""):
                        pro.photo_url = ep.photo_url
                    team_obj = db.query(EsportsTeam).filter(EsportsTeam.code == ep.team_code).first()
                    if team_obj:
                        pro.team_logo_url = team_obj.logo_url
                        pro.accent_color  = team_obj.accent_color
                    print(f"     ↳ ProPlayer '{pro.name}' mis à jour")

                found += 1
                db.commit()
                await asyncio.sleep(0.4)

            except Exception as e:
                print(f"❌ {e}")
                not_found.append(summoner_name)

        print(f"\n✅ {found} puuids trouvés")
        if not_found:
            print(f"❌ Encore manquants : {not_found}")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())