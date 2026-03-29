from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.player import SearchedPlayer
from models.pro_player import ProPlayer
from models.live_game import LiveGame
from models.user import User
from models.bet import Bet
from models.riot_account import RiotAccount
from models.esports_player import EsportsPlayer
from models.esports_team import EsportsTeam
from services import riot
from datetime import datetime, timedelta
import httpx
from fastapi.responses import Response

router = APIRouter(prefix="/players", tags=["players"])

SMITE = 11

# ─── Helpers ─────────────────────────────────────────────────

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


def build_team(participants: list, team_id: int) -> list:
    team   = [p for p in participants if p.get("teamId") == team_id]
    result = []
    for p in team:
        champ_name = (p.get("championName") or "").strip()
        spells     = {p.get("spell1Id", 0), p.get("spell2Id", 0)}
        role_guess = "JUNGLE" if SMITE in spells else None
        result.append({
            "puuid":        (p.get("puuid") or "").strip() or None,
            "summonerName": extract_pseudo(p, champ_name),
            "championId":   p.get("championId"),
            "championName": champ_name,
            "teamId":       team_id,
            "role":         role_guess,
            "spell1Id":     p.get("spell1Id"),
            "spell2Id":     p.get("spell2Id"),
        })
    return result


def compute_bet_stats(user_id: int, db: Session) -> dict:
    bets     = db.query(Bet).filter(Bet.user_id == user_id).order_by(Bet.created_at.desc()).all()
    won      = [b for b in bets if b.status == "won"]
    lost     = [b for b in bets if b.status == "lost"]
    resolved = len(won) + len(lost)
    winrate  = round((len(won) / resolved) * 100) if resolved > 0 else None
    streak   = 0
    for b in bets:
        if b.status == "won":
            streak += 1
        elif b.status == "lost":
            break
    return {
        "total":   len(bets),
        "won":     len(won),
        "lost":    len(lost),
        "winrate": winrate,
        "streak":  streak,
    }


def build_pro_response(
    esports_player: EsportsPlayer | None,
    pro_player:     ProPlayer     | None,
    team_obj:       EsportsTeam   | None,
) -> dict | None:
    """Construit la réponse pro enrichie depuis EsportsPlayer + ProPlayer + EsportsTeam."""
    if not esports_player and not pro_player:
        return None

    ep = esports_player
    pp = pro_player

    # Photo : priorité EsportsPlayer (API officielle), fallback ProPlayer (fandom)
    photo = (ep.photo_url if ep and ep.photo_url else None) or (pp.photo_url if pp else None)

    # Logo équipe HD depuis EsportsTeam, fallback ProPlayer
    team_logo = (
        team_obj.logo_url     if team_obj and team_obj.logo_url else
        pp.team_logo_url      if pp else None
    )

    # Accent color depuis EsportsTeam, fallback ProPlayer
    accent = (
        team_obj.accent_color if team_obj else
        pp.accent_color       if pp else "#00e5ff"
    )

    return {
        "name":          ep.summoner_name if ep else pp.name,
        "full_name": (
            f"{ep.first_name} \"{ep.summoner_name}\" {ep.last_name}"
            if ep and ep.first_name and ep.last_name
            else None
        ),
        "first_name":    ep.first_name if ep else None,
        "last_name":     ep.last_name  if ep else None,
        "team":          ep.team_code  if ep else pp.team,
        "team_name":     ep.team_name  if ep else pp.team,
        "team_logo_url": team_logo,
        "role":          ep.role       if ep else pp.role,
        "region":        ep.region     if ep else pp.region,
        "photo_url":     photo,
        "accent_color":  accent,
    }

# ─── Routes ──────────────────────────────────────────────────

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
            "summoner_name":    p.summoner_name,
            "tag_line":         p.tag_line,
            "region":           p.region,
            "tier":             p.tier,
            "rank":             p.rank,
            "profile_icon_url": p.profile_icon_url,
        }
        for p in results
    ]


