
import logging
from sqlalchemy.orm import Session
from database import SessionLocal
from models.esports_team import EsportsTeam
from models.esports_player import EsportsPlayer
from models.pro_player import ProPlayer
from services import lolesports

logger = logging.getLogger(__name__)

TEAM_COLORS = {
    "T1":   "#b8952a", "GEN":  "#c89b3c", "HLE":  "#e03030", "KT":   "#e03030",
    "DK":   "#00b4d8", "NS":   "#e04040", "KRX":  "#3a7bd5", "BRO":  "#9b59b6",
    "DNS":  "#6b7280", "BFX":  "#9b59b6",
    "G2":   "#ff6b35", "FNC":  "#ff7d00", "KC":   "#0099ff", "MKOI": "#00c896",
    "GX":   "#e63946", "VIT":  "#f5c518", "SK":   "#22c55e", "TH":   "#7c3aed",
    "NAVI": "#f5c518", "SHFT": "#4b5563", "LR":   "#ef4444", "KCB":  "#0099ff",
    "C9":   "#00b4d8", "TL":   "#c89b3c", "NRG":  "#ef4444", "100":  "#f59e0b",
    "EG":   "#3a7bd5", "FLY":  "#a855f7", "DIG":  "#22c55e", "IMT":  "#ef4444",
    "BLG":  "#ef4444", "JDG":  "#c89b3c", "NIP":  "#ec4899", "EDG":  "#ef4444",
    "WBG":  "#3a7bd5", "OMG":  "#f97316", "LNG":  "#65BD62", "AL":   "#6366f1",
}

TEAM_SLUGS_BY_REGION = {
    "LCK": [
        "t1", "geng", "hanwha-life-esports", "kt-rolster",
        "nongshim-redforce", "drx", "fearx",
        # dplus et dn-soopers slugs à confirmer
    ],
    "LEC": [
        "g2-esports", "fnatic", "karmine-corp", "team-vitality",
        "team-heretics-lec", "giantx", "movistar-koi", "sk-gaming",
        "natus-vincere", "team-bds", "los-ratones", "karmine-corp-blue",
    ],
    "LCS": [
        "cloud9", "team-liquid", "100-thieves",
        "evil-geniuses", "flyquest", "dignitas",
    ],
    "LPL": [
        "bilibili-gaming", "jdg", "edward-gaming",
        "weibo-gaming", "royal-never-give-up", "top-esports",
    ],
    "LFL": [
        "vitalitybee", "solary", "joblife", "zephyr",
        "karmine-corp-blue", "gameward", "ici-japon-corp",
        "tln-pirates", "galions", "zyb",
    ],
}

ALL_TEAM_SLUGS = [slug for slugs in TEAM_SLUGS_BY_REGION.values() for slug in slugs]

def _map_role(role_str: str) -> str:
    mapping = {
        "top":     "TOP",
        "jungle":  "JUNGLE",
        "mid":     "MID",
        "bot":     "ADC",
        "adc":     "ADC",
        "sup":     "SUPPORT",
        "support": "SUPPORT",
        "bottom":  "ADC",
    }
    return mapping.get((role_str or "").lower(), (role_str or "").upper())

async def sync_team(slug: str, region: str, db: Session) -> int:
    """Sync une équipe + son roster. Retourne le nb de joueurs syncés."""
    try:
        data  = await lolesports.get_teams(slug)
        teams = data.get("data", {}).get("teams", [])
        if not teams:
            logger.warning(f"[sync] {slug}: aucune donnée retournée")
            return 0

        team_data = teams[0]
        code      = team_data.get("code", "").upper()
        name      = team_data.get("name", "")
        logo_url  = team_data.get("image", "")
        api_id    = team_data.get("id", "")

        # Upsert EsportsTeam
        et = db.query(EsportsTeam).filter(EsportsTeam.slug == slug).first()
        if not et:
            et = db.query(EsportsTeam).filter(EsportsTeam.code == code).first()
        if et:
            et.name         = name
            et.logo_url     = logo_url
            et.api_id       = api_id
            et.slug         = slug
            et.code         = code
            et.region       = region
            et.accent_color = TEAM_COLORS.get(code, "#00e5ff")
        else:
            et = EsportsTeam(
                api_id       = api_id,
                slug         = slug,
                code         = code,
                name         = name,
                logo_url     = logo_url,
                region       = region,
                accent_color = TEAM_COLORS.get(code, "#00e5ff"),
            )
            db.add(et)

        db.flush()

        # Sync des joueurs du roster
        players_data = team_data.get("players", [])
        synced       = 0

        for p in players_data:
            p_id        = p.get("id", "")
            summoner    = p.get("summonerName", "") or p.get("name", "")
            first_name  = p.get("firstName", "")
            last_name   = p.get("lastName", "")
            role_raw    = p.get("role", "")
            photo       = p.get("image", "")
            is_starter  = p.get("isStarter", True)

            role = _map_role(role_raw)

            # Upsert EsportsPlayer par api_id
            ep = db.query(EsportsPlayer).filter(EsportsPlayer.api_id == p_id).first()
            if ep:
                ep.summoner_name = summoner
                ep.first_name    = first_name
                ep.last_name     = last_name
                ep.role          = role
                ep.photo_url     = photo
                ep.team_code     = code
                ep.team_name     = name
                ep.region        = region
                ep.is_starter    = is_starter
            else:
                ep = EsportsPlayer(
                    api_id        = p_id,
                    summoner_name = summoner,
                    first_name    = first_name,
                    last_name     = last_name,
                    role          = role,
                    photo_url     = photo,
                    team_code     = code,
                    team_name     = name,
                    region        = region,
                    is_starter    = is_starter,
                )
                db.add(ep)

            # ── Sync cascade vers ProPlayer ──────────────────────────
            # Si un ProPlayer existe avec le même riot_puuid → on met à jour sa photo et son logo
            if ep.riot_puuid:
                pro = db.query(ProPlayer).filter(ProPlayer.riot_puuid == ep.riot_puuid).first()
                if pro:
                    if photo and not pro.photo_url:
                        pro.photo_url = photo
                    pro.team         = code
                    pro.role         = role
                    pro.region       = region
                    pro.accent_color = TEAM_COLORS.get(code, pro.accent_color or "#00e5ff")
                    pro.team_logo_url = logo_url

            synced += 1

        db.commit()
        logger.info(f"[sync] {code} ({region}): {synced} joueurs syncés")
        return synced

    except Exception as e:
        db.rollback()
        logger.error(f"[sync] erreur {slug}: {e}")
        return 0

