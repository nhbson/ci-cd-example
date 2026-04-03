import random

PROXIES = [
    {"host": "proxy1", "port": 8000, "user": "u", "pass": "p"},
    {"host": "proxy2", "port": 8000, "user": "u", "pass": "p"},
]

def get_proxy():
    return random.choice(PROXIES)