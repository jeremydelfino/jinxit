from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models.user import User
from models.bet import Bet
from deps import get_current_user
from models.riot_account import RiotAccount
from services import riot
import random
from routers.cards import _equipped_stickers_for

router = APIRouter(prefix="/profile", tags=["profile"])

# ─── Helpers ────────────────────────────────────────────────

def _get_riot_player(user: User, db: Session) -> dict | None:
    if not user.riot_puuid:
        return None
    from models.player import SearchedPlayer
    sp = db.query(SearchedPlayer).filter(
        SearchedPlayer.riot_puuid == user.riot_puuid
    ).first()
    if not sp:
        return None
    return {
        "summoner_name":    sp.summoner_name,
        "tag_line":         sp.tag_line,
        "region":           sp.region,
        "tier":             sp.tier,
        "rank":             sp.rank,
        "lp":               sp.lp,
        "profile_icon_url": sp.profile_icon_url,
    }

def _get_bet_stats(user_id: int, db: Session) -> dict:
    bets = db.query(Bet).filter(Bet.user_id == user_id).all()
    total      = len(bets)
    resolved   = [b for b in bets if b.status in ("won", "lost")]
    won        = [b for b in resolved if b.status == "won"]
    lost       = [b for b in resolved if b.status == "lost"]
    pending    = [b for b in bets if b.status == "pending"]
    total_wagered = sum(b.amount for b in bets)
    total_won     = sum(b.payout or 0 for b in won)
    net           = total_won - total_wagered
    winrate       = round(len(won) / len(resolved) * 100) if resolved else None

    # Streak actuelle (wins consécutifs depuis le dernier pari résolu)
    streak = 0
    for b in sorted(resolved, key=lambda x: x.created_at, reverse=True):
        if b.status == "won":
            streak += 1
        else:
            break

    return {
        "total":          total,
        "won":            len(won),
        "lost":           len(lost),
        "pending":        len(pending),
        "winrate":        winrate,
        "total_wagered":  total_wagered,
        "total_won":      total_won,
        "net":            net,
        "streak":         streak,
    }
# ─── Helper : migration auto user.riot_puuid → riot_accounts ───

async def _ensure_riot_accounts_migrated(user: User, db: Session):
    """
    Migration au vol : si l'user a un riot_puuid (ancien système) mais aucune
    entrée dans riot_accounts, on crée l'entrée à la volée. Idempotent : ne
    fait rien si déjà migré. Appelé une seule fois par user (au 1er accès au profil).
    """
    if not user.riot_puuid:
        return

    existing_count = db.query(RiotAccount).filter(RiotAccount.user_id == user.id).count()
    if existing_count > 0:
        return  # déjà migré

    # Récupère les infos Riot via le puuid
    try:
        from models.player import SearchedPlayer

        # 1) Tente de récupérer depuis le cache local
        cached = db.query(SearchedPlayer).filter(
            SearchedPlayer.riot_puuid == user.riot_puuid
        ).first()

        if cached:
            new_account = RiotAccount(
                user_id          = user.id,
                riot_puuid       = user.riot_puuid,
                summoner_name    = cached.summoner_name,
                tag_line         = cached.tag_line,
                region           = cached.region,
                profile_icon_url = cached.profile_icon_url,
                tier             = cached.tier,
                rank             = cached.rank,
                lp               = cached.lp,
                is_primary       = True,
            )
            db.add(new_account)
            db.commit()
            return

        # 2) Pas de cache → on crée une entrée minimale qu'on enrichira plus tard
        # On laisse summoner_name vide, l'user pourra "refresh" via la page joueur
        new_account = RiotAccount(
            user_id    = user.id,
            riot_puuid = user.riot_puuid,
            is_primary = True,
        )
        db.add(new_account)
        db.commit()

    except Exception as e:
        db.rollback()
        # Ne bloque pas le chargement du profil si la migration échoue
        print(f"[migration] Échec migration riot_account user {user.id}: {e}")


