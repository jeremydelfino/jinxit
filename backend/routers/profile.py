from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models.user import User
from deps import get_current_user
from services import riot
import random

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me")
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    riot_player = None
    if current_user.riot_puuid:
        from models.player import SearchedPlayer
        sp = db.query(SearchedPlayer).filter(
            SearchedPlayer.riot_puuid == current_user.riot_puuid
        ).first()
        if sp:
            riot_player = {
                "summoner_name":    sp.summoner_name,
                "tag_line":         sp.tag_line,
                "region":           sp.region,
                "tier":             sp.tier,
                "rank":             sp.rank,
                "lp":               sp.lp,
                "profile_icon_url": sp.profile_icon_url,
            }

    return {
        "id":          current_user.id,
        "username":    current_user.username,
        "email":       current_user.email,
        "coins":       current_user.coins,
        "avatar_url":  current_user.avatar_url,
        "riot_linked": current_user.riot_puuid is not None,
        "riot_puuid":  current_user.riot_puuid,
        "last_daily":  current_user.last_daily,
        "riot_player": riot_player,
        "favorite_team": {
            "name":  current_user.favorite_team_name,
            "logo":  current_user.favorite_team_logo,
            "color": current_user.favorite_team_color,
        } if current_user.favorite_team_name else None,
    }


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
    return {"success": True, "favorite_team": {"name": body.name, "logo": body.logo, "color": body.color}}


class LinkRiotSchema(BaseModel):
    game_name: str
    tag_line:  str
    region:    str

@router.post("/link-riot/init")
async def link_riot_init(
    body: LinkRiotSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = await riot.get_account_by_riot_id(body.game_name, body.tag_line, body.region)
    puuid = account["puuid"]
    existing = db.query(User).filter(User.riot_puuid == puuid, User.id != current_user.id).first()
    if existing:
        raise HTTPException(400, "Ce compte Riot est déjà lié à un autre compte Jinxit")
    icon_id = random.randint(1, 28)
    current_user.riot_puuid = puuid
    current_user.riot_verification_icon = icon_id
    db.commit()
    return {
        "icon_id": icon_id,
        "icon_url": f"https://ddragon.leagueoflegends.com/cdn/14.10.1/img/profileicon/{icon_id}.png",
        "instructions": f"Change ton icône pour l'icône n°{icon_id} dans LoL, puis clique Vérifier",
        "game_name": body.game_name, "tag_line": body.tag_line, "region": body.region,
    }

@router.post("/link-riot/verify")
async def link_riot_verify(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.riot_puuid or not current_user.riot_verification_icon:
        raise HTTPException(400, "Lance d'abord /link-riot/init")
    from models.player import SearchedPlayer
    player = db.query(SearchedPlayer).filter(SearchedPlayer.riot_puuid == current_user.riot_puuid).first()
    if not player:
        raise HTTPException(400, "Joueur introuvable en cache, relance /link-riot/init")
    summoner = await riot.get_summoner_by_puuid(current_user.riot_puuid, player.region)
    current_icon = summoner["profileIconId"]
    if current_icon != current_user.riot_verification_icon:
        raise HTTPException(400, f"Mauvaise icône (actuelle : {current_icon}, attendue : {current_user.riot_verification_icon})")
    current_user.riot_verification_icon = None
    db.commit()
    return {"success": True, "message": "Compte Riot lié avec succès !", "riot_puuid": current_user.riot_puuid}