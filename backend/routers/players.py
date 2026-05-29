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
from services.game_poller import build_teams, _champ_id_to_name, load_champion_mapping
from datetime import datetime, timedelta
import httpx
import asyncio
from fastapi.responses import Response
from deps import get_current_user_optional
from routers.cards import _equipped_stickers_for

from models.user_card import UserCard
from models.card import Card

router = APIRouter(prefix="/players", tags=["players"])

# ─── DDragon ─────────────────────────────────────────────────

_ddragon_version: str | None = None

async def get_ddragon_version() -> str:
    """Récupère et met en cache la dernière version DDragon."""
    global _ddragon_version
    if _ddragon_version:
        return _ddragon_version
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            _ddragon_version = resp.json()[0]
    except Exception:
        _ddragon_version = "16.9.1"  # fallback
    return _ddragon_version

async def ddragon_url(path: str) -> str:
    """Construit une URL DDragon avec la version la plus récente."""
    version = await get_ddragon_version()
    return f"https://ddragon.leagueoflegends.com/cdn/{version}/{path}"

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


@router.get("/proxy/icon")
async def proxy_icon(url: str):
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, headers={"Referer": ""})
            return Response(
                content=resp.content,
                media_type=resp.headers.get("content-type", "image/png"),
            )
    except Exception:
        raise HTTPException(502, "Impossible de récupérer l'icône")


@router.get("/search/autocomplete")
async def autocomplete(q: str, db: Session = Depends(get_db)):
    if not q or len(q) < 2:
        return []
    results = (
        db.query(SearchedPlayer)
        .filter(SearchedPlayer.summoner_name.ilike(f"{q}%"))
        .order_by(SearchedPlayer.last_updated.desc())
        .limit(6)
        .all()
    )
    return [
        {
            "summoner_name":    r.summoner_name,
            "tag_line":         r.tag_line,
            "region":           r.region,
            "tier":             r.tier,
            "rank":             r.rank,
            "profile_icon_url": r.profile_icon_url,
        }
        for r in results
    ]

@router.post("/{region}/{game_name}/{tag_line}/refresh")
async def force_refresh_player(
    region: str,
    game_name: str,
    tag_line: str,
    db: Session = Depends(get_db),
):
    """Force un refresh du cache SearchedPlayer (bypass TTL 10min)."""
    region = region.upper()
    sp = db.query(SearchedPlayer).filter(
        SearchedPlayer.summoner_name == game_name,
        SearchedPlayer.tag_line      == tag_line,
        SearchedPlayer.region        == region,
    ).first()
    if sp:
        # On vide last_updated pour forcer le refetch dans get_player
        sp.last_updated = datetime.utcnow() - timedelta(hours=1)
        db.commit()
    return {"success": True}

from pydantic import BaseModel

class BatchRanksSchema(BaseModel):
    puuids: list[str]

@router.post("/batch-ranks")
async def get_batch_ranks(
    body: BatchRanksSchema,
    db: Session = Depends(get_db),
):
    """
    Retourne les ranks (tier/rank/lp/region/summoner_name/tag_line) pour une liste de puuids.
    Utilise le cache SearchedPlayer en DB.
    """
    if not body.puuids:
        return []
    players = db.query(SearchedPlayer).filter(
        SearchedPlayer.riot_puuid.in_(body.puuids)
    ).all()
    return [
        {
            "puuid":            p.riot_puuid,
            "summoner_name":    p.summoner_name,
            "tag_line":         p.tag_line,
            "region":           p.region,
            "tier":             p.tier,
            "rank":             p.rank,
            "lp":               p.lp,
            "profile_icon_url": p.profile_icon_url,
        }
        for p in players
    ]

