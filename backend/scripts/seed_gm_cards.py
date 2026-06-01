"""
scripts/seed_gm_cards.py
Crée une carte BASE pour chaque joueur LFL (esports_players.region='LFL'),
stats par défaut à 70 (à remplir via l'admin), + un pack LFL de base pour tester.
Idempotent (skip si la carte BASE existe déjà).
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.gm_player_card import GmPlayerCard
from models.gm_pack_type import GmPackType
from models.esports_player import EsportsPlayer
from services.gm_ovr import compute_ovr, salary_from_ovr
from sqlalchemy import func   # en haut avec les autres imports



ROLE_MAP = {
    "top": "TOP", "jungle": "JUNGLE", "jng": "JUNGLE", "mid": "MID", "middle": "MID",
    "bottom": "ADC", "adc": "ADC", "bot": "ADC", "support": "SUPPORT", "utility": "SUPPORT",
}


def norm_role(r): return ROLE_MAP.get((r or "").lower().strip(), "MID")


def seed():
    db = SessionLocal()
    added = skipped = 0

    players = db.query(EsportsPlayer).filter(
        func.lower(EsportsPlayer.region) == "lfl", EsportsPlayer.is_active == True
    ).all()
    print(f"🎯 {len(players)} joueurs LFL trouvés")

    for ep in players:
        exists = db.query(GmPlayerCard).filter(
            GmPlayerCard.esports_player_id == ep.id, GmPlayerCard.variant == "BASE"
        ).first()
        if exists:
            skipped += 1
            continue

        role = norm_role(ep.role)
        defaults = dict(laning=70, teamfight=70, vision=70, mechanics=70, stress=70, clutch=70)
        ovr = compute_ovr(role, **defaults)

        db.add(GmPlayerCard(
            esports_player_id=ep.id, variant="BASE", role=role, nationality=None,
            ego=3, traits=[], ovr=ovr, base_salary=salary_from_ovr(ovr), **defaults,
        ))
        added += 1
        print(f"  ✅ {ep.summoner_name} ({ep.team_code} · {role}) ovr={ovr}")

    # Pack LFL de base (poids 100% sur 70-74 puisque tout est à 70 au départ)
    if not db.query(GmPackType).filter(GmPackType.name == "Pack LFL").first():
        db.add(GmPackType(
            name="Pack LFL", description="Un joueur LFL au hasard.",
            price_budget=1000, w_70_74=100, w_75_84=0, w_85_89=0, w_90_99=0,
            league_filter="lfl",
        ))
        print("  📦 Pack LFL créé")

def seed_lec():
    # Idem pour LEC, à faire après avoir seed les joueurs LEC
    db = SessionLocal()
    added = skipped = 0

    players = db.query(EsportsPlayer).filter(
        func.lower(EsportsPlayer.region) == "lec", EsportsPlayer.is_active == True
    ).all()


    print(f"🎯 {len(players)} joueurs LEC trouvés")

    for ep in players:
        exists = db.query(GmPlayerCard).filter(
            GmPlayerCard.esports_player_id == ep.id, GmPlayerCard.variant == "BASE"
        ).first()
        if exists:
            skipped += 1
            continue

        role = norm_role(ep.role)
        defaults = dict(laning=70, teamfight=70, vision=70, mechanics=70, stress=70, clutch=70)
        ovr = compute_ovr(role, **defaults)

        db.add(GmPlayerCard(
            esports_player_id=ep.id, variant="BASE", role=role, nationality=None,
            ego=3, traits=[], ovr=ovr, base_salary=salary_from_ovr(ovr), **defaults,
        ))
        added += 1
        print(f"  ✅ {ep.summoner_name} ({ep.team_code} · {role}) ovr={ovr}")

    # Pack LEC de base (poids 100% sur 70-74 puisque tout est à 70 au départ)
    if not db.query(GmPackType).filter(GmPackType.name == "Pack LEC").first():
        db.add(GmPackType(
            name="Pack LEC", description="Un joueur LEC au hasard.",
            price_budget=1000, w_70_74=0, w_75_84=70, w_85_89=25, w_90_99=5,
            league_filter="lec",
        ))
        print("  📦 Pack LEC créé")

    db.commit()
    db.close()
    print(f"\n🎮 Seed terminé — {added} cartes ajoutées, {skipped} ignorées")


if __name__ == "__main__":
    seed()
    seed_lec()