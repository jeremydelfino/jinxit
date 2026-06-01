import sys, os, asyncio
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal
from services.esports_sync import sync_team, TEAM_SLUGS_BY_REGION

async def main():
    db = SessionLocal()
    total = 0
    for slug in TEAM_SLUGS_BY_REGION["LFL"]:
        try:
            n = await sync_team(slug, "lfl", db)   # region en minuscule = cohérent avec l'existant
            print(f"  ✅ {slug}: {n} joueurs")
            total += n
        except Exception as e:
            print(f"  ⚠️ {slug}: {e}")
    db.commit()        # au cas où sync_team ne commit pas lui-même
    db.close()
    print(f"\n🎮 LFL sync terminé — {total} joueurs")

if __name__ == "__main__":
    asyncio.run(main())