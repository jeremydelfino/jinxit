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

router = APIRouter(prefix="/bets", tags=["bets"])

VALID_BET_TYPES  = {"who_wins", "first_blood"}
VALID_WIN_VALUES = {"blue", "red"}
DDV = "14.24.1"


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
    bet_type = db.query(BetType).filter(
        BetType.slug == body.bet_type_slug,
        BetType.is_active == True,
    ).first()
    if not bet_type:
        raise HTTPException(400, "Type de pari invalide ou inactif")

    if body.bet_type_slug == "who_wins" and body.bet_value not in VALID_WIN_VALUES:
        raise HTTPException(400, "Valeur invalide pour who_wins (blue ou red)")

    game = db.query(LiveGame).filter(LiveGame.id == body.live_game_id).first()
    if not game:
        raise HTTPException(404, "Partie introuvable")
    if game.status != "live":
        raise HTTPException(400, "Cette partie est terminée")

    existing = db.query(Bet).filter(
        Bet.user_id      == current_user.id,
        Bet.live_game_id == body.live_game_id,
        Bet.bet_type_slug == body.bet_type_slug,
        Bet.status       == "pending",
    ).first()
    if existing:
        raise HTTPException(400, "Tu as déjà un pari en cours sur ce type pour cette partie")

    if current_user.coins < body.amount:
        raise HTTPException(400, "Coins insuffisants")

    boost = 0
    current_user.coins -= body.amount

    bet = Bet(
        user_id=current_user.id,
        live_game_id=body.live_game_id,
        card_used_id=body.card_used_id,
        bet_type_slug=body.bet_type_slug,
        bet_value=body.bet_value,
        amount=body.amount,
        boost_applied=boost,
        status="pending",
    )
    db.add(bet)

    db.add(Transaction(
        user_id=current_user.id,
        type="bet_placed",
        amount=-body.amount,
        description=f"Pari placé sur {bet_type.label} — {body.bet_value}",
    ))

    db.commit()
    db.refresh(bet)

    return {
        "bet_id":         bet.id,
        "amount":         body.amount,
        "boost_applied":  boost,
        "coins_restants": current_user.coins,
    }


def _find_player_in_game(game: LiveGame, bet_value: str, bet_type: str) -> dict | None:
    """Trouve le joueur/champion concerné par le pari dans la game."""
    if bet_type == "who_wins":
        # Renvoie le pro de l'équipe pariée s'il existe
        team = game.blue_team if bet_value == "blue" else game.red_team
        for p in (team or []):
            if p.get("pro"):
                return p
        return None

    if bet_type == "first_blood":
        # bet_value = nom du champion
        champ_name = bet_value
        for p in (game.blue_team or []) + (game.red_team or []):
            if p.get("championName") == champ_name:
                return p
        return None

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

    # Charger toutes les games en une requête
    game_ids = {b.live_game_id for b in bets if b.live_game_id}
    games = {
        g.id: g for g in db.query(LiveGame).filter(LiveGame.id.in_(game_ids)).all()
    } if game_ids else {}

    # Charger les pros liés aux games
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

        # ── Infos game de base ────────────────────────────────────────────────
        game_info = None
        if game:
            # Trouver le pro principal de la game
            all_players = (game.blue_team or []) + (game.red_team or [])
            main_pro = None
            for p in all_players:
                pro = pros_by_puuid.get(p.get("puuid", ""))
                if pro:
                    main_pro = pro
                    break

            # Champion concerné par le pari
            champion_name = None
            player_name   = None
            player_puuid  = None
            player_region = main_pro.region if main_pro else "EUW"

            if b.bet_type_slug == "first_blood":
                # Le champ bet_value = nom du champion
                champion_name = b.bet_value
                for p in all_players:
                    if p.get("championName") == champion_name:
                        player_name  = p.get("summonerName", "")
                        player_puuid = p.get("puuid", "")
                        # Chercher si c'est un pro
                        pro = pros_by_puuid.get(player_puuid)
                        if pro:
                            player_name = pro.name
                        break

            elif b.bet_type_slug == "who_wins":
                team = game.blue_team if b.bet_value == "blue" else game.red_team
                for p in (team or []):
                    pro = pros_by_puuid.get(p.get("puuid", ""))
                    if pro and not main_pro:
                        main_pro = pro
                    if not player_name:
                        player_name  = p.get("summonerName", "")
                        player_puuid = p.get("puuid", "")
                        champion_name = p.get("championName", "")
                    if pro:
                        player_name   = pro.name
                        player_puuid  = pro.riot_puuid
                        champion_name = p.get("championName", "")
                        break

            game_info = {
                "id":           game.id,
                "status":       game.status,
                "queue":        game.queue_type,
                "blue_score":   sum(p.get("kills", 0) for p in (game.blue_team or [])),
                "red_score":    sum(p.get("kills", 0) for p in (game.red_team  or [])),
                # Pro principal de la game
                "pro": {
                    "id":        main_pro.id,
                    "name":      main_pro.name,
                    "team":      main_pro.team,
                    "role":      main_pro.role,
                    "photo_url": main_pro.photo_url,
                    "region":    main_pro.region,
                    "accent_color": main_pro.accent_color,
                } if main_pro else None,
                # Joueur/champion directement concerné par le pari
                "bet_player": {
                    "summoner_name": player_name,
                    "puuid":         player_puuid,
                    "champion_name": champion_name,
                    "champion_icon": f"https://ddragon.leagueoflegends.com/cdn/{DDV}/img/champion/{champion_name}.png" if champion_name else None,
                    "region":        player_region,
                    "side":          b.bet_value if b.bet_type_slug == "who_wins" else (
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
            "boost_applied": b.boost_applied,
            "status":        b.status,
            "payout":        b.payout,
            "created_at":    b.created_at,
            "game":          game_info,
        })

    return result