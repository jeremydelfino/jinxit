from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.game_poller import poll_pro_games
from database import engine, Base

# Modèles existants
import models.user, models.card, models.player, models.match
import models.live_game, models.bet, models.bet_type
import models.transaction, models.user_card, models.pro_player
from models.riot_account import RiotAccount
import models.favorite, models.notification
import models.esports_bet
import models.esports_team
import models.esports_player
import models.esports_team_rating

# Nouveaux modèles
import models.job_run
import models.champion_stats
import models.champion_synergy
import models.team_form

# Routers
from routers import auth, players, bets, coins, profile, upload, admin, games, favorites, leaderboard
from routers import esports
from routers import admin_jobs
from routers.settings import router as settings_router

# Services
from services.esports_sync import sync_all_teams
from services.champion_winrate_collector import refresh_champion_winrates
from services.team_form_collector import refresh_team_form
from services.esports_sync import sync_all_teams_leaguepedia


Base.metadata.create_all(bind=engine)

scheduler = AsyncIOScheduler()


# ─── Wrappers pour jobs DB-aware ──────────────────────────────

async def sync_esports_teams_job():
    await sync_all_teams()


async def resolve_completed_matches_job():
    from database import SessionLocal
    from routers.esports import resolve_completed_matches
    db = SessionLocal()
    try:
        await resolve_completed_matches(db=db)
    finally:
        db.close()


async def refresh_team_winrates_job():
    """Refresh des standings (winrates saison) — wrapper pour passer db."""
    from database import SessionLocal
    from routers.esports import refresh_all_standings
    db = SessionLocal()
    try:
        await refresh_all_standings(db)
    finally:
        db.close()


# ─── Lifespan : enregistrement des jobs ───────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Jobs existants ────────────────────────────────────────
    scheduler.add_job(
        poll_pro_games,
        "interval", minutes=3,
        id="poll_games",
        next_run_time=datetime.now(),
    )
    scheduler.add_job(
        resolve_completed_matches_job,
        "interval", minutes=10,
        id="resolve_esports",
        next_run_time=datetime.now(),
    )
    scheduler.add_job(
        sync_esports_teams_job,
        "interval", hours=6,
        id="sync_esports_teams",
        # Pas de next_run_time → tournera au prochain trigger normal
    )

    # ── Nouveaux jobs ─────────────────────────────────────────

    # Refresh winrates équipes : toutes les 30min (les standings bougent souvent)
    scheduler.add_job(
        refresh_team_winrates_job,
        "interval", minutes=30,
        id="refresh_team_winrates",
    )

    # Refresh forme des équipes : toutes les heures
    scheduler.add_job(
        refresh_team_form,
        "interval", minutes=60,
        id="refresh_team_form",
    )

    # Refresh winrates champions : tous les mercredis 6h UTC (= jour de patch typique)
    scheduler.add_job(
        refresh_champion_winrates,
        CronTrigger(day_of_week="wed", hour=6, minute=0),
        id="refresh_champion_winrates",
    )


    scheduler.add_job(
        sync_all_teams_leaguepedia,
        trigger="cron",
        day_of_week="mon",
        hour=4,
        minute=0,
        id="weekly_esports_sync",
        replace_existing=True,
    )

    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="junglegap API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://*.vercel.app",
        "https://www.junglegap.fr",
        "https://junglegap.fr",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings_router)
app.include_router(auth.router)
app.include_router(players.router)
app.include_router(bets.router)
app.include_router(coins.router)
app.include_router(profile.router)
app.include_router(upload.router)
app.include_router(admin.router)
app.include_router(games.router)
app.include_router(favorites.router)
app.include_router(leaderboard.router)
app.include_router(esports.router)
app.include_router(admin_jobs.router)


@app.get("/")
def root():
    return {"status": "junglegap API is running, is there a gap here ?"}