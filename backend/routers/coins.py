from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.transaction import Transaction
from deps import get_current_user
from datetime import datetime, timedelta

router = APIRouter(prefix="/coins", tags=["coins"])

DAILY_REWARD = 100


@router.post("/daily")
def claim_daily(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.utcnow()

    if current_user.last_daily and (now - current_user.last_daily) < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now - current_user.last_daily)
        hours = int(remaining.seconds / 3600)
        minutes = int((remaining.seconds % 3600) / 60)
        raise HTTPException(400, f"Daily déjà réclamé, reviens dans {hours}h{minutes}m")

    current_user.coins += DAILY_REWARD
    current_user.last_daily = now

    transaction = Transaction(
        user_id=current_user.id,
        type="daily_reward",
        amount=DAILY_REWARD,
        description="Daily reward",
    )
    db.add(transaction)
    db.commit()

    return {
        "coins_gagnés": DAILY_REWARD,
        "coins_total": current_user.coins,
        "prochain_daily": "dans 24h",
    }


@router.get("/balance")
def get_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "coins": current_user.coins,
        "last_daily": current_user.last_daily,
        "daily_disponible": (
            not current_user.last_daily
            or (datetime.utcnow() - current_user.last_daily) >= timedelta(hours=24)
        ),
    }


@router.get("/history")
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "type": t.type,
            "amount": t.amount,
            "description": t.description,
            "created_at": t.created_at,
        }
        for t in transactions
    ]