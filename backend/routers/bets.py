from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
from database import get_db
from models.bet import Bet
from models.live_game import LiveGame
from models.pro_player import ProPlayer
from models.user import User
from models.bet_type import BetType
from models.transaction import Transaction
from deps import get_current_user
from services.live_odds_engine import FIXED_ODDS

router = APIRouter(prefix="/bets", tags=["bets"])

DDV = "14.24.1"

VALID_BET_TYPES = {
    "who_wins", "first_blood", "first_tower", "first_dragon", "first_baron",
    "game_duration_under25", "game_duration_25_35", "game_duration_over35",
    "player_positive_kda",
    "champion_kda_over25", "champion_kda_over5", "champion_kda_over10",
    "top_damage",
    "jungle_gap",
}

CHAMP_BET_TYPES = {
    "first_blood", "player_positive_kda",
    "champion_kda_over25", "champion_kda_over5", "champion_kda_over10",
    "top_damage",
}

# Types qui attendent "blue" ou "red" comme bet_value
SIDE_BET_TYPES = {"who_wins", "first_tower", "first_dragon", "first_baron"}

# Types sans bet_value côté (on valide juste que c'est non-vide)
DURATION_BET_TYPES = {"game_duration_under25", "game_duration_25_35", "game_duration_over35"}


class PlaceBetSchema(BaseModel):
    live_game_id:  int
    bet_type_slug: str
    bet_value:     str
    amount:        int
    card_used_id:  int | None = None

    @validator("amount")
    def amount_must_be_positive(cls, v):
        if v < 1:       raise ValueError("Le montant doit être >= 1")
        if v > 100_000: raise ValueError("Le montant ne peut pas dépasser 100 000 coins")
        return v

    @validator("bet_type_slug")
    def valid_bet_type(cls, v):
        if v not in VALID_BET_TYPES:
            raise ValueError(f"Type de pari invalide : {v}")
        return v


