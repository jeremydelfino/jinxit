"""Lance le refresh des pools CoachDiff puis affiche le top par rôle."""
import sys
sys.path.insert(0, ".")

from services.team_pool_scraper import refresh_team_pools
from database import SessionLocal
from models.team_champion_pool import TeamChampionPool

LANES = ["TOP", "JUNGLE", "MID", "ADC", "SUPPORT"]

def main():
    print("⏳ Refresh des pools (Karmine Corp / G2 / T1)…")
    print("✅", refresh_team_pools(), "\n")

    db = SessionLocal()
    for code in ["KC", "G2", "T1"]:
        print(f"═══ {code} ═══")
        for lane in LANES:
            rows = (db.query(TeamChampionPool)
                    .filter(TeamChampionPool.team_code == code, TeamChampionPool.lane == lane)
                    .order_by(TeamChampionPool.weight.desc()).limit(4).all())
            top = ", ".join(f"{r.champion} {int(r.weight*100)}%" for r in rows) or "—"
            print(f"  {lane:8s} {top}")
        print()
    db.close()

if __name__ == "__main__":
    main()