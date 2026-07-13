from app.db.mysql.database import SessionLocal
from app.db.mysql.models import User


def get_user(username: str):

    db = SessionLocal()

    user = db.query(User).filter(
        User.username == username
    ).first()

    db.close()

    return user



def create_user(
    username: str,
    password: str
):

    db = SessionLocal()

    user = User(
        username=username,
        password=password
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    db.close()

    return user



def verify_user(
    username: str,
    password: str
):

    db = SessionLocal()

    user = db.query(User).filter(
        User.username == username,
        User.password == password
    ).first()

    db.close()

    return user