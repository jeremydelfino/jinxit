"""
routers/gm.py — Mode gestion e-sport (game mode). Tranche 1 : franchise, packs, roster, vente.
"""
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from deps import get_current_user, get_admin_user
from models.user import User
from models.gm_team import GmTeam
from models.gm_player_card import GmPlayerCard
from models.gm_contract import GmContract
from models.gm_pack_type import GmPackType
from models.esports_team import EsportsTeam
from models.esports_player import EsportsPlayer
from models.gm_season   import GmSeason
from models.gm_standing import GmStanding
from models.gm_match    import GmMatch
from models.gm_ai_team  import GmAiTeam
from services.gm_season import create_season

from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError
from models.gm_game import GmGame
from services.gm_resolve import team_metrics, compute_pwin, reward_for, sim_ai_series
from services.coachdiff_state  import (init_state, current_turn, apply_action,
                                       apply_role_assignment, is_draft_done)
from services.coachdiff_bot    import bot_play_turn, bot_assign_roles
from services.coachdiff_scorer import compare_drafts, TeamPick
from services.gm_ovr import compute_ovr, salary_from_ovr, resale_value

router = APIRouter(prefix="/gm", tags=["gm"])

ROLES = ["TOP", "JUNGLE", "MID", "ADC", "SUPPORT"]
STARTING_BUDGET = 5000
OVR_BRACKETS = [(70, 74, "w_70_74"), (75, 84, "w_75_84"), (85, 89, "w_85_89"), (90, 99, "w_90_99")]
_BRAND_CACHE: dict = {}

def _team_brand(db, code):
    if not code:
        return None
    code = code.upper()
    if code not in _BRAND_CACHE:
        et = db.query(EsportsTeam).filter(EsportsTeam.code == code).first()
        _BRAND_CACHE[code] = {
            "logo":   et.logo_url if et else None,
            "accent": getattr(et, "accent_color", None) if et else None,
        }
    return _BRAND_CACHE[code]


# ─── Schemas ───────────────────────────────────────────────
class CreateTeamReq(BaseModel):
    name: str

class AdminCardUpdate(BaseModel):
    role:        Optional[str]  = None
    nationality: Optional[str]  = None
    laning:      Optional[int]  = None
    teamfight:   Optional[int]  = None
    vision:      Optional[int]  = None
    mechanics:   Optional[int]  = None
    stress:      Optional[int]  = None
    clutch:      Optional[int]  = None
    ego:         Optional[int]  = None
    traits:      Optional[list] = None
    photo_url:   Optional[str]  = None
    is_active:   Optional[bool] = None

class PackCreate(BaseModel):
    name:         str
    description:  Optional[str] = None
    image_url:    Optional[str] = None
    price_budget: int
    w_70_74: int = 0
    w_75_84: int = 0
    w_85_89: int = 0
    w_90_99: int = 0
    league_filter: Optional[str] = None
    role_filter:   Optional[str] = None

class ContractUpdate(BaseModel):
    is_starter: Optional[bool] = None
    role_slot:  Optional[str]  = None
    side:       Optional[str]  = None

class GmActionReq(BaseModel):
    champion: str

class GmAssignReq(BaseModel):
    role_map: dict   # {"TOP": champ, "JUNGLE": champ, ...}

# ─── Helpers de sérialisation ──────────────────────────────
def _identities(db: Session, cards):
    ids = [c.esports_player_id for c in cards if c.esports_player_id]
    rows = db.query(EsportsPlayer).filter(EsportsPlayer.id.in_(ids)).all() if ids else []
    return {r.id: r for r in rows}


