/*
 * Core module – defines shared array and types for demo.
 * Snipe should detect when another file uses arr[12] (out of bounds) or wrong type.
 */
int arr[10];

float balance = 100.0f;

int add(int a, int b) {
    return a + b;
}

void process(int count) {
    for (int i = 0; i < count && i < 10; i++) {
        arr[i] = i;
    }
}
