/*
 * Main – intentionally use arr[12] (out of bounds) and wrong type for balance.
 * Snipe should show:
 * - Array index 12 exceeds size 10 (core.c)
 * - (If we had cross-file type: balance as int elsewhere)
 */
#include <stdio.h>

extern int arr[10];
extern float balance;
extern int add(int a, int b);
extern void process(int count);

int main(void) {
    process(5);
    int x = arr[144];   /* BUG: out of bounds – arr has size 10 */
    printf("%d\n", x);
    return add(1, 2);
}