@router.get("/{region}/{game_name}/{tag_line}")
async def get_player(
    region: str,
    game_name: str,
    tag_line: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    region = region.upper()

    # ── Lookup / refresh SearchedPlayer ──────────────────────
    # On cherche d'abord par (name, tag, region) pour récupérer un éventuel
    # cache sans appel Riot. Mais l'upsert final se fait toujours par PUUID.
    cached_by_name = db.query(SearchedPlayer).filter(
        SearchedPlayer.summoner_name == game_name,
        SearchedPlayer.tag_line      == tag_line,
        SearchedPlayer.region        == region,
    ).first()

    REFRESH_TTL   = timedelta(minutes=10)
    needs_refresh = (
        not cached_by_name
        or not cached_by_name.last_updated
        or datetime.utcnow() - cached_by_name.last_updated > REFRESH_TTL
    )

    if needs_refresh:
        try:
            account   = await riot.get_account_by_riot_id(game_name, tag_line, region)
            puuid     = account["puuid"]
            summoner  = await riot.get_summoner_by_puuid(puuid, region)
            entries   = await riot.get_rank_by_puuid(puuid, region)
            solo_rank = next(
                (e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"),
                None,
            )
            icon_id          = summoner.get("profileIconId", 1)
            icon_path        = f"img/profileicon/{icon_id}.png"
            profile_icon_url = await ddragon_url(icon_path)

            # ── Upsert par PUUID (source de vérité unique) ────
            player = db.query(SearchedPlayer).filter(
                SearchedPlayer.riot_puuid == puuid
            ).first()

            if player:
                # Mise à jour du cache — le joueur existe déjà (même PUUID)
                player.summoner_name    = game_name
                player.tag_line         = tag_line
                player.region           = region
                player.tier             = solo_rank["tier"]         if solo_rank else None
                player.rank             = solo_rank["rank"]         if solo_rank else None
                player.lp               = solo_rank["leaguePoints"] if solo_rank else 0
                player.profile_icon_url = profile_icon_url
                player.last_updated     = datetime.utcnow()
            else:
                # Nouvelle entrée
                player = SearchedPlayer(
                    riot_puuid       = puuid,
                    summoner_name    = game_name,
                    tag_line         = tag_line,
                    region           = region,
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
        player = cached_by_name

    # ── Live game ─────────────────────────────────────────────
    live_game_raw  = await riot.get_live_game_by_puuid(player.riot_puuid, region)
    live_game_data = None

    if live_game_raw:
        riot_game_id = str(live_game_raw.get("gameId", ""))
        participants = live_game_raw.get("participants", [])

        existing_game = db.query(LiveGame).filter(
            LiveGame.riot_game_id == riot_game_id
        ).first()

        if existing_game:
            # Game déjà en DB : mise à jour durée uniquement
            # (ne pas écraser blue/red_team déjà enrichis par le poller)
            existing_game.duration_seconds = live_game_raw.get("gameLength", 0)
            existing_game.status           = "live"
            db.commit()
            db.refresh(existing_game)
            saved_game = existing_game

        else:
            # Nouvelle game — build_teams avec assign_roles
            if not _champ_id_to_name:
                await load_champion_mapping()

            try:
                blue_team, red_team = await build_teams(
                    participants,
                    pro_puuid_to_role={},
                    region=region,
                )
            except Exception:
                # Fallback minimal si build_teams échoue
                blue_team = _minimal_team(participants, 100)
                red_team  = _minimal_team(participants, 200)

            saved_game = LiveGame(
                searched_player_id = player.id,
                riot_game_id       = riot_game_id,
                queue_type         = str(live_game_raw.get("gameQueueConfigId", "")),
                blue_team          = blue_team,
                red_team           = red_team,
                duration_seconds   = live_game_raw.get("gameLength", 0),
                status             = "live",
                region             = region,
            )
            db.add(saved_game)
            db.commit()
            db.refresh(saved_game)

            from services.game_poller import _compute_and_save_odds
            asyncio.create_task(
                _compute_and_save_odds(saved_game.id, blue_team, red_team, region)
            )

        live_game_data = {
            "id":                saved_game.id,
            "riot_game_id":      saved_game.riot_game_id,
            "gameQueueConfigId": live_game_raw.get("gameQueueConfigId"),
            "gameLength":        live_game_raw.get("gameLength", 0),
            "participants":      participants,
            "blue_team":         saved_game.blue_team,
            "red_team":          saved_game.red_team,
        }

    # ── Match history ─────────────────────────────────────────
    raw_matches = await riot.get_match_history(player.riot_puuid, region, count=10)
    matches     = []
    for m in raw_matches:
        info  = m.get("info", {})
        meta  = m.get("metadata", {})
        parts = info.get("participants", [])
        part  = next((p for p in parts if p["puuid"] == player.riot_puuid), None)
        if not part:
            continue

        # Kill participation (sur les kills de l'équipe)
        team_id    = part["teamId"]
        team_kills = sum(p["kills"] for p in parts if p["teamId"] == team_id) or 1
        kp         = round(((part["kills"] + part["assists"]) / team_kills) * 100)

        # Items (6 items + trinket = item0..item6)
        items = [part.get(f"item{i}", 0) for i in range(7)]

        # Runes (keystone + secondary tree id)
        primary_rune   = None
        secondary_tree = None
        try:
            styles = part.get("perks", {}).get("styles", [])
            if styles:
                primary_rune   = styles[0]["selections"][0]["perk"]
                if len(styles) > 1:
                    secondary_tree = styles[1]["style"]
        except (KeyError, IndexError):
            pass

        # Tous les joueurs de la game (pour expand)
        participants_full = [
            {
                "champion":      p.get("championName", ""),
                "summoner_name": p.get("riotIdGameName") or p.get("summonerName", ""),
                "tag_line":      p.get("riotIdTagline", ""),
                "puuid":         p.get("puuid", ""),
                "team_id":       p.get("teamId", 0),
                "role":          p.get("teamPosition", ""),
                "kills":         p.get("kills", 0),
                "deaths":        p.get("deaths", 0),
                "assists":       p.get("assists", 0),
                "cs":            p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0),
                "items":         [p.get(f"item{i}", 0) for i in range(7)],
                "win":           p.get("win", False),
                "level":         p.get("champLevel", 1),
            }
            for p in parts
        ]

        matches.append({
            # ── Existant ──
            "champion":  part["championName"],
            "role":      part.get("teamPosition", ""),
            "win":       part["win"],
            "kills":     part["kills"],
            "deaths":    part["deaths"],
            "assists":   part["assists"],
            "cs":        part["totalMinionsKilled"] + part.get("neutralMinionsKilled", 0),
            "duration":  info.get("gameDuration", 0),
            "played_at": (
                datetime.utcfromtimestamp(info["gameEndTimestamp"] / 1000).isoformat()
                if info.get("gameEndTimestamp") else None
            ),
            # ── New ──
            "match_id":       meta.get("matchId", ""),
            "queue_id":       info.get("queueId", 0),
            "items":          items,
            "spell1_id":      part.get("summoner1Id", 0),
            "spell2_id":      part.get("summoner2Id", 0),
            "primary_rune":   primary_rune,
            "secondary_tree": secondary_tree,
            "vision_score":   part.get("visionScore", 0),
            "damage_dealt":   part.get("totalDamageDealtToChampions", 0),
            "gold_earned":    part.get("goldEarned", 0),
            "level":          part.get("champLevel", 1),
            "kp":             kp,
            "team_kills":     team_kills,
            "participants":   participants_full,
        })

    overall_stats = _aggregate_overall_stats(matches)

    esports_player = db.query(EsportsPlayer).filter(
        EsportsPlayer.riot_puuid == player.riot_puuid
    ).first()

    pro_player = db.query(ProPlayer).filter(
        ProPlayer.riot_puuid == player.riot_puuid
    ).first()

    team_obj = None
    if esports_player and esports_player.team_code:
        team_obj = db.query(EsportsTeam).filter(
            EsportsTeam.code == esports_player.team_code
        ).first()
    elif pro_player and pro_player.team:
        team_obj = db.query(EsportsTeam).filter(
            EsportsTeam.code == pro_player.team
        ).first()

    pro_data = None
    if pro_player:
        pro_data = {
            "id":            pro_player.id,
            "name":          pro_player.name,
            "team":          pro_player.team,
            "team_code":     esports_player.team_code if esports_player else pro_player.team,
            "role":          pro_player.role,
            "region":        pro_player.region,
            "photo_url":     pro_player.photo_url,
            "team_logo_url": pro_player.team_logo_url or (team_obj.logo_url if team_obj else None),
            "accent_color":  pro_player.accent_color  or (team_obj.color   if team_obj else None),
        }
    elif esports_player:
        pro_data = {
            "id":            esports_player.id,
            "name":          esports_player.name,
            "team":          esports_player.team_code,
            "role":          esports_player.role,
            "region":        esports_player.region,
            "photo_url":     esports_player.photo_url,
            "team_logo_url": team_obj.logo_url if team_obj else None,
            "accent_color":  team_obj.color    if team_obj else None,
        }

    return {
        "player": {
            "id":               player.id,
            "summoner_name":    player.summoner_name,
            "tag_line":         player.tag_line,
            "region":           player.region,
            "tier":             player.tier,
            "rank":             player.rank,
            "lp":               player.lp,
            "profile_icon_url": player.profile_icon_url,
            "riot_puuid":       player.riot_puuid,
        },
        "live_game":         live_game_data,
        "match_history":     matches,
        "overall_stats":     overall_stats,
        "pro_player":        pro_data,
        "junglegap_profile": _build_junglegap_profile(
            player.riot_puuid, db, current_user.id if current_user else None
        ),
    }


def _minimal_team(participants: list, team_id: int) -> list:
    """Fallback minimal si build_teams échoue — garde les données brutes."""
    team   = [p for p in participants if p.get("teamId") == team_id]
    result = []
    for p in team:
        champ_name = (p.get("championName") or "").strip()
        spells     = {p.get("spell1Id", 0), p.get("spell2Id", 0)}
        result.append({
            "puuid":        (p.get("puuid") or "").strip() or None,
            "summonerName": extract_pseudo(p, champ_name),
            "championId":   p.get("championId"),
            "championName": champ_name,
            "teamId":       team_id,
            "role":         "JUNGLE" if 11 in spells else None,
            "spell1Id":     p.get("spell1Id"),
            "spell2Id":     p.get("spell2Id"),
        })
    return result

# ─── Helpers JungleGap profile ──────────────────────────────

def _build_junglegap_profile(puuid: str, db: Session, current_user_id: int | None = None) -> dict | None:
    """Cherche un User lié à ce puuid (via riot_accounts ou User.riot_puuid legacy)."""
    user = (
        db.query(User)
        .join(RiotAccount, RiotAccount.user_id == User.id, isouter=True)
        .filter((RiotAccount.riot_puuid == puuid) | (User.riot_puuid == puuid))
        .first()
    )
    if not user:
        return None

    bets       = db.query(Bet).filter(Bet.user_id == user.id).all()
    resolved   = [b for b in bets if b.status in ("won", "lost")]
    won        = [b for b in resolved if b.status == "won"]
    total_wag  = sum(b.amount for b in bets)
    total_won_ = sum(b.payout or 0 for b in won)
    winrate    = round(len(won) / len(resolved) * 100) if resolved else None

    streak = 0
    for b in sorted(resolved, key=lambda x: x.created_at, reverse=True):
        if b.status == "won": streak += 1
        else: break

    equipped_title = None
    if user.equipped_title_id:
        title_card = db.query(Card).filter(Card.id == user.equipped_title_id).first()
        if title_card and title_card.title_text:
            equipped_title = title_card.title_text

    return {
        "id":             user.id,
        "username":       user.username,
        "avatar_url":     user.avatar_url,
        "coins":          user.coins,
        "equipped_title": equipped_title,
        "is_owner":       current_user_id is not None and user.id == current_user_id,
        "favorite_team": {
            "name":  user.favorite_team_name,
            "logo":  user.favorite_team_logo,
            "color": user.favorite_team_color,
        } if user.favorite_team_name else None,
        "equipped_stickers": _equipped_stickers_for(db, user.id),
        "bet_stats": {
            "total":   len(bets),
            "won":     len(won),
            "lost":    len(resolved) - len(won),
            "winrate": winrate,
            "streak":  streak,
            "net":     total_won_ - total_wag,
        },
    }


# ─── Helpers Match history aggregation ──────────────────────

ROLE_MAP_RIOT = {"TOP": "TOP", "JUNGLE": "JUNGLE", "MIDDLE": "MID", "BOTTOM": "ADC", "UTILITY": "SUPPORT"}

def _aggregate_overall_stats(matches: list) -> dict:
    """Calcule winrate global + perf par rôle sur les matches fournis."""
    if not matches:
        return {"total": 0, "wins": 0, "losses": 0, "winrate": 0, "avg_kda": 0, "avg_cs_min": 0, "by_role": {}}

    total = len(matches)
    wins  = sum(1 for m in matches if m["win"])

    sum_k = sum(m["kills"]   for m in matches)
    sum_d = sum(m["deaths"]  for m in matches)
    sum_a = sum(m["assists"] for m in matches)
    sum_cs = sum(m["cs"] for m in matches)
    sum_dur = sum(m["duration"] for m in matches) or 1

    avg_kda    = round((sum_k + sum_a) / max(sum_d, 1), 2)
    avg_cs_min = round(sum_cs / (sum_dur / 60), 1)

    # Par rôle
    by_role = {}
    for m in matches:
        role = ROLE_MAP_RIOT.get(m["role"], m["role"] or "FILL")
        if role not in by_role:
            by_role[role] = {"games": 0, "wins": 0, "k": 0, "d": 0, "a": 0}
        r = by_role[role]
        r["games"]   += 1
        r["wins"]    += int(m["win"])
        r["k"]       += m["kills"]
        r["d"]       += m["deaths"]
        r["a"]       += m["assists"]

    by_role_out = {
        role: {
            "games":   r["games"],
            "wins":    r["wins"],
            "winrate": round((r["wins"] / r["games"]) * 100),
            "kda":     round((r["k"] + r["a"]) / max(r["d"], 1), 2),
        }
        for role, r in by_role.items()
    }

    return {
        "total":      total,
        "wins":       wins,
        "losses":     total - wins,
        "winrate":    round((wins / total) * 100),
        "avg_kda":    avg_kda,
        "avg_cs_min": avg_cs_min,
        "by_role":    by_role_out,
    }