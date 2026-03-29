from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.favorite import UserFavorite
from models.notification import Notification
from models.player import SearchedPlayer
from deps import get_current_user
from models.user import User

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("")
def get_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    favs = (
        db.query(UserFavorite)
        .filter(UserFavorite.user_id == current_user.id)
        .all()
    )
    result = []
    for f in favs:
        player = db.query(SearchedPlayer).filter(SearchedPlayer.id == f.riot_player_id).first()
        if player:
            result.append({
                "favorite_id":    f.id,
                "riot_player_id": player.id,
                "summoner_name":  player.summoner_name,
                "tag_line":       player.tag_line,
                "region":         player.region,
                "created_at":     f.created_at,
            })
    return result


@router.get("/check/{riot_player_id}")
def check_favorite(
    riot_player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exists = db.query(UserFavorite).filter(
        UserFavorite.user_id == current_user.id,
        UserFavorite.riot_player_id == riot_player_id,
    ).first()
    return {"is_favorite": exists is not None}


@router.post("/{riot_player_id}")
def add_favorite(
    riot_player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    player = db.query(SearchedPlayer).filter(SearchedPlayer.id == riot_player_id).first()
    if not player:
        raise HTTPException(404, "Joueur introuvable")

    existing = db.query(UserFavorite).filter(
        UserFavorite.user_id == current_user.id,
        UserFavorite.riot_player_id == riot_player_id,
    ).first()
    if existing:
        raise HTTPException(400, "Déjà en favori")

    fav = UserFavorite(user_id=current_user.id, riot_player_id=riot_player_id)
    db.add(fav)
    db.commit()
    return {"message": "Ajouté aux favoris", "riot_player_id": riot_player_id}


@router.delete("/{riot_player_id}")
def remove_favorite(
    riot_player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fav = db.query(UserFavorite).filter(
        UserFavorite.user_id == current_user.id,
        UserFavorite.riot_player_id == riot_player_id,
    ).first()
    if not fav:
        raise HTTPException(404, "Pas en favori")

    db.delete(fav)
    db.commit()
    return {"message": "Retiré des favoris"}


# ── NOTIFICATIONS ──────────────────────────────────────────────

@router.get("/notifications")
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifs = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "id":         n.id,
            "type":       n.type,
            "message":    n.message,
            "data":       n.data,
            "read":       n.read,
            "created_at": n.created_at,
        }
        for n in notifs
    ]


@router.post("/notifications/{notif_id}/read")
def mark_read(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == current_user.id,
    ).first()
    if not notif:
        raise HTTPException(404, "Notification introuvable")
    notif.read = True
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read == False,
    ).update({"read": True})
    db.commit()
    return {"ok": True}