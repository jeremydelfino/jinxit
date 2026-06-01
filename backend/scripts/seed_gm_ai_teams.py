"""
scripts/gm/seed_gm_ai_teams.py
Adversaires Myceo = vraies équipes LFL (esports_teams, region='lfl') : nom + logo réels.
Toutes en tier de draft 'LFL' (bot faible < KC). base_strength étalée 74→58
pour différencier le haut/bas de tableau (sim IA vs IA + modulation de draft en 2b).
Idempotent (upsert par name). Cap à MAX_AI.
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func
from database import SessionLocal
from models.esports_team import EsportsTeam
from models.gm_ai_team   import GmAiTeam

MAX_AI = 9


def seed():
    db = SessionLocal()
    added = updated = 0

    teams = db.query(EsportsTeam).filter(
        func.lower(EsportsTeam.region) == "lfl"
    ).order_by(EsportsTeam.name.asc()).limit(MAX_AI).all()

    print(f"🎯 {len(teams)} équipes LFL trouvées (cap {MAX_AI})")
    if not teams:
        print("⚠️  Aucune équipe LFL dans esports_teams — lance d'abord ta sync LFL.")
        db.close(); return

    for i, et in enumerate(teams):
        strength = max(58, 74 - i * 2)   # 74, 72, ... 58
        existing = db.query(GmAiTeam).filter(GmAiTeam.name == et.name).first()
        if existing:
            existing.logo_url      = et.logo_url
            existing.region        = "LFL"
            existing.bot_tier      = "LFL"
            existing.base_strength = strength
            existing.seed          = i
            existing.is_active     = True
            updated += 1
        else:
            db.add(GmAiTeam(
                name=et.name, logo_url=et.logo_url, region="LFL",
                bot_tier="LFL", base_strength=strength, seed=i, is_active=True,
            ))
            added += 1
        print(f"  ✅ {et.name:<24} tier=LFL str={strength} seed={i}")

    db.commit()
    db.close()
    print(f"\n🏟️  Seed IA terminé — {added} ajoutées, {updated} mises à jour")


if __name__ == "__main__":
    seed()