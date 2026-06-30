import redis
import json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

class SessionMemory:
    def __init__(self, max_turns=20, ttl=1800):
        self.max_turns = max_turns
        self.ttl = ttl

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