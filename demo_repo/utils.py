"""
Utils – defines balance as int. core.c has balance as float.
Snipe can demonstrate cross-file type mismatch (Python vs C in same repo).
"""
balance = 42  # int here

def greet(name, greeting="Hello"):
    """Expects 1 or 2 arguments."""
    return f"{greeting}, {name}!"

def compute(a, b, c):
    """Expects exactly 3 arguments."""
    return a + b + c