@router.post("/place")
def place_bet(
    body: PlaceBetSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── Type actif en base ────────────────────────────────────
    bet_type = db.query(BetType).filter(
        BetType.slug      == body.bet_type_slug,
        BetType.is_active == True,
    ).first()
    if not bet_type:
        raise HTTPException(400, "Type de pari invalide ou inactif")

    # ── Game ──────────────────────────────────────────────────
    game = db.query(LiveGame).filter(LiveGame.id == body.live_game_id).first()
    if not game:
        raise HTTPException(404, "Partie introuvable")
    if game.status != "live":
        raise HTTPException(400, "Cette partie est terminée")

    # ── Validation bet_value selon le type ────────────────────
    all_players = (game.blue_team or []) + (game.red_team or [])
    champ_names = {p.get("championName", "") for p in all_players if p.get("championName")}

    if body.bet_type_slug in SIDE_BET_TYPES:
        if body.bet_value not in {"blue", "red"}:
            raise HTTPException(400, f"Valeur invalide pour {body.bet_type_slug} — attendu : blue ou red")

    elif body.bet_type_slug in CHAMP_BET_TYPES:
        if body.bet_value not in champ_names:
            raise HTTPException(400, f"Champion '{body.bet_value}' introuvable dans cette partie")

    elif body.bet_type_slug in DURATION_BET_TYPES:
        if not body.bet_value:
            raise HTTPException(400, "bet_value manquant")

    # ── Un seul pari par type par game ────────────────────────
    # On vérifie uniquement sur bet_type_slug (pas bet_value) pour les types
    # où une seule option est possible (durée, jungle_gap, etc.)
    # Pour les types "side" (who_wins, first_tower...) on bloque aussi
    # le même type même avec une valeur différente — un joueur ne peut pas
    # parier blue ET red sur who_wins dans la même game.
    existing = db.query(Bet).filter(
        Bet.user_id       == current_user.id,
        Bet.live_game_id  == body.live_game_id,
        Bet.bet_type_slug == body.bet_type_slug,
        Bet.status        == "pending",
    ).first()
    if existing:
        raise HTTPException(400, f"Tu as déjà un pari '{bet_type.label}' en cours sur cette partie")

    # ── Solde ─────────────────────────────────────────────────
    if current_user.coins < body.amount:
        raise HTTPException(400, "Coins insuffisants")

    # ── Récupération de la côte depuis odds_data ──────────────
    odds_data = game.odds_data or {}
    odds      = _resolve_odds(body.bet_type_slug, body.bet_value, odds_data)

    # ── Création du pari ──────────────────────────────────────
    current_user.coins -= body.amount

    bet = Bet(
        user_id       = current_user.id,
        live_game_id  = body.live_game_id,
        card_used_id  = body.card_used_id,
        bet_type_slug = body.bet_type_slug,
        bet_value     = body.bet_value,
        amount        = body.amount,
        odds          = odds,
        boost_applied = 0,
        status        = "pending",
    )
    db.add(bet)
    db.add(Transaction(
        user_id     = current_user.id,
        type        = "bet_placed",
        amount      = -body.amount,
        description = f"Pari placé sur {bet_type.label} — {body.bet_value} (×{odds})",
    ))

    db.commit()
    db.refresh(bet)

    return {
        "bet_id":         bet.id,
        "amount":         body.amount,
        "odds":           odds,
        "boost_applied":  0,
        "coins_restants": current_user.coins,
    }


def _resolve_odds(slug: str, value: str, odds_data: dict) -> float:
    """
    Récupère la côte depuis odds_data (calculée au démarrage de la game).
    Fallback sur FIXED_ODDS si absente.
    """
    try:
        if slug == "who_wins":
            return float(odds_data.get("who_wins", {}).get(value, 2.0))
        if slug == "first_tower":
            return float(odds_data.get("first_tower",  {}).get(value, FIXED_ODDS["first_tower"]))
        if slug == "first_dragon":
            return float(odds_data.get("first_dragon", {}).get(value, FIXED_ODDS["first_dragon"]))
        if slug == "first_baron":
            return float(odds_data.get("first_baron",  {}).get(value, FIXED_ODDS["first_baron"]))
        if slug == "jungle_gap":
            return float(odds_data.get("jungle_gap",   {}).get(value, 2.0))
        if slug == "first_blood":
            return float(odds_data.get("first_blood", FIXED_ODDS["first_blood"]))
        if slug in ("game_duration_under25", "game_duration_25_35", "game_duration_over35",
                    "player_positive_kda", "champion_kda_over25", "champion_kda_over5",
                    "champion_kda_over10", "top_damage"):
            return float(odds_data.get(slug, FIXED_ODDS.get(slug, 2.0)))
    except (TypeError, ValueError):
        pass
    return FIXED_ODDS.get(slug, 2.0)


def _find_player_in_game(game: LiveGame, bet_value: str, bet_type: str) -> dict | None:
    if bet_type == "who_wins":
        team = game.blue_team if bet_value == "blue" else game.red_team
        for p in (team or []):
            if p.get("pro"):
                return p
        return None
    if bet_type in CHAMP_BET_TYPES:
        for p in (game.blue_team or []) + (game.red_team or []):
            if p.get("championName") == bet_value:
                return p
    return None


@router.get("/my-bets")
def get_my_bets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bets = (
        db.query(Bet)
        .filter(Bet.user_id == current_user.id)
        .order_by(Bet.created_at.desc())
        .all()
    )

    game_ids = {b.live_game_id for b in bets if b.live_game_id}
    games    = {
        g.id: g for g in db.query(LiveGame).filter(LiveGame.id.in_(game_ids)).all()
    } if game_ids else {}

    all_puuids = set()
    for g in games.values():
        for p in (g.blue_team or []) + (g.red_team or []):
            if p.get("puuid"):
                all_puuids.add(p["puuid"])
    pros_by_puuid = {
        p.riot_puuid: p
        for p in db.query(ProPlayer).filter(ProPlayer.riot_puuid.in_(all_puuids)).all()
    } if all_puuids else {}

    result = []
    for b in bets:
        game = games.get(b.live_game_id)

        game_info = None
        if game:
            all_players = (game.blue_team or []) + (game.red_team or [])
            main_pro    = None
            for p in all_players:
                pro = pros_by_puuid.get(p.get("puuid", ""))
                if pro:
                    main_pro = pro
                    break

            champion_name = None
            player_name   = None
            player_puuid  = None
            player_region = main_pro.region if main_pro else "EUW"

            if b.bet_type_slug in CHAMP_BET_TYPES:
                champion_name = b.bet_value
                for p in all_players:
                    if p.get("championName") == champion_name:
                        player_name  = p.get("summonerName", "")
                        player_puuid = p.get("puuid", "")
                        pro = pros_by_puuid.get(player_puuid)
                        if pro:
                            player_name = pro.name
                        break

            elif b.bet_type_slug in SIDE_BET_TYPES:
                team = game.blue_team if b.bet_value == "blue" else game.red_team
                for p in (team or []):
                    pro = pros_by_puuid.get(p.get("puuid", ""))
                    if pro and not main_pro:
                        main_pro = pro
                    if not player_name:
                        player_name   = p.get("summonerName", "")
                        player_puuid  = p.get("puuid", "")
                        champion_name = p.get("championName", "")
                    if pro:
                        player_name   = pro.name
                        player_puuid  = pro.riot_puuid
                        champion_name = p.get("championName", "")
                        break

            game_info = {
                "id":         game.id,
                "status":     game.status,
                "queue":      game.queue_type,
                "blue_score": sum(p.get("kills", 0) for p in (game.blue_team or [])),
                "red_score":  sum(p.get("kills", 0) for p in (game.red_team  or [])),
                "pro": {
                    "id":           main_pro.id,
                    "name":         main_pro.name,
                    "team":         main_pro.team,
                    "role":         main_pro.role,
                    "photo_url":    main_pro.photo_url,
                    "region":       main_pro.region,
                    "accent_color": main_pro.accent_color,
                } if main_pro else None,
                "bet_player": {
                    "summoner_name": player_name,
                    "puuid":         player_puuid,
                    "champion_name": champion_name,
                    "champion_icon": f"https://ddragon.leagueoflegends.com/cdn/{DDV}/img/champion/{champion_name}.png" if champion_name else None,
                    "region":        player_region,
                    "side":          b.bet_value if b.bet_type_slug in SIDE_BET_TYPES else (
                        "blue" if any(p.get("championName") == champion_name for p in (game.blue_team or []))
                        else "red"
                    ),
                } if player_name or champion_name else None,
            }

        result.append({
            "id":            b.id,
            "live_game_id":  b.live_game_id,
            "game_status":   game.status if game else "ended",
            "bet_type":      b.bet_type_slug,
            "bet_value":     b.bet_value,
            "amount":        b.amount,
            "odds":          b.odds,
            "boost_applied": b.boost_applied,
            "status":        b.status,
            "payout":        b.payout,
            "created_at":    b.created_at,
            "game":          game_info,
        })

    return result