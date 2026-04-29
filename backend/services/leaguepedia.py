"""
services/leaguepedia.py
Client pour l'API Cargo de Leaguepedia (lol.fandom.com).
Source primaire pour les rosters des équipes esports — bien plus à jour
que l'API officielle lolesports getTeams.

Doc : https://lol.fandom.com/wiki/Special:CargoTables
"""
import logging
import httpx

logger = logging.getLogger(__name__)

CARGO_URL = "https://lol.fandom.com/api.php"
TIMEOUT   = 15


async def _cargo_query(params: dict) -> list[dict]:
    """
    Wrapper générique pour cargoquery. Retourne une liste de dicts.
    Format Leaguepedia : { "cargoquery": [ { "title": {...} }, ... ] }
    """
    full_params = {
        "action":            "cargoquery",
        "format":            "json",
        "formatversion":     "2",
        "limit":             "100",
        **params,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(CARGO_URL, params=full_params)
        r.raise_for_status()
        data = r.json()

    rows = data.get("cargoquery", [])
    return [row.get("title", {}) for row in rows]


def _name_variants(team_name: str) -> list[str]:
    """
    Génère des variantes plausibles d'un nom d'équipe pour matcher Leaguepedia.
    Ex: 'T1Academy' → ['T1Academy', 'T1 Academy', 'T1.Academy']
    """
    n = team_name.strip()
    variants = {n, n.replace(" ", ""), n.replace(".", " ").strip()}
    # Insère un espace avant 'Academy' / 'Challengers' / 'Youth'
    for suffix in ("Academy", "Challengers", "Youth", "Esports", "Gaming"):
        if suffix in n and f" {suffix}" not in n:
            variants.add(n.replace(suffix, f" {suffix}"))
    return list(variants)


async def get_team_roster(team_name: str) -> list[dict] | None:
    """
    Récupère le roster ACTUEL d'une équipe via la table Players.
    Essaie plusieurs variantes du nom si la première échoue.

    Retourne une liste de dicts :
      [
        { "id": "Faker", "name": "Lee Sang-hyeok", "role": "Mid",
          "country": "South Korea", "image": "Faker.jpg", "team": "T1" },
        ...
      ]
    Ou None si aucune variante ne matche.
    """
    variants = _name_variants(team_name)
    for variant in variants:
        rows = await _cargo_query({
            "tables": "Players",
            "fields": "Players.ID=id,Players.Name=name,Players.Role=role,"
                      "Players.Country=country,Players.Image=image,Players.Team=team,"
                      "Players.IsRetired=is_retired",
            "where":  f'Players.Team = "{variant}" AND (Players.IsRetired IS NULL OR Players.IsRetired = "0")',
            "order_by": "Players.Role",
        })
        if rows:
            logger.info(f"[leaguepedia] roster trouvé via variante '{variant}' ({len(rows)} joueurs)")
            return rows

    logger.warning(f"[leaguepedia] aucun roster pour '{team_name}' (variantes essayées : {variants})")
    return None


async def get_player_image_url(image_name: str) -> str:
    """
    Convertit un nom d'image Leaguepedia (ex: 'Faker.jpg') en URL directe.
    Utilise Special:FilePath qui redirige vers l'URL CDN actuelle.
    """
    if not image_name:
        return ""
    # Encode juste les espaces — Special:FilePath gère le reste
    safe = image_name.replace(" ", "_")
    return f"https://lol.fandom.com/wiki/Special:FilePath/{safe}"


async def get_team_logo_url(team_name: str) -> str:
    """Récupère l'URL du logo d'une équipe."""
    variants = _name_variants(team_name)
    for variant in variants:
        rows = await _cargo_query({
            "tables": "Teams",
            "fields": "Teams.Image=image",
            "where":  f'Teams.Name = "{variant}"',
            "limit":  "1",
        })
        if rows and rows[0].get("image"):
            return await get_player_image_url(rows[0]["image"])
    return ""