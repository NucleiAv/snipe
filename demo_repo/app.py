"""
App – call greet with wrong number of args (signature drift) and use balance.
Type mismatch: balance is int in utils.py but float in core.c (cross-language demo).
"""
from utils import balance, greet, compute

def main():
    print(greet("World"))           # OK: 1 arg
    print(greet("X", "Hi", "extra"))  # BUG: 3 args, greet expects 1 or 2
    print(compute(1, 2))           # BUG: 2 args, compute expects 3
    print(balance)

if __name__ == "__main__":
    main()
