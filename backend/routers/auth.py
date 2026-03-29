from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models.user import User
from models.riot_account import RiotAccount
from deps import get_current_user
from services import riot
import random

router = APIRouter(prefix="/profile", tags=["profile"])

DDV = "14.10.1"

# ─── Helpers ────────────────────────────────────────────────

def _serialize_riot_account(ra: RiotAccount) -> dict:
    return {
        "id":               ra.id,
        "riot_puuid":       ra.riot_puuid,
        "summoner_name":    ra.summoner_name,
        "tag_line":         ra.tag_line,
        "region":           ra.region,
        "tier":             ra.tier,
        "rank":             ra.rank,
        "lp":               ra.lp,
        "profile_icon_id":  ra.profile_icon_id,
        "profile_icon_url": ra.profile_icon_url,
        "is_primary":       ra.is_primary,
    }

# ─── GET /me ────────────────────────────────────────────────

@router.get("/me")
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    riot_accounts = [_serialize_riot_account(ra) for ra in current_user.riot_accounts]

    # Compat legacy : riot_player = le compte primaire
    primary = next((ra for ra in current_user.riot_accounts if ra.is_primary), None)
    if not primary and current_user.riot_accounts:
        primary = current_user.riot_accounts[0]

    riot_player = None
    if primary:
        riot_player = {
            "summoner_name":    primary.summoner_name,
            "tag_line":         primary.tag_line,
            "region":           primary.region,
            "tier":             primary.tier,
            "rank":             primary.rank,
            "lp":               primary.lp,
            "profile_icon_url": primary.profile_icon_url,
        }

    return {
        "id":            current_user.id,
        "username":      current_user.username,
        "email":         current_user.email,
        "coins":         current_user.coins,
        "avatar_url":    current_user.avatar_url,
        "riot_linked":   len(riot_accounts) > 0,
        "riot_player":   riot_player,
        "riot_accounts": riot_accounts,
        "last_daily":    current_user.last_daily,
        "favorite_team": {
            "name":  current_user.favorite_team_name,
            "logo":  current_user.favorite_team_logo,
            "color": current_user.favorite_team_color,
        } if current_user.favorite_team_name else None,
    }

# ─── GET /user/:id (profil public) ──────────────────────────

