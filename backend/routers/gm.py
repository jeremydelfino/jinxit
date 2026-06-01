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
from models.esports_player import EsportsPlayer
from services.gm_ovr import compute_ovr, salary_from_ovr, resale_value

router = APIRouter(prefix="/gm", tags=["gm"])

ROLES = ["TOP", "JUNGLE", "MID", "ADC", "SUPPORT"]
STARTING_BUDGET = 5000
OVR_BRACKETS = [(70, 74, "w_70_74"), (75, 84, "w_75_84"), (85, 89, "w_85_89"), (90, 99, "w_90_99")]


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

# ─── Helpers de sérialisation ──────────────────────────────
def _identities(db: Session, cards):
    ids = [c.esports_player_id for c in cards if c.esports_player_id]
    rows = db.query(EsportsPlayer).filter(EsportsPlayer.id.in_(ids)).all() if ids else []
    return {r.id: r for r in rows}


def _serialize_card(card: GmPlayerCard, ep: Optional[EsportsPlayer]):
    return {
        "card_id":     card.id,
        "variant":     card.variant,
        "role":        card.role,
        "nationality": card.nationality,
        "ovr":         card.ovr,
        "ego":         card.ego,
        "traits":      card.traits,
        "base_salary": card.base_salary,
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
        "is_starter":  ct.is_starter,
        "side":        ct.side,
        "role_slot":   ct.role_slot,
        "salary":      ct.salary,
        **_serialize_card(cmap[ct.card_id], idmap.get(cmap[ct.card_id].esports_player_id)),
    } for ct in contracts if ct.card_id in cmap]

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
    return {"card": _serialize_card(card, ep), "budget": team.budget}


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

    card.ovr = compute_ovr(card.role, card.laning, card.teamfight, card.vision,
                           card.mechanics, card.stress, card.clutch)
    card.base_salary = salary_from_ovr(card.ovr)
    db.commit()

    ep = db.query(EsportsPlayer).filter(EsportsPlayer.id == card.esports_player_id).first() \
        if card.esports_player_id else None
    return _serialize_card(card, ep)


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