def _serialize_riot_accounts(user: User, db: Session) -> list:
    """Sérialise les riot_accounts d'un user en JSON pour le frontend."""
    accounts = (
        db.query(RiotAccount)
        .filter(RiotAccount.user_id == user.id)
        .order_by(RiotAccount.is_primary.desc(), RiotAccount.created_at.asc())
        .all()
    )
    return [
        {
            "id":               ra.id,
            "summoner_name":    ra.summoner_name,
            "tag_line":         ra.tag_line,
            "region":           ra.region,
            "profile_icon_url": ra.profile_icon_url,
            "tier":             ra.tier,
            "rank":             ra.rank,
            "lp":               ra.lp,
            "is_primary":       ra.is_primary,
        }
        for ra in accounts
    ]
# ─── GET /me ────────────────────────────────────────────────

@router.get("/me")
async def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Migration au vol (idempotent)
    await _ensure_riot_accounts_migrated(current_user, db)

    equipped_title_text = None
    if current_user.equipped_title_id:
        from models.card import Card
        title_card = db.query(Card).filter(Card.id == current_user.equipped_title_id).first()
        if title_card:
            equipped_title_text = title_card.title_text or title_card.name

    return {
        "id":            current_user.id,
        "username":      current_user.username,
        "email":         current_user.email,
        "coins":         current_user.coins,
        "avatar_url":    current_user.avatar_url,
        "riot_linked":   current_user.riot_puuid is not None,
        "riot_puuid":    current_user.riot_puuid,
        "last_daily":    current_user.last_daily,
        "riot_player":   _get_riot_player(current_user, db),
        "riot_accounts": _serialize_riot_accounts(current_user, db),
        "bet_stats":     _get_bet_stats(current_user.id, db),
        "favorite_team": {
            "name":  current_user.favorite_team_name,
            "logo":  current_user.favorite_team_logo,
            "color": current_user.favorite_team_color,
        } if current_user.favorite_team_name else None,
        "social": {
            "discord":   {
                "id":          current_user.discord_id,
                "username":    current_user.discord_username,
                "verified_at": current_user.discord_verified_at,
            } if current_user.discord_id else None,
            "twitch":    {
                "username":    current_user.twitch_username,
                "verified_at": current_user.twitch_verified_at,
            } if current_user.twitch_id else None,
            "x_handle":         current_user.x_handle,
            "instagram_handle": current_user.instagram_handle,
        },
        "equipped_stickers": _equipped_stickers_for(db, current_user.id),
        "equipped_title_id":   current_user.equipped_title_id,
        "equipped_title_text": equipped_title_text,
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

    equipped_title_text = None
    if user.equipped_title_id:
        from models.card import Card
        title_card = db.query(Card).filter(Card.id == user.equipped_title_id).first()
        if title_card:
            equipped_title_text = title_card.title_text or title_card.name

    return {
        "id":            user.id,
        "username":      user.username,
        "avatar_url":    user.avatar_url,
        "coins":         user.coins,
        "riot_linked":   user.riot_puuid is not None,
        "riot_player":   _get_riot_player(user, db),
        "riot_accounts": _serialize_riot_accounts(user, db),
        "bet_stats":     _get_bet_stats(user.id, db),
        "favorite_team": {
            "name":  user.favorite_team_name,
            "logo":  user.favorite_team_logo,
            "color": user.favorite_team_color,
        } if user.favorite_team_name else None,
        "social": {
            "discord":   {"id": user.discord_id, "username": user.discord_username} if user.discord_id else None,
            "twitch":    {"username": user.twitch_username} if user.twitch_id else None,
            "x_handle":         user.x_handle,
            "instagram_handle": user.instagram_handle,
        },
        "equipped_stickers": _equipped_stickers_for(db, user.id),
        "equipped_title_id":   user.equipped_title_id,
        "equipped_title_text": equipped_title_text,
    }

# ─── POST /set-team ──────────────────────────────────────────

class SetTeamSchema(BaseModel):
    name:  str
    logo:  str | None = None
    color: str | None = None

@router.post("/set-team")
def set_favorite_team(
    body: SetTeamSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.favorite_team_name  = body.name or None
    current_user.favorite_team_logo  = body.logo or None
    current_user.favorite_team_color = body.color or None
    db.commit()
    return {"success": True, "favorite_team": {"name": body.name, "logo": body.logo, "color": body.color}}

# ─── POST /link-riot/init ────────────────────────────────────

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
    if db.query(RiotAccount).filter(RiotAccount.user_id == current_user.id).count() >= 3:
        raise HTTPException(400, "Tu as déjà 3 comptes Riot liés")

    try:
        account = await riot.get_account_by_riot_id(body.game_name, body.tag_line, body.region)
    except Exception:
        raise HTTPException(400, "Riot ID introuvable — vérifie le pseudo et le tag")

    puuid = account["puuid"]

    # Vérifie que ce puuid n'est pas déjà lié à un autre user
    existing = (
        db.query(RiotAccount)
        .filter(RiotAccount.riot_puuid == puuid, RiotAccount.user_id != current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(400, "Ce compte Riot est déjà lié à un autre compte JungleGap")

    icon_id = random.randint(1, 28)
    is_primary = db.query(RiotAccount).filter(RiotAccount.user_id == current_user.id).count() == 0

    # Crée ou réutilise un RiotAccount pending pour ce puuid
    pending_ra = (
        db.query(RiotAccount)
        .filter(RiotAccount.user_id == current_user.id, RiotAccount.riot_puuid == puuid)
        .first()
    )
    if pending_ra:
        pending_ra.verification_icon = icon_id
    else:
        pending_ra = RiotAccount(
            user_id           = current_user.id,
            riot_puuid        = puuid,
            summoner_name     = body.game_name,
            tag_line          = body.tag_line,
            region            = body.region.upper(),
            is_primary        = is_primary,
            verification_icon = icon_id,
        )
        db.add(pending_ra)

    db.commit()
    db.refresh(pending_ra)

    return {
        "riot_account_id": pending_ra.id,
        "icon_id":         icon_id,
        "icon_url":        f"https://ddragon.leagueoflegends.com/cdn/16.7.1/img/profileicon/{icon_id}.png",
        "game_name":       body.game_name,
        "tag_line":        body.tag_line,
        "region":          body.region.upper(),
    }

# ─── POST /link-riot/verify ──────────────────────────────────

class VerifyRiotSchema(BaseModel):
    riot_account_id: int

@router.post("/link-riot/verify")
async def link_riot_verify(
    body: VerifyRiotSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ra = db.query(RiotAccount).filter(
        RiotAccount.id      == body.riot_account_id,
        RiotAccount.user_id == current_user.id,
    ).first()
    if not ra or not ra.verification_icon:
        raise HTTPException(400, "Session de vérification introuvable, recommence")

    try:
        summoner = await riot.get_summoner_by_puuid(ra.riot_puuid, ra.region)
    except Exception:
        raise HTTPException(400, "Impossible de contacter Riot, réessaie")

    if summoner["profileIconId"] != ra.verification_icon:
        raise HTTPException(
            400,
            f"Mauvaise icône (actuelle : {summoner['profileIconId']}, attendue : {ra.verification_icon})"
        )

    # Vérification OK — enrichit le compte et le marque comme vérifié
    ra.verification_icon  = None
    ra.summoner_name      = summoner.get("name") or ra.summoner_name
    ra.profile_icon_url   = f"https://ddragon.leagueoflegends.com/cdn/16.7.1/img/profileicon/{summoner['profileIconId']}.png"
    db.commit()
    db.refresh(ra)

    return {
        "riot_account": {
            "id":               ra.id,
            "summoner_name":    ra.summoner_name,
            "tag_line":         ra.tag_line,
            "region":           ra.region,
            "profile_icon_url": ra.profile_icon_url,
            "tier":             ra.tier,
            "rank":             ra.rank,
            "lp":               ra.lp,
            "is_primary":       ra.is_primary,
        }
    }