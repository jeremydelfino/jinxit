from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.live_game import LiveGame
from models.bet import Bet
from models.pro_player import ProPlayer
from services.game_poller import poll_pro_games, resolve_bets_for_game
import asyncio

router = APIRouter(prefix="/games", tags=["games"])

QUEUE_NAMES = {
    "420": "Ranked Solo",
    "440": "Ranked Flex",
    "400": "Normal",
    "450": "ARAM",
    "":   "Custom",
}


def enrich_team(team: list, pro_map: dict) -> list:
    result = []
    for p in team:
        puuid = p.get("puuid", "")
        pro = pro_map.get(puuid)
        result.append({
            **p,
            "pro": {
                "id":           pro.id,
                "name":         pro.name,
                "team":         pro.team,
                "role":         pro.role,
                "photo_url":    pro.photo_url,
                "accent_color": pro.accent_color,
            } if pro else None,
        })
    return result


@router.post("/poll")
async def force_poll():
    await poll_pro_games()
    return {"status": "Poll lancé"}


# ✅ Endpoint pour forcer la résolution des paris d'une game terminée
# Utile pour résoudre les paris en attente sur une game déjà ended
# Usage: POST /games/resolve/42  (id PostgreSQL de la game)
@router.post("/resolve/{game_id}")
async def force_resolve(game_id: int, db: Session = Depends(get_db)):
    game = db.query(LiveGame).filter(LiveGame.id == game_id).first()
    if not game:
        raise HTTPException(404, "Partie introuvable")

    pending_count = db.query(Bet).filter(
        Bet.live_game_id == game_id,
        Bet.status == "pending"
    ).count()

    if pending_count == 0:
        return {"status": "Aucun pari pending à résoudre", "game_id": game_id}

    # Trouver la région
    all_p = (game.blue_team or []) + (game.red_team or [])
    puuids = [p.get("puuid") for p in all_p if p.get("puuid")]
    pro = db.query(ProPlayer).filter(ProPlayer.riot_puuid.in_(puuids)).first()
    region = pro.region if pro else "EUW"

    # S'assurer que la game est marquée ended
    if game.status == "live":
        game.status = "ended"
        db.commit()

    # Lancer la résolution en background
    asyncio.create_task(resolve_bets_for_game(game_id, game.riot_game_id, region))

    return {
        "status": "Résolution lancée en background",
        "game_id": game_id,
        "riot_game_id": game.riot_game_id,
        "pending_bets": pending_count,
        "region": region,
    }


@router.get("/live")
def get_live_games(db: Session = Depends(get_db)):
    games = (
        db.query(LiveGame)
        .filter(LiveGame.status == "live")
        .order_by(LiveGame.fetched_at.desc())
        .all()
    )

    result = []
    seen = set()
    for game in games:
        if game.riot_game_id in seen:
            continue
        seen.add(game.riot_game_id)

        all_puuids = [p.get("puuid") for p in (game.blue_team + game.red_team) if p.get("puuid")]
        pro = db.query(ProPlayer).filter(
            ProPlayer.riot_puuid.in_(all_puuids),
            ProPlayer.is_active == True,
        ).first()

        result.append({
            "id":               game.id,
            "riot_game_id":     game.riot_game_id,
            "queue":            QUEUE_NAMES.get(game.queue_type, game.queue_type),
            "duration_seconds": game.duration_seconds,
            "status":           game.status,
            "blue_team":        game.blue_team,
            "red_team":         game.red_team,
            "pro": {
                "id":            pro.id,
                "name":          pro.name,
                "team":          pro.team,
                "role":          pro.role,
                "photo_url":     pro.photo_url,
                "team_logo_url": pro.team_logo_url,
                "accent_color":  pro.accent_color,
            } if pro else None,
            "fetched_at": game.fetched_at,
        })

    return result[:12]


@router.get("/{game_id}")
def get_game(game_id: str, db: Session = Depends(get_db)):
    game = None
    if game_id.isdigit() and len(game_id) <= 10:
        game = db.query(LiveGame).filter(LiveGame.id == int(game_id)).first()
    if not game:
        game = db.query(LiveGame).filter(LiveGame.riot_game_id == game_id).first()
    if not game:
        raise HTTPException(404, "Partie introuvable")

    all_puuids = [p.get("puuid") for p in (game.blue_team + game.red_team) if p.get("puuid")]
    pros_in_game = db.query(ProPlayer).filter(
        ProPlayer.riot_puuid.in_(all_puuids),
        ProPlayer.is_active == True,
    ).all()
    pro_map  = {p.riot_puuid: p for p in pros_in_game}
    main_pro = pros_in_game[0] if pros_in_game else None

    return {
        "id":               game.id,
        "riot_game_id":     game.riot_game_id,
        "queue":            QUEUE_NAMES.get(game.queue_type, game.queue_type),
        "duration_seconds": game.duration_seconds,
        "status":           game.status,
        "blue_team":        enrich_team(game.blue_team, pro_map),
        "red_team":         enrich_team(game.red_team, pro_map),
        "pro": {
            "id":            main_pro.id,
            "name":          main_pro.name,
            "team":          main_pro.team,
            "role":          main_pro.role,
            "photo_url":     main_pro.photo_url,
            "team_logo_url": main_pro.team_logo_url,
            "accent_color":  main_pro.accent_color,
        } if main_pro else None,
        "fetched_at": game.fetched_at,
    }