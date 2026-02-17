"""
Utils – defines balance as int. core.c has balance as float.
Snipe can demonstrate cross-file type mismatch (Python vs C in same repo).
"""
from dataclasses import dataclass

balance: int = 42  # int here

scores: list = [90, 85, 78, 92, 88]  # size 5

def greet(name: str, greeting: str = "Hello") -> str:
    """Expects 1 or 2 arguments."""
    return f"{greeting}, {name}!"

def compute(a: int, b: int, c: int) -> int:
    """Expects exactly 3 arguments."""
    return a + b + c

def flexible(*args, **kwargs) -> None:
    """Accepts any number of arguments."""
    pass

@dataclass
class Config:
    host: str
    port: int = 8080
