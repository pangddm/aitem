from app.db.mysql.crud import (
    create_user,
    get_user,
    verify_user
)
from fastapi import APIRouter
router = APIRouter()
@router.post("/register")
def register(data: dict):

    username = data["username"]
    password = data["password"]


    # 查询用户名是否存在
    user = get_user(username)


    if user:

        return {
            "success": False,
            "message": "用户名已经存在"
        }


    create_user(
        username,
        password
    )


    return {
        "success": True,
        "message": "注册成功"
    }


@router.post("/login")
def login(data: dict):

    username = data["username"]
    password = data["password"]


    user = verify_user(
        username,
        password
    )


    if user:

        return {
            "success": True,
            "user_id": user.username
        }


    return {
        "success": False,
        "message": "用户名或密码错误"
    }