async def sync_all_teams():
    """
    Sync depuis les standings DB — on connaît déjà les codes et images.
    On fetch getTeams pour enrichir avec le roster des joueurs.
    """
    db = SessionLocal()
    total = 0
    try:
        from models.esports_team_stats import EsportsTeamStats

        # Récupérer tous les codes d'équipes connus depuis les standings
        all_stats = db.query(EsportsTeamStats).all()
        # Dédupliquer par code
        seen_codes = {}
        for s in all_stats:
            if s.team_code not in seen_codes:
                seen_codes[s.team_code] = s

        logger.info(f"[sync] {len(seen_codes)} équipes à syncer depuis standings")

        for code, stats in seen_codes.items():
            # On essaie d'abord le slug lowercase du code, puis quelques variantes
            slug_candidates = [
                code.lower(),
                code.lower().replace(" ", "-"),
            ]

            synced = False
            for slug in slug_candidates:
                try:
                    data  = await get_teams_by_slug(slug)
                    teams = data.get("data", {}).get("teams", [])
                    if teams:
                        await _upsert_team_from_api(teams[0], stats.league_slug, db)
                        total += 1
                        synced = True
                        break
                except Exception:
                    continue

            if not synced:
                # Fallback : créer EsportsTeam depuis les standings sans roster
                await _upsert_team_from_standings(stats, db)
                total += 1

        logger.info(f"[sync] ✅ Sync complète — {total} équipes traitées")
    except Exception as e:
        logger.error(f"[sync] ❌ Erreur sync globale: {e}")
    finally:
        db.close()

    await sync_photos_to_pro_players()
    


async def get_teams_by_slug(slug: str) -> dict:
    import httpx
    ESPORTS_API = "https://esports-api.lolesports.com/persisted/gw"
    API_KEY     = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.get(
            f"{ESPORTS_API}/getTeams",
            headers={"x-api-key": API_KEY},
            params={"hl": "fr-FR", "id": slug},
        )
        r.raise_for_status()
        return r.json()


