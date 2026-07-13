import requests


BASE_URL = "http://127.0.0.1:8000"


def login(username, password):

    res = requests.post(
        f"{BASE_URL}/login",
        json={
            "username": username,
            "password": password
        },
        timeout=10
    )

    return res.json()



def chat(user_id, message):

    res = requests.post(
        f"{BASE_URL}/chat",
        json={
            "user_id": user_id,
            "message": message
        },
        timeout=120
    )

    return res.json()

def register(username, password):

    res = requests.post(
        f"{BASE_URL}/register",
        json={
            "username": username,
            "password": password
        },
        timeout=10
    )

    return res.json()