@router.get("/{region}/{game_name}/{tag_line}")
async def get_player(
    region:    str,
    game_name: str,
    tag_line:  str,
    db: Session = Depends(get_db),
):
    # ── Cache SearchedPlayer ──────────────────────────────────
    cached     = db.query(SearchedPlayer).filter(
        SearchedPlayer.summoner_name.ilike(game_name),
        SearchedPlayer.tag_line.ilike(tag_line),
        SearchedPlayer.region == region.upper(),
    ).first()
    cache_valid = cached and (datetime.utcnow() - cached.last_updated) < timedelta(minutes=5)

    if not cache_valid:
        try:
            account   = await riot.get_account_by_riot_id(game_name, tag_line, region)
            puuid     = account["puuid"]
            summoner  = await riot.get_summoner_by_puuid(puuid, region)
            rank_data = await riot.get_rank_by_puuid(puuid, region)
            solo_rank = next((r for r in rank_data if r["queueType"] == "RANKED_SOLO_5x5"), None)
            profile_icon_url = (
                f"https://ddragon.leagueoflegends.com/cdn/14.10.1/img/profileicon/"
                f"{summoner['profileIconId']}.png"
            )

            existing = db.query(SearchedPlayer).filter(SearchedPlayer.riot_puuid == puuid).first()
            if existing:
                existing.summoner_name    = game_name
                existing.tag_line         = tag_line
                existing.region           = region.upper()
                existing.tier             = solo_rank["tier"]          if solo_rank else None
                existing.rank             = solo_rank["rank"]          if solo_rank else None
                existing.lp               = solo_rank["leaguePoints"]  if solo_rank else 0
                existing.profile_icon_url = profile_icon_url
                existing.last_updated     = datetime.utcnow()
                player = existing
            elif cached:
                cached.riot_puuid         = puuid
                cached.tier               = solo_rank["tier"]          if solo_rank else None
                cached.rank               = solo_rank["rank"]          if solo_rank else None
                cached.lp                 = solo_rank["leaguePoints"]  if solo_rank else 0
                cached.profile_icon_url   = profile_icon_url
                cached.last_updated       = datetime.utcnow()
                player = cached
            else:
                player = SearchedPlayer(
                    riot_puuid       = puuid,
                    summoner_name    = game_name,
                    tag_line         = tag_line,
                    region           = region.upper(),
                    tier             = solo_rank["tier"]         if solo_rank else None,
                    rank             = solo_rank["rank"]         if solo_rank else None,
                    lp               = solo_rank["leaguePoints"] if solo_rank else 0,
                    profile_icon_url = profile_icon_url,
                )
                db.add(player)
            db.commit()
            db.refresh(player)
        except Exception as e:
            raise HTTPException(404, f"Joueur introuvable : {str(e)}")
    else:
        player = cached

    # ── Live game ─────────────────────────────────────────────
    live_game_raw  = await riot.get_live_game_by_puuid(player.riot_puuid, region)
    live_game_data = None

    if live_game_raw:
        riot_game_id  = str(live_game_raw.get("gameId", ""))
        participants  = live_game_raw.get("participants", [])
        blue_team     = build_team(participants, 100)
        red_team      = build_team(participants, 200)

        existing_game = db.query(LiveGame).filter(LiveGame.riot_game_id == riot_game_id).first()
        if existing_game:
            existing_game.duration_seconds = live_game_raw.get("gameLength", 0)
            existing_game.blue_team        = blue_team
            existing_game.red_team         = red_team
            existing_game.status           = "live"
            db.commit()
            db.refresh(existing_game)
            saved_game = existing_game
        else:
            saved_game = LiveGame(
                searched_player_id = player.id,
                riot_game_id       = riot_game_id,
                queue_type         = str(live_game_raw.get("gameQueueConfigId", "")),
                blue_team          = blue_team,
                red_team           = red_team,
                duration_seconds   = live_game_raw.get("gameLength", 0),
                status             = "live",
            )
            db.add(saved_game)
            db.commit()
            db.refresh(saved_game)

        live_game_data = {
            "id":              saved_game.id,
            "riot_game_id":    saved_game.riot_game_id,
            "gameQueueConfigId": live_game_raw.get("gameQueueConfigId"),
            "gameLength":      live_game_raw.get("gameLength", 0),
            "participants":    participants,
            "blue_team":       saved_game.blue_team,
            "red_team":        saved_game.red_team,
        }

    # ── Match history ─────────────────────────────────────────
    raw_matches = await riot.get_match_history(player.riot_puuid, region, count=10)
    matches     = []
    for m in raw_matches:
        part = next(
            (p for p in m["info"]["participants"] if p["puuid"] == player.riot_puuid),
            None,
        )
        if part:
            matches.append({
                "champion": part["championName"],
                "role":     part.get("teamPosition", ""),
                "win":      part["win"],
                "kills":    part["kills"],
                "deaths":   part["deaths"],
                "assists":  part["assists"],
                "cs":       part["totalMinionsKilled"],
                "duration": m["info"]["gameDuration"],
                "played_at": (
                    datetime.utcfromtimestamp(
                        m["info"]["gameEndTimestamp"] / 1000
                    ).isoformat()
                    if m["info"].get("gameEndTimestamp") else None
                ),
            })

    # ── Pro enrichi : EsportsPlayer + ProPlayer + EsportsTeam ─
    esports_player = db.query(EsportsPlayer).filter(
        EsportsPlayer.riot_puuid == player.riot_puuid
    ).first()

    pro_player = db.query(ProPlayer).filter(
        ProPlayer.riot_puuid == player.riot_puuid
    ).first()

    # Cherche l'équipe HD : priorité EsportsPlayer, fallback ProPlayer
    team_code = (
        esports_player.team_code if esports_player and esports_player.team_code else
        pro_player.team          if pro_player else
        None
    )
    team_obj = (
        db.query(EsportsTeam).filter(EsportsTeam.code == team_code).first()
        if team_code else None
    )

    pro_response = build_pro_response(esports_player, pro_player, team_obj)

    # ── Jungle Gap profile ────────────────────────────────────
    riot_acc       = db.query(RiotAccount).filter(
        RiotAccount.riot_puuid == player.riot_puuid
    ).first()
    junglegap_user = None
    if riot_acc:
        junglegap_user = db.query(User).filter(User.id == riot_acc.user_id).first()
    if not junglegap_user:
        junglegap_user = db.query(User).filter(
            User.riot_puuid == player.riot_puuid
        ).first()

    junglegap_profile = None
    if junglegap_user:
        bet_stats = compute_bet_stats(junglegap_user.id, db)
        junglegap_profile = {
            "id":             junglegap_user.id,
            "username":       junglegap_user.username,
            "avatar_url":     junglegap_user.avatar_url,
            "coins":          junglegap_user.coins,
            "equipped_title": None,
            "bet_stats":      bet_stats,
        }
        if junglegap_user.equipped_title_id:
            from models.card import Card
            tc = db.query(Card).filter(Card.id == junglegap_user.equipped_title_id).first()
            if tc:
                junglegap_profile["equipped_title"] = tc.title_text

    return {
        "player": {
            "id":               player.id,
            "summoner_name":    player.summoner_name,
            "tag_line":         player.tag_line,
            "region":           player.region,
            "tier":             player.tier,
            "rank":             player.rank,
            "lp":               player.lp,
            "riot_puuid":       player.riot_puuid,
            "profile_icon_url": player.profile_icon_url,
        },
        "live_game":         live_game_data,
        "match_history":     matches,
        "junglegap_profile": junglegap_profile,
        "pro_player":        pro_response,
    }