async def _upsert_team_from_api(team_data: dict, region: str, db: Session):
    code     = team_data.get("code", "").upper()
    name     = team_data.get("name", "")
    logo_url = team_data.get("image", "")
    api_id   = team_data.get("id", "")
    slug     = team_data.get("slug", "")

    # Upsert EsportsTeam
    et = db.query(EsportsTeam).filter(EsportsTeam.code == code).first()
    if et:
        et.name     = name
        et.logo_url = logo_url
        et.api_id   = api_id
        et.slug     = slug
        et.region   = region
        et.accent_color = TEAM_COLORS.get(code, et.accent_color or "#00e5ff")
    else:
        et = EsportsTeam(
            api_id=api_id, slug=slug, code=code, name=name,
            logo_url=logo_url, region=region,
            accent_color=TEAM_COLORS.get(code, "#00e5ff"),
        )
        db.add(et)
    db.flush()

    # Sync joueurs
    for p in team_data.get("players", []):
        p_id      = p.get("id", "")
        summoner  = p.get("summonerName", "")
        role      = _map_role(p.get("role", ""))
        photo     = p.get("image", "")
        is_default_photo = "default-headshot" in photo

        ep = db.query(EsportsPlayer).filter(EsportsPlayer.api_id == p_id).first()
        if ep:
            ep.summoner_name = summoner
            ep.first_name    = p.get("firstName", "")
            ep.last_name     = p.get("lastName", "")
            ep.role          = role
            ep.team_code     = code
            ep.team_name     = name
            ep.region        = region
            if not is_default_photo:
                ep.photo_url = photo
        else:
            ep = EsportsPlayer(
                api_id        = p_id,
                summoner_name = summoner,
                first_name    = p.get("firstName", ""),
                last_name     = p.get("lastName", ""),
                role          = role,
                photo_url     = None if is_default_photo else photo,
                team_code     = code,
                team_name     = name,
                region        = region,
            )
            db.add(ep)

        # Cascade vers ProPlayer
        if ep.riot_puuid:
            pro = db.query(ProPlayer).filter(ProPlayer.riot_puuid == ep.riot_puuid).first()
            if pro:
                if not is_default_photo and photo:
                    pro.photo_url = photo
                pro.team          = code
                pro.role          = role
                pro.region        = region
                pro.accent_color  = TEAM_COLORS.get(code, pro.accent_color or "#00e5ff")
                pro.team_logo_url = logo_url

    db.commit()
    logger.info(f"[sync] ✅ {code} ({region}): {len(team_data.get('players', []))} joueurs")


async def _upsert_team_from_standings(stats, db: Session):
    """Fallback : crée EsportsTeam depuis standings sans roster."""
    code = stats.team_code
    et   = db.query(EsportsTeam).filter(EsportsTeam.code == code).first()
    if not et:
        et = EsportsTeam(
            code         = code,
            name         = stats.team_name or code,
            logo_url     = stats.team_image,
            region       = stats.league_slug.upper(),
            accent_color = TEAM_COLORS.get(code, "#00e5ff"),
        )
        db.add(et)
    else:
        if stats.team_image and not et.logo_url:
            et.logo_url = stats.team_image
    db.commit()
    logger.info(f"[sync] 📦 {code}: créé depuis standings (pas de roster API)")

async def sync_photos_to_pro_players():
    db = SessionLocal()
    try:
        pros    = db.query(ProPlayer).filter(ProPlayer.is_active == True).all()
        updated = 0

        for pro in pros:

            # ── Logo + accent_color depuis EsportsTeam ────────────────
            if pro.team:
                team_obj = db.query(EsportsTeam).filter(
                    EsportsTeam.code == pro.team.upper()
                ).first()
                if team_obj:
                    if team_obj.logo_url:
                        pro.team_logo_url = team_obj.logo_url
                    if team_obj.accent_color:
                        pro.accent_color = team_obj.accent_color

            # ── Photo joueur ──────────────────────────────────────────

            # 1. Match direct par riot_puuid
            if pro.riot_puuid:
                ep = db.query(EsportsPlayer).filter(
                    EsportsPlayer.riot_puuid == pro.riot_puuid
                ).first()
                if ep and ep.photo_url and "default-headshot" not in ep.photo_url:
                    pro.photo_url = ep.photo_url
                    updated += 1
                    continue

            # 2. Match par summonerName exact (ilike)
            if pro.name:
                ep = db.query(EsportsPlayer).filter(
                    EsportsPlayer.summoner_name.ilike(pro.name)
                ).first()
                if ep and ep.photo_url and "default-headshot" not in ep.photo_url:
                    pro.photo_url = ep.photo_url
                    if ep.riot_puuid and not pro.riot_puuid:
                        already = db.query(ProPlayer).filter(
                            ProPlayer.riot_puuid == ep.riot_puuid,
                            ProPlayer.id         != pro.id,
                        ).first()
                        if not already:
                            pro.riot_puuid = ep.riot_puuid
                    updated += 1
                    continue

            # 3. Match par team_code + role — seulement si candidat unique
            if pro.team and pro.role:
                candidates = db.query(EsportsPlayer).filter(
                    EsportsPlayer.team_code == pro.team.upper(),
                    EsportsPlayer.role.ilike(pro.role),
                    EsportsPlayer.is_active == True,
                ).all()
                with_photo = [
                    c for c in candidates
                    if c.photo_url and "default-headshot" not in c.photo_url
                ]
                if len(with_photo) == 1:
                    pro.photo_url = with_photo[0].photo_url
                    if with_photo[0].riot_puuid and not pro.riot_puuid:
                        already = db.query(ProPlayer).filter(
                            ProPlayer.riot_puuid == with_photo[0].riot_puuid,
                            ProPlayer.id         != pro.id,
                        ).first()
                        if not already:
                            pro.riot_puuid = with_photo[0].riot_puuid
                    updated += 1

        db.commit()
        logger.info(f"[sync_photos] ✅ {updated}/{len(pros)} pros mis à jour")

    except Exception as e:
        logger.error(f"[sync_photos] ❌ Erreur: {e}")
        db.rollback()
    finally:
        db.close()