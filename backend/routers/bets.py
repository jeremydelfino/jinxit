from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
from database import get_db
from models.bet import Bet
from models.live_game import LiveGame
from models.pro_player import ProPlayer
from models.player import SearchedPlayer
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

# Types qui attendent "blue" ou "red"
SIDE_BET_TYPES = {"who_wins", "first_tower", "first_dragon", "first_baron"}

# jungle_gap séparé : accepte "blue", "red" ou "none"
JUNGLE_GAP_TYPE = "jungle_gap"

# Types sans bet_value côté
DURATION_BET_TYPES = {"game_duration_under25", "game_duration_25_35", "game_duration_over35"}


class PlaceBetSchema(BaseModel):
    live_game_id:  int
    bet_type_slug: str
    bet_value:     str
    amount:        int
    card_used_id:  int | None = None
    slip_id:       str | None = None

    @validator("amount")
    def amount_valid(cls, v):
        if v < 10:
            raise ValueError("Mise minimum 10 coins")
        if v > 100_000:
            raise ValueError("Mise maximum 100 000 coins")
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

    elif body.bet_type_slug == JUNGLE_GAP_TYPE:
        if body.bet_value not in {"blue", "red", "none"}:
            raise HTTPException(400, "Valeur invalide pour jungle_gap — attendu : blue, red ou none")

    elif body.bet_type_slug in CHAMP_BET_TYPES:
        if body.bet_value not in champ_names:
            raise HTTPException(400, f"Champion '{body.bet_value}' introuvable dans cette partie")

    elif body.bet_type_slug in DURATION_BET_TYPES:
        if not body.bet_value:
            raise HTTPException(400, "bet_value manquant")

    # ── Un seul pari par type par game ────────────────────────
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
        slip_id       = body.slip_id,
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
            return float(odds_data.get("first_tower",  {}).get(value, FIXED_ODDS.get("first_tower",  1.8)))
        if slug == "first_dragon":
            return float(odds_data.get("first_dragon", {}).get(value, FIXED_ODDS.get("first_dragon", 1.8)))
        if slug == "first_baron":
            return float(odds_data.get("first_baron",  {}).get(value, FIXED_ODDS.get("first_baron",  1.8)))
        if slug == "jungle_gap":
            return float(odds_data.get("jungle_gap",   {}).get(value, 2.0))
        if slug == "first_blood":
            return float(odds_data.get("first_blood", FIXED_ODDS.get("first_blood", 1.8)))
        if slug in DURATION_BET_TYPES | {
            "player_positive_kda", "champion_kda_over25",
            "champion_kda_over5", "champion_kda_over10", "top_damage",
        }:
            return float(odds_data.get(slug, FIXED_ODDS.get(slug, 2.0)))
    except (TypeError, ValueError):
        pass
    return FIXED_ODDS.get(slug, 2.0)


def _pick_player_from_team(
    team: list,
    pros_by_puuid: dict,
) -> tuple[str, str, str, str | None, object]:
    """
    Parcourt une liste de joueurs, retourne :
    (player_name, player_puuid, champion_name, tag_line, pro_obj)
    Priorité aux pros, fallback sur le premier joueur lambda trouvé.
    """
    player_name   = ""
    player_puuid  = ""
    champion_name = ""
    found_pro     = None

    for p in (team or []):
        puuid = p.get("puuid", "")
        pro   = pros_by_puuid.get(puuid)
        if not player_name:
            player_name   = pro.name if pro else p.get("summonerName", "")
            player_puuid  = pro.riot_puuid if pro else puuid
            champion_name = p.get("championName", "")
        if pro:
            player_name   = pro.name
            player_puuid  = pro.riot_puuid
            champion_name = p.get("championName", "")
            found_pro     = pro
            break

    return player_name, player_puuid, champion_name, found_pro


