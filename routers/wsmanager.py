from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi_utils.tasks import repeat_every
from db import get_db, SessionLocal
from models.notifications import Notification
from models.users import Users
from notification import manager
from routers.auth import get_current_user_socket
from schemas.notifications import NotificationSchema
from sqlalchemy.orm import Session
from schemas.users import UserCurrent

notification_router = APIRouter()

db: Session = SessionLocal()


@notification_router.websocket("/ws/connection")
async def websocket_endpoint(
        websocket: WebSocket,
        db: Session = Depends(get_db), user: UserCurrent = Depends(get_current_user_socket)
):
    await manager.connect(websocket, user)
    if user:
        for ntf in user.notifications:
            message = NotificationSchema(
                title=ntf.title,
                body=ntf.body,
                user_id=ntf.user_id,

            )
            await manager.send_personal_json(message, (websocket, user))
        db.query(Notification).filter_by(user_id=user.id).delete()
        db.commit()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


@notification_router.on_event("startup")
@repeat_every(seconds=43200, wait_first=True)
async def startup():
    try:
        drivers = db.query(Users).filter(Users.status == True, Users.role == "driver").all()
        for user in drivers:
            data = NotificationSchema(
                title="Order",
                body="order",
                user_id=user.id,
            )
            await manager.send_user(message=data, user_id=user.id, db=db)
        return drivers
    finally:
        db.close()