def _serialize_card(card: GmPlayerCard, ep: Optional[EsportsPlayer], brand=None):
    return {
        "card_id":     card.id,
        "variant":     card.variant,
        "role":        card.role,
        "nationality": card.nationality,
        "ovr":         card.ovr,
        "ego":         card.ego,
        "traits":      card.traits,
        "base_salary": card.base_salary,
        "photo_url":  card.photo_url or ep.photo_url,
        "stats": {
            "laning":    card.laning,   "teamfight": card.teamfight,
            "vision":    card.vision,   "mechanics": card.mechanics,
            "stress":    card.stress,   "clutch":    card.clutch,
        },
        "player": ({
            "name":       ep.summoner_name,
            "photo_url":  ep.photo_url,
            "team_code":  ep.team_code,
            "team_name":  ep.team_name,
            "league":     ep.region,
            "team_logo":   (brand or {}).get("logo"),
            "team_accent": (brand or {}).get("accent"),
        } if ep else None),
    }


def _get_team(db, user) -> GmTeam:
    team = db.query(GmTeam).filter(GmTeam.owner_id == user.id).first()
    if not team:
        raise HTTPException(404, "Aucune franchise. Crée ta team d'abord.")
    return team


def _recompute_team_ovr(db, team):
    starters = db.query(GmContract).filter(
        GmContract.team_id == team.id, GmContract.is_starter == True
    ).all()
    if not starters:
        team.ovr_cached = 0
        return
    cards = db.query(GmPlayerCard).filter(
        GmPlayerCard.id.in_([c.card_id for c in starters])
    ).all()
    team.ovr_cached = round(sum(c.ovr for c in cards) / len(cards))


