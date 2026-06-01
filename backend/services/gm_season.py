"""
services/gm_season.py
Génération d'une saison Myceo : calendrier round-robin (toi + IA LFL) + classement initial.
3 splits/an → year/split dérivés du nombre de saisons déjà créées par la franchise.
"""
from sqlalchemy.orm import Session

from models.gm_ai_team import GmAiTeam
from models.gm_season  import GmSeason
from models.gm_standing import GmStanding
from models.gm_match    import GmMatch

MAX_AI = 9   # toi + 9 = 10 compétiteurs → round-robin propre (9 journées)


def _round_robin(tokens):
    """Circle method. Retourne une liste de journées, chacune = liste de paires (home, away)."""
    ts = list(tokens)
    if len(ts) % 2 == 1:
        ts.append("BYE")
    n = len(ts)
    fixed, rot = ts[0], ts[1:]
    rounds = []
    for _ in range(n - 1):
        arr = [fixed] + rot
        rounds.append([(arr[i], arr[n - 1 - i]) for i in range(n // 2)])
        rot = [rot[-1]] + rot[:-1]
    return rounds


def create_season(db: Session, team) -> GmSeason:
    # Pas de double saison active
    existing = db.query(GmSeason).filter(
        GmSeason.team_id == team.id, GmSeason.phase != "DONE"
    ).first()
    if existing:
        return existing

    ai_teams = db.query(GmAiTeam).filter(GmAiTeam.is_active == True) \
        .order_by(GmAiTeam.seed.asc(), GmAiTeam.id.asc()).limit(MAX_AI).all()

    n_prev   = db.query(GmSeason).filter(GmSeason.team_id == team.id).count()
    year     = n_prev // 3 + 1
    split_no = n_prev % 3 + 1

    competitors = [None] + [a.id for a in ai_teams]   # None = la franchise
    rounds   = _round_robin(competitors)
    total_md = len(rounds)

    season = GmSeason(
        team_id=team.id, league="LFL", year=year, split_no=split_no,
        phase="REGULAR", current_matchday=1, total_matchdays=total_md,
    )
    db.add(season)
    db.flush()   # → season.id

    db.add(GmStanding(season_id=season.id, ai_team_id=None))   # toi
    for a in ai_teams:
        db.add(GmStanding(season_id=season.id, ai_team_id=a.id))

    for md, pairs in enumerate(rounds, start=1):
        for home, away in pairs:
            if home == "BYE" or away == "BYE":
                continue
            db.add(GmMatch(
                season_id=season.id, phase="REGULAR", matchday=md,
                home_ai_id=home, away_ai_id=away, format="BO1",
                status="SCHEDULED", involves_user=(home is None or away is None),
            ))

    db.commit()
    db.refresh(season)
    return season