from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.user import User

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

@router.get("")
def get_leaderboard(db: Session = Depends(get_db)):
    users = (
        db.query(User)
        .order_by(User.coins.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "rank":       i + 1,
            "id":         u.id,
            "username":   u.username,
            "coins":      u.coins,
            "avatar_url": u.avatar_url,
        }
        for i, u in enumerate(users)
    ]