# ═══════════════════════════════════════════════════════════
# FRANCHISE
# ═══════════════════════════════════════════════════════════
@router.post("/team")
def create_team(body: CreateTeamReq, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.query(GmTeam).filter(GmTeam.owner_id == user.id).first():
        raise HTTPException(400, "Tu as déjà une franchise.")
    name = body.name.strip()
    if not (2 <= len(name) <= 60):
        raise HTTPException(400, "Nom entre 2 et 60 caractères.")

    team = GmTeam(owner_id=user.id, name=name, league="LFL", budget=STARTING_BUDGET, reputation=50)
    db.add(team)
    db.flush()  # team.id dispo

    # Start-5 : 1 carte LFL par rôle (région insensible à la casse)
    pool = (db.query(GmPlayerCard)
            .join(EsportsPlayer, GmPlayerCard.esports_player_id == EsportsPlayer.id)
            .filter(GmPlayerCard.is_active == True, func.lower(EsportsPlayer.region) == "lfl").all())
    by_role = {r: [c for c in pool if c.role == r] for r in ROLES}
    used = set()
    for role in ROLES:
        choices = [c for c in by_role.get(role, []) if c.id not in used]
        if not choices:
            choices = [c for c in pool if c.id not in used]  # fallback si rôle non couvert
        if not choices:
            break
        card = random.choice(choices)
        used.add(card.id)
        db.add(GmContract(team_id=team.id, card_id=card.id, role_slot=card.role,
                          salary=card.base_salary, side="NEUTRAL", is_starter=True))

    db.flush()
    _recompute_team_ovr(db, team)
    db.commit()
    return get_team(db, user)


@router.get("/team")
def get_team(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_team(db, user)
    contracts = db.query(GmContract).filter(GmContract.team_id == team.id).all()
    cards = db.query(GmPlayerCard).filter(GmPlayerCard.id.in_([c.card_id for c in contracts])).all()
    cmap = {c.id: c for c in cards}
    idmap = _identities(db, cards)

    roster = [{
        "contract_id": ct.id,
        "role_slot":   ct.role_slot,
        "side":        ct.side,
        "is_starter":  ct.is_starter,
        "salary":      ct.salary,
        **_serialize_card(
            cmap[ct.card_id],
            idmap.get(cmap[ct.card_id].esports_player_id),
            _team_brand(db, getattr(idmap.get(cmap[ct.card_id].esports_player_id), "team_code", None)),
        ),
    } for ct in contracts]

    return {
        "team": {
            "id": team.id, "name": team.name, "logo_url": team.logo_url,
            "league": team.league, "budget": team.budget, "fans": team.fans,
            "reputation": team.reputation, "ovr": team.ovr_cached,
        },
        "roster": roster,
    }


# ═══════════════════════════════════════════════════════════
# PACKS
# ═══════════════════════════════════════════════════════════
@router.get("/packs")
def list_packs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    packs = db.query(GmPackType).filter(GmPackType.is_active == True).all()
    return [{
        "id": p.id, "name": p.name, "description": p.description, "image_url": p.image_url,
        "price_budget": p.price_budget, "league_filter": p.league_filter, "role_filter": p.role_filter,
        "weights": {"70-74": p.w_70_74, "75-84": p.w_75_84, "85-89": p.w_85_89, "90+": p.w_90_99},
    } for p in packs]


def _roll_bracket(pack):
    buckets = [(lo, hi, getattr(pack, attr)) for lo, hi, attr in OVR_BRACKETS]
    total = sum(w for _, _, w in buckets)
    if total <= 0:
        return (70, 74)
    r, acc = random.uniform(0, total), 0
    for lo, hi, w in buckets:
        acc += w
        if r <= acc:
            return (lo, hi)
    return (70, 74)


@router.post("/packs/{pack_id}/open")
def open_pack(pack_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_team(db, user)
    pack = db.query(GmPackType).filter(GmPackType.id == pack_id, GmPackType.is_active == True).first()
    if not pack:
        raise HTTPException(404, "Pack introuvable.")
    if team.budget < pack.price_budget:
        raise HTTPException(400, "Budget insuffisant.")

    def base_query():
        q = db.query(GmPlayerCard).filter(GmPlayerCard.is_active == True)
        if pack.league_filter:
            q = q.join(EsportsPlayer, GmPlayerCard.esports_player_id == EsportsPlayer.id) \
                 .filter(func.lower(EsportsPlayer.region) == pack.league_filter.lower())
        if pack.role_filter:
            q = q.filter(GmPlayerCard.role == pack.role_filter)
        return q

    lo, hi = _roll_bracket(pack)
    candidates = base_query().filter(GmPlayerCard.ovr >= lo, GmPlayerCard.ovr <= hi).all()
    if not candidates:
        candidates = base_query().all()  # fallback : aucune carte dans la tranche tirée
    if not candidates:
        raise HTTPException(409, "Aucune carte disponible dans le pool de ce pack.")

    card = random.choice(candidates)
    team.budget -= pack.price_budget
    db.add(GmContract(team_id=team.id, card_id=card.id, role_slot=card.role,
                      salary=card.base_salary, side="NEUTRAL", is_starter=False))
    db.commit()

    ep = db.query(EsportsPlayer).filter(EsportsPlayer.id == card.esports_player_id).first() \
        if card.esports_player_id else None
    return {"card": _serialize_card(card, ep, _team_brand(db, ep.team_code) if ep else None), "budget": team.budget}


# ═══════════════════════════════════════════════════════════
# VENTE
# ═══════════════════════════════════════════════════════════
@router.post("/contracts/{contract_id}/sell")
def sell_contract(contract_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_team(db, user)
    ct = db.query(GmContract).filter(GmContract.id == contract_id, GmContract.team_id == team.id).first()
    if not ct:
        raise HTTPException(404, "Contrat introuvable.")
    if ct.is_starter:
        raise HTTPException(400, "Titulaire : retire-le du 5 avant de vendre.")

    card = db.query(GmPlayerCard).filter(GmPlayerCard.id == ct.card_id).first()
    amount = resale_value(card.ovr if card else 70)
    team.budget += amount
    db.delete(ct)
    db.commit()
    return {"sold": amount, "budget": team.budget}

@router.patch("/contracts/{contract_id}")
def update_contract(contract_id: int, body: ContractUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_team(db, user)
    ct = db.query(GmContract).filter(GmContract.id == contract_id, GmContract.team_id == team.id).first()
    if not ct:
        raise HTTPException(404, "Contrat introuvable.")

    if body.side is not None:
        s = body.side.upper()
        if s not in ("STRONG", "WEAK", "NEUTRAL"):
            raise HTTPException(400, "Side invalide.")
        ct.side = s

    if body.role_slot is not None:
        rs = body.role_slot.upper()
        if rs not in ROLES:
            raise HTTPException(400, "Rôle invalide.")
        ct.role_slot = rs

    if body.is_starter is not None:
        if body.is_starter:
            card = db.query(GmPlayerCard).filter(GmPlayerCard.id == ct.card_id).first()
            role = (ct.role_slot or (card.role if card else "MID")).upper()
            ct.role_slot = role
            # Banc l'ancien titulaire de ce rôle
            for c in db.query(GmContract).filter(
                GmContract.team_id == team.id, GmContract.is_starter == True,
                GmContract.role_slot == role, GmContract.id != ct.id).all():
                c.is_starter = False
            ct.is_starter = True
        else:
            ct.is_starter = False

    db.flush()
    _recompute_team_ovr(db, team)
    db.commit()
    return get_team(db, user)

# ═══════════════════════════════════════════════════════════
# COMPÉTITION (Tranche 2 — 2a : saison, calendrier, classement)
# ═══════════════════════════════════════════════════════════
def _serialize_season(db, season, team):
    ai = {a.id: a for a in db.query(GmAiTeam).all()}

    def comp(ai_id):
        if ai_id is None:
            return {"is_user": True, "name": team.name, "logo_url": team.logo_url, "tier": None}
        a = ai.get(ai_id)
        return {"is_user": False, "name": a.name if a else "?",
                "logo_url": a.logo_url if a else None, "tier": a.bot_tier if a else None}

    standings = db.query(GmStanding).filter(GmStanding.season_id == season.id).all()
    standings.sort(key=lambda s: (-s.points, -(s.wins - s.losses), s.losses))
    table = [{**comp(s.ai_team_id), "wins": s.wins, "losses": s.losses,
              "points": s.points, "played": s.played} for s in standings]

    matches = db.query(GmMatch).filter(GmMatch.season_id == season.id) \
        .order_by(GmMatch.matchday.asc(), GmMatch.id.asc()).all()
    calendar = [{
        "id": m.id, "matchday": m.matchday, "phase": m.phase, "format": m.format,
        "status": m.status, "involves_user": m.involves_user,
        "home": comp(m.home_ai_id), "away": comp(m.away_ai_id),
        "score_home": m.score_home, "score_away": m.score_away, "winner_side": m.winner_side,
    } for m in matches]

    return {
        "season": {
            "id": season.id, "league": season.league, "year": season.year,
            "split_no": season.split_no, "phase": season.phase,
            "current_matchday": season.current_matchday, "total_matchdays": season.total_matchdays,
        },
        "standings": table,
        "calendar": calendar,
    }


@router.post("/season/start")
def start_season(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_team(db, user)
    season = create_season(db, team)
    return _serialize_season(db, season, team)


@router.get("/season")
def get_season(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_team(db, user)
    season = db.query(GmSeason).filter(
        GmSeason.team_id == team.id, GmSeason.phase != "DONE"
    ).order_by(GmSeason.id.desc()).first()
    if not season:
        return {"season": None}
    return _serialize_season(db, season, team)

# ═══════════════════════════════════════════════════════════
# ADMIN — saisie des stats + packs
# ═══════════════════════════════════════════════════════════
@router.get("/admin/cards")
def admin_list_cards(league: Optional[str] = None, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    q = db.query(GmPlayerCard).filter(GmPlayerCard.is_active == True)
    if league:
        q = q.join(EsportsPlayer, GmPlayerCard.esports_player_id == EsportsPlayer.id) \
             .filter(func.lower(EsportsPlayer.region) == league.lower())
    cards = q.all()
    idmap = _identities(db, cards)
    return [_serialize_card(c, idmap.get(c.esports_player_id)) for c in cards]


@router.put("/admin/cards/{card_id}")
def admin_update_card(card_id: int, body: AdminCardUpdate, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    card = db.query(GmPlayerCard).filter(GmPlayerCard.id == card_id).first()
    if not card:
        raise HTTPException(404, "Carte introuvable.")

    for stat in ("laning", "teamfight", "vision", "mechanics", "stress", "clutch"):
        v = getattr(body, stat)
        if v is not None:
            setattr(card, stat, max(0, min(100, v)))
    if body.ego is not None:
        if not (1 <= body.ego <= 5):
            raise HTTPException(400, "Ego entre 1 et 5.")
        card.ego = body.ego
    if body.role is not None:
        card.role = body.role.upper()
    if body.nationality is not None:
        card.nationality = (body.nationality.upper()[:2] or None)
    if body.traits is not None:
        card.traits = body.traits
    if body.photo_url is not None:
        card.photo_url = body.photo_url.strip() or None
    if body.is_active is not None:
        card.is_active = bool(body.is_active)

    card.ovr = compute_ovr(card.role, card.laning, card.teamfight, card.vision,
                           card.mechanics, card.stress, card.clutch)
    card.base_salary = salary_from_ovr(card.ovr)
    db.commit()

    ep = db.query(EsportsPlayer).filter(EsportsPlayer.id == card.esports_player_id).first() \
        if card.esports_player_id else None
    return _serialize_card(card, ep, _team_brand(db, ep.team_code) if ep else None)


@router.post("/admin/packs")
def admin_create_pack(body: PackCreate, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    total = body.w_70_74 + body.w_75_84 + body.w_85_89 + body.w_90_99
    if total != 100:
        raise HTTPException(400, f"Les poids doivent totaliser 100 (actuel : {total}).")
    pack = GmPackType(**body.dict())
    db.add(pack)
    db.commit()
    db.refresh(pack)
    return {"id": pack.id, "name": pack.name}

@router.delete("/admin/cards/{card_id}")
def admin_deactivate_card(card_id: int, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    card = db.query(GmPlayerCard).filter(GmPlayerCard.id == card_id).first()
    if not card:
        raise HTTPException(404, "Carte introuvable.")
    card.is_active = False
    db.commit()
    return {"ok": True, "card_id": card_id}

# ═══════════════════════════════════════════════════════════
# MATCH (Tranche 2 — 2b : jouer sa journée)
# ═══════════════════════════════════════════════════════════
_FORMAT_WINS = {"BO1": 1, "BO3": 2, "BO5": 3}


def _active_season(db, team):
    s = db.query(GmSeason).filter(
        GmSeason.team_id == team.id, GmSeason.phase != "DONE"
    ).order_by(GmSeason.id.desc()).first()
    if not s:
        raise HTTPException(404, "Aucune saison en cours.")
    return s


def _current_user_match(db, season):
    return db.query(GmMatch).filter(
        GmMatch.season_id == season.id,
        GmMatch.matchday == season.current_matchday,
        GmMatch.involves_user == True,
        GmMatch.status != "PLAYED",
    ).first()


def _opp_ai(db, match):
    aid = match.away_ai_id if match.home_ai_id is None else match.home_ai_id
    return db.query(GmAiTeam).filter(GmAiTeam.id == aid).first()


def _user_side_in_match(match):
    return "HOME" if match.home_ai_id is None else "AWAY"


def _match_of(db, game):
    return db.query(GmMatch).filter(GmMatch.id == game.match_id).first()


def _active_game(db, team):
    season = _active_season(db, team)
    match = _current_user_match(db, season)
    if not match:
        raise HTTPException(404, "Aucun match en cours.")
    game = db.query(GmGame).filter(
        GmGame.match_id == match.id, GmGame.game_no == 1, GmGame.status == "DRAFTING"
    ).first()
    if not game:
        raise HTTPException(404, "Aucune draft en cours. Lance le match d'abord.")
    return game


def _bump_standing(db, season_id, ai_team_id, won):
    st = db.query(GmStanding).filter(
        GmStanding.season_id == season_id, GmStanding.ai_team_id == ai_team_id
    ).first()
    if not st:
        return
    st.played += 1
    if won:
        st.wins += 1; st.points += 1
    else:
        st.losses += 1


def _sim_matchday_ai(db, season, matchday):
    matches = db.query(GmMatch).filter(
        GmMatch.season_id == season.id, GmMatch.matchday == matchday,
        GmMatch.involves_user == False, GmMatch.status != "PLAYED",
    ).all()
    strengths = {a.id: a.base_strength for a in db.query(GmAiTeam).all()}
    for m in matches:
        sh, sa, winner = sim_ai_series(
            float(strengths.get(m.home_ai_id, 65)),
            float(strengths.get(m.away_ai_id, 65)),
            wins_needed=_FORMAT_WINS.get(m.format, 1),
        )
        m.score_home, m.score_away, m.winner_side = sh, sa, winner
        m.status, m.played_at = "PLAYED", datetime.utcnow()
        home_won = winner == "HOME"
        _bump_standing(db, season.id, m.home_ai_id, home_won)
        _bump_standing(db, season.id, m.away_ai_id, not home_won)


def _generate_playoffs(db, season):
    standings = db.query(GmStanding).filter(GmStanding.season_id == season.id).all()
    standings.sort(key=lambda s: (-s.points, -(s.wins - s.losses), s.losses))
    top4 = standings[:4]
    if len(top4) < 4:
        return
    sid = lambda s: s.ai_team_id   # None = user
    for label, a, b in [("Demi-finale 1", top4[0], top4[3]),
                        ("Demi-finale 2", top4[1], top4[2])]:
        db.add(GmMatch(
            season_id=season.id, phase="SEMI", round_label=label,
            home_ai_id=sid(a), away_ai_id=sid(b), format="BO3",
            status="SCHEDULED", involves_user=(sid(a) is None or sid(b) is None),
        ))


def _advance_season(db, season):
    if season.current_matchday < season.total_matchdays:
        season.current_matchday += 1
        return
    if season.phase == "REGULAR":
        season.phase = "PLAYOFFS"
        _generate_playoffs(db, season)


def _serialize_match_game(db, match, game):
    state = game.draft_state or {}
    opp = _opp_ai(db, match)
    return {
        "match_id": match.id, "game_id": game.id, "matchday": match.matchday,
        "format": match.format, "user_side": game.user_side, "status": game.status,
        "opponent": {"name": opp.name if opp else "?",
                     "logo_url": opp.logo_url if opp else None,
                     "tier": opp.bot_tier if opp else None},
        "draft_state": state,
        "current_turn": current_turn(state) if state else None,
    }


@router.post("/season/match/start")
def match_start(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_team(db, user)
    season = _active_season(db, team)
    if season.phase != "REGULAR":
        raise HTTPException(400, "Phase non jouable (playoffs à venir).")
    match = _current_user_match(db, season)
    if not match:
        raise HTTPException(404, "Aucun match à jouer pour cette journée.")
    game = db.query(GmGame).filter(GmGame.match_id == match.id, GmGame.game_no == 1).first()
    if game and game.status == "DRAFTING":
        return _serialize_match_game(db, match, game)
    if game and game.status == "PLAYED":
        raise HTTPException(400, "Match déjà joué.")
    user_side = random.choice(["BLUE", "RED"])
    game = GmGame(match_id=match.id, game_no=1, user_side=user_side,
                  draft_state=init_state(user_side), status="DRAFTING")
    match.status = "DRAFTING"
    db.add(game)
    try:
        db.commit()
    except IntegrityError:
        # course : une autre requête a déjà créé la game → on récupère l'existante
        db.rollback()
        game = db.query(GmGame).filter(
            GmGame.match_id == match.id, GmGame.game_no == 1
        ).first()
        if not game:
            raise HTTPException(409, "Conflit de création, réessaie.")
        return _serialize_match_game(db, match, game)
    db.refresh(game)
    return _serialize_match_game(db, match, game)


@router.post("/season/match/action")
def match_action(body: GmActionReq, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_team(db, user)
    game = _active_game(db, team)
    state = dict(game.draft_state or {})
    if is_draft_done(state):
        raise HTTPException(400, "Draft terminée.")
    if current_turn(state)["actor"] != "USER":
        raise HTTPException(400, "Tour du bot.")
    try:
        apply_action(state, body.champion, expected_actor="USER")
    except ValueError as e:
        raise HTTPException(400, str(e))
    game.draft_state = state
    flag_modified(game, "draft_state")
    db.commit(); db.refresh(game)
    return _serialize_match_game(db, _match_of(db, game), game)


@router.post("/season/match/bot-turn")
def match_bot_turn(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_team(db, user)
    game = _active_game(db, team)
    state = dict(game.draft_state or {})
    if is_draft_done(state):
        raise HTTPException(400, "Draft terminée.")
    if current_turn(state)["actor"] != "BOT":
        raise HTTPException(400, "Pas le tour du bot.")
    match = _match_of(db, game)
    opp = _opp_ai(db, match)
    state, _ = bot_play_turn(db, state, opp.bot_tier if opp else "LFL")
    game.draft_state = state
    flag_modified(game, "draft_state")
    db.commit(); db.refresh(game)
    return _serialize_match_game(db, match, game)


@router.post("/season/match/finish")
def match_finish(body: GmAssignReq, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_team(db, user)
    game = _active_game(db, team)
    state = dict(game.draft_state or {})
    if not is_draft_done(state):
        raise HTTPException(400, "Draft pas terminée.")
    match  = _match_of(db, game)
    season = db.query(GmSeason).filter(GmSeason.id == match.season_id).first()
    opp    = _opp_ai(db, match)

    user_side, bot_side = state["user_side"], state["bot_side"]
    try:
        apply_role_assignment(state, user_side, body.role_map)
    except ValueError as e:
        raise HTTPException(400, str(e))
    bot_picks = state["red" if bot_side == "RED" else "blue"]["picks"]
    apply_role_assignment(state, bot_side, bot_assign_roles(db, bot_picks, plan=state.get("bot_plan")))

    blue = [TeamPick(champion=c, lane=l) for l, c in state["blue"]["lanes"].items()]
    red  = [TeamPick(champion=c, lane=l) for l, c in state["red"]["lanes"].items()]
    res = compare_drafts(db, blue, red)
    draft_user = res["blue"]["total"] if user_side == "BLUE" else res["red"]["total"]
    draft_opp  = res["red"]["total"]  if user_side == "BLUE" else res["blue"]["total"]

    metrics = team_metrics(db, team.id)
    opp_strength = float(opp.base_strength) if opp else 65.0
    p_win, d, f, m, su, mu = compute_pwin(draft_user, draft_opp, metrics, opp_strength)
    win = random.random() < p_win

    game.draft_state = state
    game.user_side = user_side
    game.draft_user, game.draft_opp = draft_user, draft_opp
    game.strength_user, game.strength_opp = su, opp_strength
    game.mental_user, game.mental_opp = mu, 0.0
    game.p_win, game.result = p_win, ("WIN" if win else "LOSS")
    game.status, game.played_at = "PLAYED", datetime.utcnow()
    flag_modified(game, "draft_state")

    us = _user_side_in_match(match)
    if (win and us == "HOME") or (not win and us == "AWAY"):
        match.score_home += 1
    else:
        match.score_away += 1
    match.winner_side = "HOME" if match.score_home > match.score_away else "AWAY"
    match.status, match.played_at = "PLAYED", datetime.utcnow()

    _bump_standing(db, season.id, None, win)
    _bump_standing(db, season.id, opp.id if opp else None, not win)

    reward = reward_for(win)
    team.budget += reward

    _sim_matchday_ai(db, season, match.matchday)
    _advance_season(db, season)

    db.commit()
    return {
        "result": "WIN" if win else "LOSS",
        "p_win": round(p_win, 3),
        "draft": {"user": round(draft_user, 1), "opp": round(draft_opp, 1)},
        "components": {"draft": round(d, 3), "strength": round(f, 3), "mental": round(m, 3)},
        "reward_budget": reward, "budget": team.budget,
        "season": _serialize_season(db, season, team),
    }