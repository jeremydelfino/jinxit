from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.player import SearchedPlayer
from models.pro_player import ProPlayer
from models.live_game import LiveGame
from services import riot
from datetime import datetime, timedelta
from models.user import User
import httpx
from fastapi.responses import Response

router = APIRouter(prefix="/players", tags=["players"])

# Spell IDs → rôle certain
SMITE    = 11  # → JUNGLE (100% certain)
EXHAUST  = 3   # → SUPPORT (très probable)
BARRIER  = 21  # → SUPPORT ou ADC
HEAL     = 7   # → ADC ou SUPPORT
TELEPORT = 12  # → TOP ou MID (rarement ADC/SUPP)
IGNITE   = 14  # → MID, TOP ou SUPP


def get_spell_role(s1: int, s2: int) -> str | None:
    spells = {s1, s2}
    if SMITE   in spells: return "JUNGLE"
    if EXHAUST in spells: return "SUPPORT"
    return None


def build_team(participants: list, team_id: int) -> list:
    team = [p for p in participants if p.get("teamId") == team_id]

    # Étape 1 : détecter les rôles certains via spells
    assigned = {}
    for i, p in enumerate(team):
        role = get_spell_role(p.get("spell1Id", 0), p.get("spell2Id", 0))
        if role:
            assigned[i] = role

    # Étape 2 : attribuer les rôles restants par ordre canonique
    all_roles    = ["TOP", "JUNGLE", "MID", "ADC", "SUPPORT"]
    taken_roles  = set(assigned.values())
    free_roles   = [r for r in all_roles if r not in taken_roles]
    free_indices = [i for i in range(len(team)) if i not in assigned]

    for i, idx in enumerate(free_indices):
        assigned[idx] = free_roles[i] if i < len(free_roles) else "?"

    result = []
    for i, p in enumerate(team):
        champ_name = (p.get("championName") or "").strip()
        result.append({
            "puuid":        (p.get("puuid") or "").strip() or None,
            "summonerName": extract_pseudo(p, champ_name),
            "championId":   p.get("championId"),
            "championName": champ_name,
            "teamId":       team_id,
            "role":         assigned.get(i, "?"),
            "spell1Id":     p.get("spell1Id"),
            "spell2Id":     p.get("spell2Id"),
        })
    return result


def extract_pseudo(p: dict, champ_name: str) -> str:
    riot_id = (p.get("riotId") or "").strip()
    if "#" in riot_id:
        return riot_id.split("#")[0].strip()
    if riot_id and champ_name:
        rid = riot_id.lower().replace(" ", "").replace("'", "")
        chp = champ_name.lower().replace(" ", "").replace("'", "")
        if rid == chp or rid in chp or chp in rid:
            return ""
    sn = (p.get("summonerName") or "").strip()
    if sn and len(sn) < 30 and sn.count("-") < 4:
        return sn
    return riot_id if riot_id else ""


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
    return [{"summoner_name": p.summoner_name, "tag_line": p.tag_line, "region": p.region,
             "tier": p.tier, "rank": p.rank, "profile_icon_url": p.profile_icon_url}
            for p in results]


