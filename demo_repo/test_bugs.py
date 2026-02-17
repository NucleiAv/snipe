"""
Test bugs – intentional errors for Snipe to detect across Python files.
Mirrors main.c which tests C-side bugs against core.c.

Snipe should report:
  - SNIPE_SIGNATURE_DRIFT: greet() called with 0 args (expects 1-2)
  - SNIPE_SIGNATURE_DRIFT: compute() called with 4 args (expects 3)
  - SNIPE_ARRAY_BOUNDS:    scores[99] out of bounds (size 5)
  - SNIPE_TYPE_MISMATCH:   balance used as float here vs int in utils.py
"""
from utils import greet, compute, scores, balance, flexible, Config

# --- Signature drift bugs ---

result = greet()                    # BUG: 0 args, expects 1 or 2
result = greet("A", "B", "C")      # BUG: 3 args, expects 1 or 2
result = compute(1, 2, 3, 4)       # BUG: 4 args, expects 3

# --- These should be fine ---

result = greet("Alice")             # OK: 1 arg
result = greet("Bob", "Hey")        # OK: 2 args
result = compute(10, 20, 30)        # OK: 3 args
flexible(1, 2, 3, key="val")        # OK: variadic accepts anything

# --- Array bounds bug ---

first = scores[0]                   # OK: index 0, size 5
last = scores[4]                    # OK: index 4, size 5
oob = scores[99]                    # BUG: index 99, size 5

# --- Type mismatch bug ---

balance: float = 3.14               # BUG: balance is int in utils.py, float here

# --- Dataclass usage ---

cfg = Config(host="localhost", port=9090)  # OK
