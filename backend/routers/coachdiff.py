"""
routers/coachdiff.py

Endpoints CoachDiff (1v1 vs bot, draft tournoi).

Flux :
  POST /coachdiff/start          → crée une game, débite 5 coins, retourne l'état
  GET  /coachdiff/game/{id}      → état actuel
  POST /coachdiff/action         → user joue un pick/ban
  POST /coachdiff/bot-turn       → fait jouer le bot UN tour (frontend pilote)
  POST /coachdiff/assign-roles   → user assigne ses rôles → bot assigne → score → résolu
  GET  /coachdiff/history        → historique des games du user
"""
from __future__ import annotations
import logging
from datetime import datetime
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user
from models.user            import User
from models.transaction     import Transaction
from models.coachdiff_game  import CoachDiffGame
from services.coachdiff_state import (
    init_state, current_turn, apply_action, apply_role_assignment,
    is_draft_done, is_role_assignment_complete, picks_with_lanes, LANES,
)
from services.coachdiff_bot   import bot_play_turn, bot_assign_roles
from services.coachdiff_scorer import compare_drafts, TeamPick

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/coachdiff", tags=["coachdiff"])

# ─── Économie ─────────────────────────────────────────────────
ENTRY_COST = 5
WIN_PAYOUT = 10   # gain net = +5 (10 versés - 5 mise)


# ─── Schémas ──────────────────────────────────────────────────
class ActionPayload(BaseModel):
    game_id:  int
    champion: str = Field(..., min_length=1, max_length=64)


class BotTurnPayload(BaseModel):
    game_id: int


class AssignRolesPayload(BaseModel):
    game_id:  int
    role_map: dict[str, str]   # {"TOP": "Aatrox", "JUNGLE": "Viego", ...}

class StartPayload(BaseModel):
    opponent: str | None = None

VALID_OPPONENTS = {"KC", "G2", "T1"}

# ─── Helpers ──────────────────────────────────────────────────
def _serialize_game(g: CoachDiffGame) -> dict:
    state = g.draft_state or {}
    turn = current_turn(state) if state else None
    return {
        "id":               g.id,
        "status":           g.status,
        "user_side":        g.user_side,
        "bot_side":         g.bot_side,          
        "draft_state":      state,
        "current_turn":     turn,
        "user_breakdown":   g.user_breakdown,
        "bot_breakdown":    g.bot_breakdown,
        "winner":           g.winner,
        "user_score":       g.user_score,
        "bot_score":        g.bot_score,
        "created_at":       g.created_at.isoformat() if g.created_at else None,
        "finished_at":      g.finished_at.isoformat() if g.finished_at else None,
    }


def _get_user_game(db: Session, game_id: int, user: User) -> CoachDiffGame:
    g = db.query(CoachDiffGame).filter(CoachDiffGame.id == game_id).first()
    if not g:
        raise HTTPException(404, "Game introuvable")
    if g.user_id != user.id:
        raise HTTPException(403, "Pas votre game")
    return g


