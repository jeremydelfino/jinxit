"""
Résout n'importe quel nom de champion (Leaguepedia, Riot, DDragon) vers l'ID DDragon
canonique utilisé par le front. Cache 24h, fetch DDragon en stdlib (zéro dépendance).
"""
from __future__ import annotations
import json, logging, re, time, urllib.request

logger = logging.getLogger(__name__)

_DDRAGON_VERSION_FALLBACK = "15.10.1"
_cache = {"map": None, "ts": 0.0}
_TTL = 86400

# Filet pour les formes que DDragon ne donne pas directement
ALIASES = {"nunuwillump": "Nunu", "renataglasc": "Renata", "wukong": "MonkeyKing"}

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def _fetch_json(url: str, timeout: int = 10):
    req = urllib.request.Request(url, headers={"User-Agent": "junglegap"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def _build_map() -> dict:
    try:
        version = _fetch_json("https://ddragon.leagueoflegends.com/api/versions.json")[0]
    except Exception:
        version = _DDRAGON_VERSION_FALLBACK
    data = _fetch_json(f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json")
    m = {}
    for cid, c in data["data"].items():
        m[_norm(cid)] = cid          # forme ID  ("XinZhao")
        m[_norm(c["name"])] = cid     # forme nom ("Wukong"→MonkeyKing, "Renata Glasc"→Renata)
    m.update(ALIASES)
    return m

def _get_map() -> dict:
    if _cache["map"] and time.time() - _cache["ts"] < _TTL:
        return _cache["map"]
    try:
        _cache["map"] = _build_map(); _cache["ts"] = time.time()
    except Exception as e:
        logger.warning(f"[naming] build map échoué : {e}")
    return _cache["map"] or {}

def to_ddragon_id(name: str) -> str:
    """Renvoie l'ID DDragon, ou le nom d'origine si introuvable."""
    if not name:
        return name
    return _get_map().get(_norm(name), name)