@router.get("/user/{user_id}")
def get_public_profile(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")

    primary = next((ra for ra in user.riot_accounts if ra.is_primary), None)
    if not primary and user.riot_accounts:
        primary = user.riot_accounts[0]

    return {
        "id":          user.id,
        "username":    user.username,
        "avatar_url":  user.avatar_url,
        "riot_linked": len(user.riot_accounts) > 0,
        "riot_player": {
            "summoner_name":    primary.summoner_name,
            "tag_line":         primary.tag_line,
            "region":           primary.region,
            "tier":             primary.tier,
            "rank":             primary.rank,
            "profile_icon_url": primary.profile_icon_url,
        } if primary else None,
        "riot_accounts": [_serialize_riot_account(ra) for ra in user.riot_accounts],
        "favorite_team": {
            "name":  user.favorite_team_name,
            "logo":  user.favorite_team_logo,
            "color": user.favorite_team_color,
        } if user.favorite_team_name else None,
    }

# ─── SET TEAM ────────────────────────────────────────────────

class SetTeamSchema(BaseModel):
    name:  str
    logo:  str
    color: str

@router.post("/set-team")
def set_favorite_team(
    body: SetTeamSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.favorite_team_name  = body.name
    current_user.favorite_team_logo  = body.logo
    current_user.favorite_team_color = body.color
    db.commit()
    return {"success": True}

# ─── ADD RIOT ACCOUNT — STEP 1 : init ───────────────────────

class AddRiotInitSchema(BaseModel):
    game_name: str
    tag_line:  str
    region:    str

@router.post("/riot-accounts/init")
async def add_riot_init(
    body: AddRiotInitSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Max 3 comptes par user
    if len(current_user.riot_accounts) >= 3:
        raise HTTPException(400, "Maximum 3 comptes Riot par profil")

    try:
        account = await riot.get_account_by_riot_id(body.game_name, body.tag_line, body.region)
    except Exception:
        raise HTTPException(400, "Riot ID introuvable — vérifie le pseudo et le tag")

    puuid = account["puuid"]

    # Déjà lié à ce user ?
    already_linked = db.query(RiotAccount).filter(
        RiotAccount.riot_puuid == puuid,
    ).first()
    if already_linked:
        raise HTTPException(400, "Ce compte Riot est déjà lié à un profil Jungle Gap")

    icon_id  = random.randint(1, 28)
    icon_url = f"https://ddragon.leagueoflegends.com/cdn/{DDV}/img/profileicon/{icon_id}.png"

    # Stocker temporairement le puuid + icône dans un RiotAccount non-vérifié
    pending = RiotAccount(
        user_id=current_user.id,
        riot_puuid=puuid,
        summoner_name=body.game_name,
        tag_line=body.tag_line,
        region=body.region,
        verification_icon=icon_id,
        is_primary=False,
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)

    return {
        "riot_account_id": pending.id,
        "puuid":           puuid,
        "icon_id":         icon_id,
        "icon_url":        icon_url,
        "game_name":       body.game_name,
        "tag_line":        body.tag_line,
        "region":          body.region,
    }

# ─── ADD RIOT ACCOUNT — STEP 2 : verify ─────────────────────

class AddRiotVerifySchema(BaseModel):
    riot_account_id: int

@router.post("/riot-accounts/verify")
async def add_riot_verify(
    body: AddRiotVerifySchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ra = db.query(RiotAccount).filter(
        RiotAccount.id      == body.riot_account_id,
        RiotAccount.user_id == current_user.id,
    ).first()
    if not ra:
        raise HTTPException(404, "Compte Riot introuvable, relance l'ajout")
    if not ra.verification_icon:
        raise HTTPException(400, "Ce compte est déjà vérifié")

    try:
        summoner     = await riot.get_summoner_by_puuid(ra.riot_puuid, ra.region)
        current_icon = summoner["profileIconId"]
    except Exception:
        raise HTTPException(400, "Impossible de récupérer le profil Riot")

    if current_icon != ra.verification_icon:
        raise HTTPException(
            400,
            f"Mauvaise icône (actuelle : {current_icon}, attendue : {ra.verification_icon}). "
            "Change bien ton icône dans LoL et réessaie."
        )

    # Vérification OK — finaliser
    icon_url     = f"https://ddragon.leagueoflegends.com/cdn/{DDV}/img/profileicon/{current_icon}.png"
    is_first     = len(current_user.riot_accounts) == 1  # ce compte est le seul = primary

    ra.profile_icon_id   = current_icon
    ra.profile_icon_url  = icon_url
    ra.verification_icon = None
    ra.is_primary        = is_first

    db.commit()
    db.refresh(ra)

    return {"success": True, "riot_account": _serialize_riot_account(ra)}

# ─── DELETE RIOT ACCOUNT ─────────────────────────────────────

@router.delete("/riot-accounts/{account_id}")
def delete_riot_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ra = db.query(RiotAccount).filter(
        RiotAccount.id      == account_id,
        RiotAccount.user_id == current_user.id,
    ).first()
    if not ra:
        raise HTTPException(404, "Compte introuvable")

    was_primary = ra.is_primary
    db.delete(ra)
    db.flush()

    # Si on supprime le primary, promouvoir le suivant
    if was_primary:
        remaining = db.query(RiotAccount).filter(
            RiotAccount.user_id == current_user.id,
        ).order_by(RiotAccount.created_at.asc()).first()
        if remaining:
            remaining.is_primary = True

    db.commit()
    return {"success": True}

# ─── SET PRIMARY ACCOUNT ─────────────────────────────────────

@router.post("/riot-accounts/{account_id}/set-primary")
def set_primary_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Retirer primary de tous
    for ra in current_user.riot_accounts:
        ra.is_primary = False

    # Mettre primary sur celui-ci
    target = db.query(RiotAccount).filter(
        RiotAccount.id      == account_id,
        RiotAccount.user_id == current_user.id,
    ).first()
    if not target:
        raise HTTPException(404, "Compte introuvable")

    target.is_primary = True
    db.commit()
    return {"success": True}