# ─── POST /start ──────────────────────────────────────────────
@router.post("/start")
def start_game(
    payload: StartPayload = StartPayload(),
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    opponent = (payload.opponent or "G2")
    if opponent not in VALID_OPPONENTS:
        opponent = "G2"
    # Vérifier qu'il n'a pas déjà une partie en cours
    existing = db.query(CoachDiffGame).filter(
        CoachDiffGame.user_id == user.id,
        CoachDiffGame.status  == "in_progress",
    ).first()
    if existing:
        raise HTTPException(400, f"Tu as déjà une partie en cours (id={existing.id})")

    if user.coins < ENTRY_COST:
        raise HTTPException(400, f"Solde insuffisant ({user.coins}/{ENTRY_COST})")

    user.coins -= ENTRY_COST
    db.add(Transaction(
        user_id     = user.id,
        type        = "coachdiff_entry",
        amount      = -ENTRY_COST,
        description = "Mise CoachDiff",
    ))

    user_side = random.choice(["BLUE", "RED"])
    bot_side  = "RED" if user_side == "BLUE" else "BLUE"
    state = init_state(user_side)

    game = CoachDiffGame(
        user_id      = user.id,
        status       = "in_progress",
        user_side    = user_side,
        bot_side     = bot_side,
        opponent     = opponent,
        draft_state  = state,
        created_at   = datetime.utcnow(),
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    logger.info(f"[coachdiff] start game {game.id} user={user.id} side={user_side}")
    return _serialize_game(game)

# ─── GET /game/{id} ───────────────────────────────────────────
@router.get("/game/{game_id}")
def get_game(
    game_id: int,
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    g = _get_user_game(db, game_id, user)
    return _serialize_game(g)


# ─── POST /action (user) ──────────────────────────────────────
@router.post("/action")
def user_action(
    payload: ActionPayload,
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    g = _get_user_game(db, payload.game_id, user)
    if g.status != "in_progress":
        raise HTTPException(400, f"Game {g.status}")

    state = dict(g.draft_state or {})
    if is_draft_done(state):
        raise HTTPException(400, "Draft déjà terminée")

    turn = current_turn(state)
    if turn["actor"] != "USER":
        raise HTTPException(400, "Pas votre tour (tour du bot)")

    try:
        apply_action(state, payload.champion, expected_actor="USER")
    except ValueError as e:
        raise HTTPException(400, str(e))

    g.draft_state = state
    # SQLAlchemy + JSONB : il faut explicitement marquer comme dirty parfois
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(g, "draft_state")
    db.commit()
    db.refresh(g)
    return _serialize_game(g)


# ─── POST /bot-turn ───────────────────────────────────────────
@router.post("/bot-turn")
def bot_turn(
    payload: BotTurnPayload,
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    g = _get_user_game(db, payload.game_id, user)
    if g.status != "in_progress":
        raise HTTPException(400, f"Game {g.status}")

    state = dict(g.draft_state or {})
    if is_draft_done(state):
        raise HTTPException(400, "Draft déjà terminée")

    turn = current_turn(state)
    if turn["actor"] != "BOT":
        raise HTTPException(400, "Pas le tour du bot")

    state, choice = bot_play_turn(db, state, g.opponent)
    logger.info(f"[coachdiff] game {g.id} bot {turn['action']} → {choice}")

    g.draft_state = state
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(g, "draft_state")
    db.commit()
    db.refresh(g)
    return _serialize_game(g)


# ─── POST /assign-roles ───────────────────────────────────────
@router.post("/assign-roles")
def assign_roles(
    payload: AssignRolesPayload,
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    g = _get_user_game(db, payload.game_id, user)
    if g.status != "in_progress":
        raise HTTPException(400, f"Game {g.status}")

    state = dict(g.draft_state or {})
    if not is_draft_done(state):
        raise HTTPException(400, "Draft pas encore terminée")

    user_side = state["user_side"]
    bot_side  = state["bot_side"]

    # 1) Assigner les rôles user
    try:
        apply_role_assignment(state, user_side, payload.role_map)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # 2) Assigner les rôles bot (auto, greedy par pickrate Pro)
    bot_picks = state["red" if bot_side == "RED" else "blue"]["picks"]
    bot_lane_map = bot_assign_roles(db, bot_picks, plan=state.get("bot_plan"))
    apply_role_assignment(state, bot_side, bot_lane_map)

    # 3) Scorer
    blue_picks = [TeamPick(champion=c, lane=l) for l, c in state["blue"]["lanes"].items()]
    red_picks  = [TeamPick(champion=c, lane=l) for l, c in state["red"]["lanes"].items()]
    result = compare_drafts(db, blue_picks, red_picks)

    user_breakdown = result["blue"] if user_side == "BLUE" else result["red"]
    bot_breakdown  = result["red"]  if user_side == "BLUE" else result["blue"]

    if result["winner"] == "DRAW":
        winner = "DRAW"
    elif result["winner"] == user_side:
        winner = "USER"
    else:
        winner = "BOT"

    # 4) Payout
    payout = 0
    tx_type = None
    tx_desc = None
    if winner == "USER":
        payout = WIN_PAYOUT
        tx_type = "coachdiff_win"
        tx_desc = f"CoachDiff gagné (game {g.id})"
    elif winner == "DRAW":
        payout = ENTRY_COST  # remboursement
        tx_type = "coachdiff_draw"
        tx_desc = f"CoachDiff égalité (game {g.id})"

    if payout > 0:
        user.coins += payout
        db.add(Transaction(
            user_id     = user.id,
            type        = tx_type,
            amount      = payout,
            description = tx_desc,
        ))

    # 5) Persister
    state["phase"] = "FINISHED"
    g.draft_state    = state
    g.status         = "finished"
    g.winner         = winner
    g.user_score     = user_breakdown["total"]
    g.bot_score      = bot_breakdown["total"]
    g.user_breakdown = user_breakdown
    g.bot_breakdown  = bot_breakdown
    g.finished_at    = datetime.utcnow()

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(g, "draft_state")
    flag_modified(g, "user_breakdown")
    flag_modified(g, "bot_breakdown")
    db.commit()
    db.refresh(g)

    logger.info(
        f"[coachdiff] game {g.id} finished — "
        f"winner={winner} user={g.user_score:.1f} bot={g.bot_score:.1f} payout={payout}"
    )
    return _serialize_game(g)


# ─── GET /history ─────────────────────────────────────────────
@router.get("/history")
def history(
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    games = (
        db.query(CoachDiffGame)
        .filter(CoachDiffGame.user_id == user.id)
        .order_by(CoachDiffGame.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [
        {
            "id":          g.id,
            "status":      g.status,
            "user_side":   g.user_side,
            "winner":      g.winner,
            "user_score":  g.user_score,
            "bot_score":   g.bot_score,
            "created_at":  g.created_at.isoformat() if g.created_at else None,
            "finished_at": g.finished_at.isoformat() if g.finished_at else None,
        }
        for g in games
    ]


# ─── POST /admin/refresh-pro-stats (existant) ─────────────────
@router.post("/admin/refresh-pro-stats", include_in_schema=False)
def admin_refresh_pro_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not getattr(user, "is_admin", False):
        raise HTTPException(403, "Admin only")
    from services.leaguepedia_scraper import refresh_pro_stats
    return refresh_pro_stats()