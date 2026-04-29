import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import asyncio
import re
from database import SessionLocal
from models.pro_player import ProPlayer
from services.riot import get_account_by_riot_id

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Mapping nom pro → slug trackingthepros
PRO_SLUGS = {
    # T1
    "Doran": "Doran", "Oner": "Oner", "Faker": "Faker", "Peyz": "Peyz", "Keria": "Keria",
    # Gen.G
    "Kiin": "Kiin", "Canyon": "Canyon", "Chovy": "Chovy", "Ruler": "Ruler", "Lehends": "Lehends",
    # HLE
    "Zeus": "Zeus", "Kanavi": "Kanavi", "Zeka": "Zeka", "Gumayusi": "Gumayusi", "Delight": "Delight",
    # KT
    "Kingen": "Kingen", "Cuzz": "Cuzz", "Bdd": "Bdd", "Aiming": "Aiming", "Ghost": "Ghost",
    # DRX
    "Rich": "Rich", "Vincenzo": "Vincenzo", "ucal": "Ucal", "Jiwoo": "Jiwoo", "Andil": "Andil",
    # Dplus KIA
    "Siwoo": "Siwoo", "Lucid": "Lucid", "ShowMaker": "ShowMaker", "Smash": "Smash", "Career": "Career",
    # Nongshim
    "Sponge": "Sponge", "Scout": "Scout", "Taeyoon": "Taeyoon",
    # FEARX
    "Raptor": "Raptor", "VicLa": "VicLa", "Clear": "Clear", "Kellin": "Kellin",
    # DN SOOPers
    "DuDu": "DuDu", "Pyosik": "Pyosik", "Clozer": "Clozer", "deokdam": "Deokdam", "Peter": "Peter",
    # LEC
    "Caps": "Caps", "BrokenBlade": "BrokenBlade", "SkewMond": "SkewMond",
    "Hans Sama": "Hans-Sama", "Labrov": "Labrov",
    "Empyros": "Empyros", "Razork": "Razork", "Vladi": "Vladi", "Upset": "Upset", "Lospa": "Lospa",
    "Canna": "Canna", "Yike": "Yike", "Kyeahoo": "Kyeahoo", "Caliste": "Caliste", "Busio": "Busio",
    "Elyoya": "Elyoya", "Jojopyun": "Jojopyun", "Humanoid": "Humanoid",
    "Jackies": "Jackies", "Wunder": "Wunder", "Mikyx": "Mikyx",
    "Odoamne": "Odoamne", "Larssen": "Larssen", "Patrik": "Patrik",
    "Myrwn": "Myrwn", "Supa": "Supa", "Lot": "Lot", "ISMA": "Isma",
    "Noah": "Noah", "Jun": "Jun", "Naak Nako": "Naak-Nako", "Lyncas": "Lyncas",
    "Carzzy": "Carzzy", "Fleshy": "Fleshy", "Rooster": "Rooster",
    "Boukada": "Boukada", "nuc": "Nuc", "Paduck": "Paduck", "Trymbi": "Trymbi",
    "Markoon": "Markoon", "Reeker": "Reeker", "Exakick": "Exakick",
    "Daglas": "Daglas", "Tracyn": "Tracyn", "Maynter": "Maynter",
    "Sanchi": "Sanchi", "Poby": "Poby",
}

REGION_MAP = { "KR": "KR", "EUW": "EUW", "CN": "CN" }

def get_best_account(html: str, region: str) -> str | None:
    region_tag = f"[{region}]"
    clean = re.sub(r'<[^>]+>', '', html)
    lines = clean.split("\n")

    best_account = None
    best_lp = -1

    for line in lines:
        line = line.strip()
        if not line or region_tag not in line:
            continue

        match = re.search(r'([^\[\]\s][^#\[\]]*#([A-Za-z0-9]{2,8}?))(GM|Ch|Master|Diamond|Platinum|Gold|Silver|Bronze|Iron|\d+LP|\s|$)', line)
        if not match:
            continue

        raw = match.group(1).strip()

        parts = raw.split("#")
        if len(parts) != 2:
            continue

        game_name = parts[0].strip()
        tag = re.sub(r'[^A-Za-z0-9]', '', parts[1])[:8]
        account = f"{game_name}#{tag}"

        lp_match = re.search(r'(\d+)\s*LP', line)
        lp = int(lp_match.group(1)) if lp_match else 0

        if lp > best_lp:
            best_lp = lp
            best_account = account

    return best_account


async def fetch_pro_account(slug: str, region: str) -> str | None:
    url = f"https://www.trackingthepros.com/player/{slug}"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as client:
            res = await client.get(url)
            if res.status_code != 200:
                return None
            return get_best_account(res.text, region)
    except Exception as e:
        print(f"   ❌ Erreur fetch {slug}: {e}")
        return None

async def main():
    db = SessionLocal()
    pros = db.query(ProPlayer).filter(ProPlayer.riot_puuid == None).all()
    print(f"📡 {len(pros)} joueurs sans puuid à traiter\n")

    for pro in pros:
        slug = PRO_SLUGS.get(pro.name)
        if not slug:
            print(f"⏭️  {pro.name} — pas de slug connu, skip")
            continue

        print(f"🔍 {pro.name} ({pro.team})...")
        account_str = await fetch_pro_account(slug, pro.region)

        if not account_str:
            print(f"   ⚠️  Pas de compte {pro.region} trouvé")
            continue

        parts = account_str.split("#")
        if len(parts) != 2:
            print(f"   ⚠️  Format invalide: {account_str}")
            continue

        game_name = parts[0].strip()
        tag = re.sub(r'[^A-Za-z0-9]', '', parts[1])[:8]
        print(f"   → Compte trouvé: {game_name}#{tag}")

        try:
            account = await get_account_by_riot_id(game_name, tag, pro.region)
            pro.riot_puuid = account["puuid"]
            db.commit()
            print(f"   ✅ PUUID lié: {account['puuid'][:20]}...")
        except Exception as e:
            print(f"   ❌ Riot API error: {e}")

        await asyncio.sleep(1.5)

    db.close()
    print(f"\n🎮 Terminé !")

if __name__ == "__main__":
    asyncio.run(main())