def _get_tag_line(player_puuid: str, pros_by_puuid: dict, db: Session) -> str | None:
    """
    Récupère le tag_line d'un joueur :
    - Pour un pro : pas de tag_line Riot pertinent, on retourne None
    - Pour un lambda : cherche dans SearchedPlayer via le puuid
    """
    if pros_by_puuid.get(player_puuid):
        return None  # pro : la navigation se fait via pro.name sans tag
    if not player_puuid:
        return None
    searched = db.query(SearchedPlayer).filter(
        SearchedPlayer.riot_puuid == player_puuid
    ).first()
    return searched.tag_line if searched else None


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
        g.id: g
        for g in db.query(LiveGame).filter(LiveGame.id.in_(game_ids)).all()
    } if game_ids else {}

    # ── Collecte tous les puuids pour lookup pros + SearchedPlayers ──
    all_puuids = set()
    for g in games.values():
        for p in (g.blue_team or []) + (g.red_team or []):
            if p.get("puuid"):
                all_puuids.add(p["puuid"])

    pros_by_puuid = {
        p.riot_puuid: p
        for p in db.query(ProPlayer).filter(ProPlayer.riot_puuid.in_(all_puuids)).all()
    } if all_puuids else {}

    # Lookup SearchedPlayer pour récupérer les tag_lines des joueurs lambda
    searched_by_puuid = {
        s.riot_puuid: s
        for s in db.query(SearchedPlayer).filter(SearchedPlayer.riot_puuid.in_(all_puuids)).all()
    } if all_puuids else {}

    result = []
    for b in bets:
        game = games.get(b.live_game_id)

        game_info = None
        if game:
            all_players = (game.blue_team or []) + (game.red_team or [])

            # ── Pro principal de la game ──────────────────────
            main_pro = None
            for p in all_players:
                pro = pros_by_puuid.get(p.get("puuid", ""))
                if pro:
                    main_pro = pro
                    break

            player_region = main_pro.region if main_pro else "EUW"
            champion_name = None
            player_name   = None
            player_puuid  = None
            found_pro     = None

            # ── Résolution du joueur de contexte selon le type ──
            if b.bet_type_slug in CHAMP_BET_TYPES:
                champion_name = b.bet_value
                for p in all_players:
                    if p.get("championName") == champion_name:
                        player_puuid = p.get("puuid", "")
                        pro          = pros_by_puuid.get(player_puuid)
                        player_name  = pro.name if pro else p.get("summonerName", "")
                        found_pro    = pro
                        if pro and not main_pro:
                            main_pro = pro
                        break

            elif b.bet_type_slug in SIDE_BET_TYPES:
                team = game.blue_team if b.bet_value == "blue" else game.red_team
                player_name, player_puuid, champion_name, found_pro = _pick_player_from_team(
                    team, pros_by_puuid
                )
                if found_pro and not main_pro:
                    main_pro = found_pro

            elif b.bet_type_slug == JUNGLE_GAP_TYPE:
                if b.bet_value in ("blue", "red"):
                    team = game.blue_team if b.bet_value == "blue" else game.red_team
                else:
                    team = all_players
                player_name, player_puuid, champion_name, found_pro = _pick_player_from_team(
                    team, pros_by_puuid
                )
                if found_pro and not main_pro:
                    main_pro = found_pro

            elif b.bet_type_slug in DURATION_BET_TYPES:
                player_name, player_puuid, champion_name, found_pro = _pick_player_from_team(
                    all_players, pros_by_puuid
                )
                if found_pro and not main_pro:
                    main_pro = found_pro

            else:
                player_name, player_puuid, champion_name, found_pro = _pick_player_from_team(
                    all_players, pros_by_puuid
                )

            # ── tag_line : depuis SearchedPlayer pour les lambdas ──
            tag_line = None
            if not found_pro and player_puuid:
                searched = searched_by_puuid.get(player_puuid)
                if searched:
                    tag_line     = searched.tag_line
                    player_name  = player_name or searched.summoner_name
                    player_region = searched.region

            # ── Side du joueur de contexte ────────────────────
            bet_player_side = None
            if b.bet_type_slug in SIDE_BET_TYPES or b.bet_type_slug == JUNGLE_GAP_TYPE:
                bet_player_side = b.bet_value
            elif champion_name:
                in_blue = any(p.get("championName") == champion_name for p in (game.blue_team or []))
                bet_player_side = "blue" if in_blue else "red"

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
                    "champion_icon": (
                        f"https://ddragon.leagueoflegends.com/cdn/{DDV}/img/champion/{champion_name}.png"
                        if champion_name else None
                    ),
                    "region":        player_region,
                    "tag_line":      tag_line,
                    "side":          bet_player_side,
                } if player_name or champion_name else None,
            }

        result.append({
            "id":            b.id,
            "live_game_id":  b.live_game_id,
            "slip_id":       b.slip_id,
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