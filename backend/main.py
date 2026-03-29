from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.game_poller import poll_pro_games
from database import engine, Base
import models.user, models.card, models.player, models.match
import models.live_game, models.bet, models.bet_type
import models.transaction, models.user_card, models.pro_player
from models.riot_account import RiotAccount
import models.favorite, models.notification
import models.esports_bet      
import models.esports_team
import models.esports_player  
import models.esports_team_rating                               
from routers import auth, players, bets, coins, profile, upload, admin, games, favorites, leaderboard
from routers import esports                    

from services.esports_sync import sync_all_teams

Base.metadata.create_all(bind=engine)

scheduler = AsyncIOScheduler()


async def sync_esports_teams_job():
    await sync_all_teams()

scheduler.add_job(
    sync_esports_teams_job,
    "interval",
    hours=24,
    id="sync_esports_teams",
    next_run_time=datetime.now()   # lance immédiatement au démarrage
)

async def resolve_completed_matches_job():
    from database import SessionLocal
    from routers.esports import resolve_completed_matches
    db = SessionLocal()
    try:
        await resolve_completed_matches(db=db)
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(poll_pro_games, "interval", minutes=3, id="poll_games", next_run_time=datetime.now())
    scheduler.add_job(resolve_completed_matches_job, "interval", minutes=10, id="resolve_esports", next_run_time=datetime.now())
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="junglegap API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/")
def root():
    return {"status": "junglegap API is running, is there a gap here ?"}