@router.get("/{region}/{game_name}/{tag_line}")
async def get_player(region: str, game_name: str, tag_line: str, db: Session = Depends(get_db)):

    cached = db.query(SearchedPlayer).filter(
        SearchedPlayer.summoner_name.ilike(game_name),
        SearchedPlayer.tag_line.ilike(tag_line),
        SearchedPlayer.region == region.upper()
    ).first()

    cache_valid = cached and (datetime.utcnow() - cached.last_updated) < timedelta(minutes=5)

    if not cache_valid:
        try:
            account   = await riot.get_account_by_riot_id(game_name, tag_line, region)
            puuid     = account["puuid"]
            summoner  = await riot.get_summoner_by_puuid(puuid, region)
            rank_data = await riot.get_rank_by_puuid(puuid, region)
            solo_rank = next((r for r in rank_data if r["queueType"] == "RANKED_SOLO_5x5"), None)
            profile_icon_url = f"https://ddragon.leagueoflegends.com/cdn/14.10.1/img/profileicon/{summoner['profileIconId']}.png"

            existing_by_puuid = db.query(SearchedPlayer).filter(SearchedPlayer.riot_puuid == puuid).first()

            if existing_by_puuid:
                existing_by_puuid.summoner_name = game_name; existing_by_puuid.tag_line = tag_line
                existing_by_puuid.region = region.upper(); existing_by_puuid.tier = solo_rank["tier"] if solo_rank else None
                existing_by_puuid.rank = solo_rank["rank"] if solo_rank else None
                existing_by_puuid.lp = solo_rank["leaguePoints"] if solo_rank else 0
                existing_by_puuid.profile_icon_url = profile_icon_url; existing_by_puuid.last_updated = datetime.utcnow()
                player = existing_by_puuid
            elif cached:
                cached.riot_puuid = puuid; cached.tier = solo_rank["tier"] if solo_rank else None
                cached.rank = solo_rank["rank"] if solo_rank else None
                cached.lp = solo_rank["leaguePoints"] if solo_rank else 0
                cached.profile_icon_url = profile_icon_url; cached.last_updated = datetime.utcnow()
                player = cached
            else:
                player = SearchedPlayer(riot_puuid=puuid, summoner_name=game_name, tag_line=tag_line,
                    region=region.upper(), tier=solo_rank["tier"] if solo_rank else None,
                    rank=solo_rank["rank"] if solo_rank else None,
                    lp=solo_rank["leaguePoints"] if solo_rank else 0, profile_icon_url=profile_icon_url)
                db.add(player)
            db.commit(); db.refresh(player)
        except Exception as e:
            raise HTTPException(404, f"Joueur introuvable : {str(e)}")
    else:
        player = cached

    live_game_raw  = await riot.get_live_game_by_puuid(player.riot_puuid, region)
    live_game_data = None

    if live_game_raw:
        riot_game_id = str(live_game_raw.get("gameId", ""))
        participants = live_game_raw.get("participants", [])
        blue_team = build_team(participants, 100)
        red_team  = build_team(participants, 200)

        existing_game = db.query(LiveGame).filter(LiveGame.riot_game_id == riot_game_id).first()
        if existing_game:
            existing_game.duration_seconds = live_game_raw.get("gameLength", 0)
            existing_game.blue_team = blue_team; existing_game.red_team = red_team
            existing_game.status = "live"; db.commit(); db.refresh(existing_game)
            saved_game = existing_game
        else:
            saved_game = LiveGame(searched_player_id=player.id, riot_game_id=riot_game_id,
                queue_type=str(live_game_raw.get("gameQueueConfigId", "")),
                blue_team=blue_team, red_team=red_team,
                duration_seconds=live_game_raw.get("gameLength", 0), status="live")
            db.add(saved_game); db.commit(); db.refresh(saved_game)

        live_game_data = {"id": saved_game.id, "riot_game_id": saved_game.riot_game_id,
            "gameQueueConfigId": live_game_raw.get("gameQueueConfigId"),
            "gameLength": live_game_raw.get("gameLength", 0),
            "participants": participants,
            "blue_team": saved_game.blue_team, "red_team": saved_game.red_team}

    raw_matches = await riot.get_match_history(player.riot_puuid, region, count=10)
    matches = []
    for m in raw_matches:
        part = next((p for p in m["info"]["participants"] if p["puuid"] == player.riot_puuid), None)
        if part:
            matches.append({"champion": part["championName"], "role": part.get("teamPosition", ""),
                "win": part["win"], "kills": part["kills"], "deaths": part["deaths"],
                "assists": part["assists"], "cs": part["totalMinionsKilled"], "duration": m["info"]["gameDuration"]})

    pro_player  = db.query(ProPlayer).filter(ProPlayer.riot_puuid == player.riot_puuid).first()
    jinxit_user = db.query(User).filter(User.riot_puuid == player.riot_puuid).first()
    jinxit_profile = None
    if jinxit_user:
        jinxit_profile = {"username": jinxit_user.username, "avatar_url": jinxit_user.avatar_url,
            "coins": jinxit_user.coins, "equipped_title": None, "equipped_banner": None}
        if jinxit_user.equipped_title_id:
            from models.card import Card
            tc = db.query(Card).filter(Card.id == jinxit_user.equipped_title_id).first()
            if tc: jinxit_profile["equipped_title"] = tc.title_text
        if jinxit_user.equipped_banner_id:
            from models.card import Card
            bc = db.query(Card).filter(Card.id == jinxit_user.equipped_banner_id).first()
            if bc: jinxit_profile["equipped_banner"] = bc.image_url

    return {
        "player": {"summoner_name": player.summoner_name, "tag_line": player.tag_line,
            "region": player.region, "tier": player.tier, "rank": player.rank,
            "lp": player.lp, "profile_icon_url": player.profile_icon_url},
        "live_game": live_game_data, "match_history": matches,
        "jinxit_profile": jinxit_profile,
        "pro_player": {"name": pro_player.name, "team": pro_player.team, "role": pro_player.role,
            "accent_color": pro_player.accent_color, "photo_url": pro_player.photo_url,
            "team_logo_url": pro_player.team_logo_url} if pro_player else None,
    }