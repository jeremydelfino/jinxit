import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import httpx
from bs4 import BeautifulSoup
from database import SessionLocal
from models.pro_player import ProPlayer
from services.cloudinary_service import upload_image

# Liquipedia base URL
LIQUIPEDIA_BASE = "https://liquipedia.net/leagueoflegends"

HEADERS = {
    "User-Agent": "junglegap/1.0 (educational project; contact: ton@email.com)",
    "Accept-Language": "en-US,en;q=0.9",
}

async def fetch_liquipedia_photo(name: str, client: httpx.AsyncClient) -> bytes | None:
    """Scrape la photo d'un joueur sur Liquipedia."""
    url = f"{LIQUIPEDIA_BASE}/{name}"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            print(f"   ⚠️  Page introuvable pour {name} (status {resp.status_code})")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # L'image du joueur est dans .infobox-image ou .player-image
        img_tag = (
            soup.select_one(".infobox-image img") or
            soup.select_one(".player-image img") or
            soup.select_one(".infobox img")
        )

        if not img_tag:
            print(f"   ⚠️  Aucune image trouvée pour {name}")
            return None

        img_src = img_tag.get("src") or img_tag.get("data-src")
        if not img_src:
            return None

        # Reconstruire l'URL complète
        if img_src.startswith("//"):
            img_src = "https:" + img_src
        elif img_src.startswith("/"):
            img_src = "https://liquipedia.net" + img_src

        # Télécharger l'image
        img_resp = await client.get(img_src, headers=HEADERS, timeout=10)
        if img_resp.status_code == 200:
            return img_resp.content

        return None

    except Exception as e:
        print(f"   ❌ Erreur fetch {name}: {e}")
        return None


async def update_pro_photos():
    db = SessionLocal()
    pros = db.query(ProPlayer).filter(
        ProPlayer.photo_url == None,
        ProPlayer.is_active == True
    ).all()

    print(f"📸 {len(pros)} pros sans photo à mettre à jour...\n")

    async with httpx.AsyncClient() as client:
        for pro in pros:
            print(f"🔍 {pro.name} ({pro.team})...")

            # Liquipedia utilise le nom du joueur dans l'URL
            photo_bytes = await fetch_liquipedia_photo(pro.name, client)

            if photo_bytes:
                try:
                    url = await upload_image(
                        photo_bytes,
                        folder="junglegap/pros",
                        public_id=f"pro_{pro.id}_{pro.name.lower()}"
                    )
                    pro.photo_url = url
                    db.commit()
                    print(f"   ✅ Photo uploadée → {url}")
                except Exception as e:
                    print(f"   ❌ Erreur Cloudinary: {e}")
            else:
                print(f"   ⏭️  Skipped")

            # Rate limit Liquipedia (respectueux)
            await asyncio.sleep(2)

    db.close()
    print("\n✅ Terminé !")


if __name__ == "__main__":
    asyncio.run(update_pro_photos())