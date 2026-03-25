from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.player import SearchedPlayer
from models.pro_player import ProPlayer
from models.match import MatchHistory
from services import riot
from datetime import datetime, timedelta
from models.user import User
import httpx
from fastapi.responses import Response

router = APIRouter(prefix="/players", tags=["players"])



@router.get("/proxy/icon")
async def proxy_icon(url: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        return Response(content=res.content, media_type="image/png")

@router.get("/search/autocomplete")
def autocomplete(q: str, db: Session = Depends(get_db)):
    if not q or len(q) < 2:
        return []
    results = db.query(SearchedPlayer).filter(
        SearchedPlayer.summoner_name.ilike(f"%{q}%")
    ).order_by(SearchedPlayer.last_updated.desc()).limit(5).all()
    return [
        {
            "summoner_name": p.summoner_name,
            "tag_line": p.tag_line,
            "region": p.region,
            "tier": p.tier,
            "rank": p.rank,
            "profile_icon_url": p.profile_icon_url,
        }
        for p in results
    ]

@router.get("/{region}/{game_name}/{tag_line}")
async def get_player(region: str, game_name: str, tag_line: str, db: Session = Depends(get_db)):

    # 1. Chercher en cache d'abord (par nom+tag+region OU par puuid)
    cached = db.query(SearchedPlayer).filter(
        SearchedPlayer.summoner_name.ilike(game_name),
        SearchedPlayer.tag_line.ilike(tag_line),
        SearchedPlayer.region == region.upper()
    ).first()

    cache_valid = cached and (datetime.utcnow() - cached.last_updated) < timedelta(minutes=5)

    if not cache_valid:
        try:
            account = await riot.get_account_by_riot_id(game_name, tag_line, region)
            puuid = account["puuid"]

            summoner = await riot.get_summoner_by_puuid(puuid, region)
            rank_data = await riot.get_rank_by_puuid(puuid, region)
            solo_rank = next((r for r in rank_data if r["queueType"] == "RANKED_SOLO_5x5"), None)

            profile_icon_url = f"https://ddragon.leagueoflegends.com/cdn/14.10.1/img/profileicon/{summoner['profileIconId']}.png"

            # ✅ Chercher aussi par puuid pour éviter le UniqueViolation
            existing_by_puuid = db.query(SearchedPlayer).filter(
                SearchedPlayer.riot_puuid == puuid
            ).first()

            if existing_by_puuid:
                # Mettre à jour l'entrée existante
                existing_by_puuid.summoner_name = game_name
                existing_by_puuid.tag_line = tag_line
                existing_by_puuid.region = region.upper()
                existing_by_puuid.tier = solo_rank["tier"] if solo_rank else None
                existing_by_puuid.rank = solo_rank["rank"] if solo_rank else None
                existing_by_puuid.lp = solo_rank["leaguePoints"] if solo_rank else 0
                existing_by_puuid.profile_icon_url = profile_icon_url
                existing_by_puuid.last_updated = datetime.utcnow()
                player = existing_by_puuid
            elif cached:
                cached.riot_puuid = puuid
                cached.tier = solo_rank["tier"] if solo_rank else None
                cached.rank = solo_rank["rank"] if solo_rank else None
                cached.lp = solo_rank["leaguePoints"] if solo_rank else 0
                cached.profile_icon_url = profile_icon_url
                cached.last_updated = datetime.utcnow()
                player = cached
            else:
                player = SearchedPlayer(
                    riot_puuid=puuid,
                    summoner_name=game_name,
                    tag_line=tag_line,
                    region=region.upper(),
                    tier=solo_rank["tier"] if solo_rank else None,
                    rank=solo_rank["rank"] if solo_rank else None,
                    lp=solo_rank["leaguePoints"] if solo_rank else 0,
                    profile_icon_url=profile_icon_url,
                )
                db.add(player)

            db.commit()
            db.refresh(player)

        except Exception as e:
            raise HTTPException(404, f"Joueur introuvable : {str(e)}")
    else:
        player = cached

    live_game = await riot.get_live_game_by_puuid(player.riot_puuid, region)

    # 5. Récupérer l'historique des matchs
    raw_matches = await riot.get_match_history(player.riot_puuid, region, count=10)
    matches = []
    for m in raw_matches:
        participant = next((p for p in m["info"]["participants"] if p["puuid"] == player.riot_puuid), None)
        if participant:
            matches.append({
                "champion": participant["championName"],
                "role": participant.get("teamPosition", ""),
                "win": participant["win"],
                "kills": participant["kills"],
                "deaths": participant["deaths"],
                "assists": participant["assists"],
                "cs": participant["totalMinionsKilled"],
                "duration": m["info"]["gameDuration"],
            })

    pro_player = db.query(ProPlayer).filter(
        ProPlayer.riot_puuid == player.riot_puuid
    ).first()

    # Vérifier si ce joueur a un compte Jinxit lié
    jinxit_profile = None
    jinxit_user = db.query(User).filter(User.riot_puuid == player.riot_puuid).first()
    if jinxit_user:
        jinxit_profile = {
            "username": jinxit_user.username,
            "avatar_url": jinxit_user.avatar_url,
            "coins": jinxit_user.coins,
            "equipped_title": None,
            "equipped_banner": None,
        }
        if jinxit_user.equipped_title_id:
            from models.card import Card
            title_card = db.query(Card).filter(Card.id == jinxit_user.equipped_title_id).first()
            if title_card:
                jinxit_profile["equipped_title"] = title_card.title_text
        if jinxit_user.equipped_banner_id:
            from models.card import Card
            banner_card = db.query(Card).filter(Card.id == jinxit_user.equipped_banner_id).first()
            if banner_card:
                jinxit_profile["equipped_banner"] = banner_card.image_url

    return {
    "player": {
        "summoner_name": player.summoner_name,
        "tag_line": player.tag_line,
        "region": player.region,
        "tier": player.tier,
        "rank": player.rank,
        "lp": player.lp,
        "profile_icon_url": player.profile_icon_url,
    },
    "live_game": live_game,
    "match_history": matches,
    "jinxit_profile": jinxit_profile,
    "pro_player": {
        "name": pro_player.name,
        "team": pro_player.team,
        "role": pro_player.role,
        "accent_color": pro_player.accent_color,
        "photo_url": pro_player.photo_url,
        "team_logo_url": pro_player.team_logo_url,  # ✅ ajout
    } if pro_player else None,
}