import redis
import os
import json
from dotenv import load_dotenv
load_dotenv()
r = redis.Redis(host=os.getenv("REDIS_HOST"), port=int(os.getenv("REDIS_PORT")), decode_responses=True)

class SessionMemory:
    def __init__(self, max_turns=None, ttl=None):
        self.max_turns = int(os.getenv("REDIS_MAX_TURNS")) if max_turns is None else max_turns
        self.ttl = int(os.getenv("REDIS_TTL")) if ttl is None else ttl

    def key(self, user_id):
        return f"session:{user_id}"

    def load(self, user_id):
        data = r.get(self.key(user_id))
        if not data:
            return []
        return json.loads(data)

    def save(self, user_id, messages):
        messages = messages[-self.max_turns:]
        r.set(self.key(user_id), json.dumps(messages))
        r.expire(self.key(user_id), self.ttl)

    def append(self, user_id, role, content):
        messages = self.load(user_id)
        messages.append({"role": role, "content": content})
        self.save(user_id, messages)
        return messages