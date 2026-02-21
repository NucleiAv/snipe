# Snipe — Supported Error Handling

Snipe currently detects **19 categories of errors** across C and Python, using real-time cross-file semantic analysis powered by Tree-sitter AST parsing and a repo-wide knowledge graph.

---

## C Error Detection

| # | Error Code | Name | Severity | What It Detects | Example |
|---|-----------|------|----------|-----------------|---------|
| 1 | `SNIPE_TYPE_MISMATCH` | Cross-file type mismatch | ERROR | `extern` declaration type doesn't match the canonical definition in another file | `core.c`: `char arr[10];` / `main.c`: `extern int arr[10];` |
| 2 | `SNIPE_TYPE_MISMATCH` | Array write type mismatch | ERROR | Assigning a value of the wrong type into a typed array element | `char arr[10]; arr[0] = 42;` (assigning `int` to `char` array) |
| 3 | `SNIPE_ARRAY_BOUNDS` | Array out of bounds | ERROR | Static array index exceeds the declared size (cross-file aware) | `int arr[10];` in core.c / `arr[12]` accessed in main.c |
| 4 | `SNIPE_SIGNATURE_DRIFT` | Function signature drift | ERROR | Function called with wrong number of arguments vs its definition | `int add(int a, int b)` called as `add(1, 2, 3)` |
| 5 | `SNIPE_UNDEFINED_SYMBOL` | Undefined function call | WARNING | Calling a function not defined anywhere in the repo or C standard library | `my_custom_func(42);` when `my_custom_func` is never defined |
| 6 | `SNIPE_FORMAT_STRING` | Format string argument mismatch | ERROR | Printf-family call has different number of format specifiers (`%d`, `%s`, etc.) vs actual arguments | `printf("%d %s", 42);` (2 specifiers, 1 argument) |
| 7 | `SNIPE_UNUSED_EXTERN` | Unused extern declaration | WARNING | An `extern` declaration is never referenced anywhere in the file | `extern int helper;` declared but `helper` never used |
| 8 | `SNIPE_UNSAFE_FUNCTION` | Unsafe / discouraged function | ERROR or WARNING | Use of C functions that are removed from the standard (ERROR) or discouraged by CERT C (WARNING) | `gets(buf)` = ERROR / `strcpy(dst, src)` = WARNING |
| 9 | `SNIPE_STRUCT_ACCESS` | Invalid struct member access | ERROR | Accessing a member that doesn't exist on a struct type | `struct Point { int x; int y; }; p.z;` — `z` doesn't exist |

---

## Python Error Detection

| # | Error Code | Name | Severity | What It Detects | Example |
|---|-----------|------|----------|-----------------|---------|
| 1 | `SNIPE_TYPE_MISMATCH` | Cross-file type mismatch | ERROR | Variable declared with a different type than in another file in the repo | `utils.py`: `balance: int = 42` / `test.py`: `balance: float = 3.14` |
| 2 | `SNIPE_ARRAY_BOUNDS` | List/tuple out of bounds | ERROR | Static index exceeds the declared list/tuple size (cross-file aware) | `scores = [90, 85, 78]` in utils.py / `scores[99]` in app.py |
| 3 | `SNIPE_SIGNATURE_DRIFT` | Function signature drift | ERROR | Function called with wrong number of arguments (supports defaults, `*args`, `**kwargs`) | `def compute(a, b, c)` called as `compute(1, 2)` |
| 4 | `SNIPE_UNDEFINED_SYMBOL` | Undefined symbol reference | WARNING | Using a name not defined in the file, repository, imports, or Python builtins | `print(unknown_var)` when `unknown_var` is never defined |
| 5 | `SNIPE_UNDEFINED_SYMBOL` | Undefined function call | WARNING | Calling a function not defined in the file, repository, imports, or Python builtins | `result = mystery_func(42)` when `mystery_func` is never defined |
| 6 | `SNIPE_SHADOWED_SYMBOL` | Variable shadowing | WARNING | A local variable inside a function shadows a module-level variable | `x = 10` at module level / `def foo(): x = "hello"` shadows it |
| 7 | `SNIPE_DEAD_IMPORT` | Dead import | WARNING | An imported name is never used anywhere in the file | `from os import path, getcwd` when `getcwd` is never used |
| 8 | `SNIPE_TYPE_MISMATCH` | Return type mismatch | ERROR | A function's return statement type doesn't match its declared return type annotation | `def foo() -> int: return "hello"` (returns `str`, declared `int`) |
| 9 | `SNIPE_TYPE_MISMATCH` | Assignment type mismatch | ERROR | Assigning a value of the wrong type to a type-annotated variable | `x: int = "hello"` (annotated `int`, assigned `str`) |
| 10 | `SNIPE_ARG_TYPE_MISMATCH` | Argument type mismatch | ERROR | Calling a function with arguments whose types don't match parameter annotations | `def greet(name: str)` called as `greet(42)` (expected `str`, got `int`) |

---

## Unsafe C Functions Flagged (`SNIPE_UNSAFE_FUNCTION`)

Snipe flags **60+ dangerous C functions** based on the CERT C Secure Coding Standard. `gets()` is flagged as **ERROR** (removed from C11). All others are **WARNING** (discouraged but still in the standard).

### Removed from C Standard (C11+) — ERROR

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `gets()` | Removed in C11 — no bounds checking, guaranteed buffer overflow risk | `fgets(buf, size, stdin)` |

### Unsafe String Handling Functions — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `strcpy()` | No bounds checking — writes past buffer if source is longer than destination | `strncpy()` or `strlcpy()` |
| `strcat()` | No bounds checking — concatenation can overflow destination buffer | `strncat()` or `strlcat()` |
| `stpcpy()` | No bounds checking — same risks as `strcpy()` | `strncpy()` or `strlcpy()` |
| `gets_s()` | Annex K optional function — not widely supported, still risky | `fgets(buf, size, stdin)` |
| `strtok()` | Uses internal static state — not thread-safe, modifies input string | `strtok_r()` (POSIX) or manual parsing |
| `strncpy()` | Does not guarantee null-termination if source >= n bytes | `strlcpy()` or manually null-terminate |
| `strncat()` | Easy to misuse — size parameter is remaining space, not total buffer size | `strlcat()` or compute remaining size carefully |
| `strdup()` | No input length limit — untrusted input can cause memory exhaustion | `strndup()` with a max length |

### Unsafe Formatted Output Functions — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `sprintf()` | No bounds checking — format output can overflow destination buffer | `snprintf(buf, size, fmt, ...)` |
| `vsprintf()` | No bounds checking — variadic format output can overflow buffer | `vsnprintf(buf, size, fmt, ap)` |

### Potentially Unsafe Input Functions — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `scanf()` | Without field width limits, `%s` can overflow buffers | `fgets()` + `sscanf()`, or `%99s` |
| `fscanf()` | Without field width limits, `%s` can overflow buffers | `fgets()` + `sscanf()` with bounded specifiers |
| `sscanf()` | Without field width limits, `%s` can overflow buffers | Limit field width (e.g. `%99s`) |
| `vscanf()` | Variadic version of `scanf` — same overflow risks | `fgets()` + `vsscanf()` with bounded specifiers |
| `vfscanf()` | Variadic version of `fscanf` — same overflow risks | `fgets()` + `vsscanf()` with bounded specifiers |
| `vsscanf()` | Variadic version of `sscanf` — same overflow risks | Limit field width (e.g. `%99s`) |

### Temporary File Functions (Race Condition Risk) — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `tmpnam()` | Race condition between name generation and file creation (TOCTOU) | `mkstemp()` or `tmpfile()` |
| `tempnam()` | Race condition between name generation and file creation (TOCTOU) | `mkstemp()` or `tmpfile()` |
| `tmpfile()` | Less risky than `tmpnam()` but still implementation-sensitive | `mkstemp()` for full control |

### Memory / Environment Risk — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `getenv()` | Returns pointer to environment which can be attacker-controlled | `secure_getenv()` (glibc) or validate the value |
| `alloca()` | Allocates on the stack — no failure indication, stack overflow risk | `malloc()` / `calloc()` with size checks |

### Weak Random Number Generation — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `rand()` | Predictable PRNG — not suitable for security-sensitive contexts | `arc4random()`, `getrandom()`, or `/dev/urandom` |
| `srand()` | Seeds the predictable `rand()` PRNG — not cryptographically secure | `arc4random()` or `getrandom()` (no manual seeding) |
| `random()` | Better than `rand()` but still not cryptographically secure | `arc4random()` or `getrandom()` |
| `drand48()` | Predictable PRNG — not suitable for security-sensitive contexts | `arc4random()` or `getrandom()` |

### Unsafe Type Conversion — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `atoi()` | No error detection — undefined behavior on overflow | `strtol()` with `errno` checking |
| `atol()` | No error detection — undefined behavior on overflow | `strtol()` with `errno` checking |
| `atoll()` | No error detection — undefined behavior on overflow | `strtoll()` with `errno` checking |
| `atof()` | No error detection — can't distinguish `0.0` from conversion failure | `strtod()` with `errno` checking |

### Process / Execution Functions (Command Injection Risk) — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `system()` | Passes string to shell — vulnerable to command injection | `execve()` or `posix_spawn()` with explicit args |
| `popen()` | Passes string to shell — vulnerable to command injection | `pipe()` + `fork()` + `exec()` with explicit args |
| `execl()` | Inherits environment — exploitable via PATH/env manipulation | `execve()` with explicit environment |
| `execle()` | Safer than `execl()` but still requires careful validation | Validate all arguments and use absolute paths |
| `execlp()` | Searches PATH — attacker can place malicious binary in PATH | `execve()` with absolute paths |
| `execv()` | Inherits environment — exploitable via env manipulation | `execve()` with explicit environment |
| `execvp()` | Searches PATH — attacker can place malicious binary in PATH | `execve()` with absolute paths |
| `execve()` | Safest exec variant but still requires careful argument validation | Validate all arguments and paths |

### Unsafe Signal Handling — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `signal()` | Behavior varies across platforms — can cause race conditions | `sigaction()` for reliable, portable handling |

### Dangerous Memory Operations — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `memcpy()` | Undefined behavior if source and destination buffers overlap | `memmove()` or verify non-overlap |
| `memmove()` | Safer for overlap but still dangerous if size is miscalculated | Validate size parameter against buffer sizes |
| `memcmp()` | Not constant-time — unsafe for comparing secrets (timing attack) | Constant-time comparison for passwords/keys |
| `bcopy()` | Non-standard legacy BSD function — removed from POSIX.1-2008 | `memmove()` |
| `bzero()` | Deprecated BSD function — removed from POSIX.1-2008 | `memset(buf, 0, size)` |

### Potentially Unsafe I/O — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `getc()` | Macro — can evaluate stream argument multiple times | `fgetc()` |
| `putc()` | Macro — can evaluate arguments multiple times | `fputc()` |
| `getchar()` | No input size control — may read unbounded input | `fgets()` for controlled reading |
| `putchar()` | No output error checking by default | Check return value or use `fputc()` |
| `rewind()` | Silently clears error indicator — hides I/O failures | `fseek(fp, 0, SEEK_SET)` + check return |
| `freopen()` | Can redirect critical streams unexpectedly | `fopen()` for new streams |

### Unreliable Environment Info — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `getlogin()` | Not reliable — can be spoofed, may return NULL | `getpwuid(getuid())` |

### Legacy / Obsolete (Not Thread-Safe) — WARNING

| Function | Reason | Safe Alternative |
|----------|--------|------------------|
| `setbuf()` | Cannot report errors — undefined behavior if buffer too small | `setvbuf()` |
| `ctime()` | Returns pointer to static buffer — not thread-safe | `ctime_r()` (POSIX) or `strftime()` |
| `asctime()` | Returns pointer to static buffer — not thread-safe | `asctime_r()` (POSIX) or `strftime()` |
| `gmtime()` | Returns pointer to static buffer — not thread-safe | `gmtime_r()` (POSIX) |
| `localtime()` | Returns pointer to static buffer — not thread-safe | `localtime_r()` (POSIX) |

---

## Printf-Family Functions Checked (`SNIPE_FORMAT_STRING`)

| Function | Format String Argument Position |
|----------|---------------------------------|
| `printf(fmt, ...)` | 1st argument |
| `scanf(fmt, ...)` | 1st argument |
| `fprintf(file, fmt, ...)` | 2nd argument |
| `fscanf(file, fmt, ...)` | 2nd argument |
| `sprintf(buf, fmt, ...)` | 2nd argument |
| `sscanf(str, fmt, ...)` | 2nd argument |
| `snprintf(buf, size, fmt, ...)` | 3rd argument |

---

## Error Codes Quick Reference

| Code | Severity | Languages | Checks |
|------|----------|-----------|--------|
| `SNIPE_TYPE_MISMATCH` | ERROR | C, Python | Cross-file type mismatch, array write type, return type, assignment type |
| `SNIPE_ARRAY_BOUNDS` | ERROR | C, Python | Static array/list index out of bounds |
| `SNIPE_SIGNATURE_DRIFT` | ERROR | C, Python | Function call argument count mismatch |
| `SNIPE_UNDEFINED_SYMBOL` | WARNING | C, Python | Undefined symbol or function reference |
| `SNIPE_SHADOWED_SYMBOL` | WARNING | Python | Local variable shadows module-level variable |
| `SNIPE_FORMAT_STRING` | ERROR | C | Printf format specifier vs argument count mismatch |
| `SNIPE_UNUSED_EXTERN` | WARNING | C | Extern declaration never used in file |
| `SNIPE_DEAD_IMPORT` | WARNING | Python | Imported name never used in file |
| `SNIPE_UNSAFE_FUNCTION` | ERROR / WARNING | C | `gets()` = ERROR (removed from C11); 60+ other functions = WARNING (discouraged by CERT C) |
| `SNIPE_ARG_TYPE_MISMATCH` | ERROR | Python | Function argument type vs parameter annotation mismatch |
| `SNIPE_STRUCT_ACCESS` | ERROR | C | Non-existent struct member access |

---

## Key Features

- **Cross-file analysis**: Errors are detected across file boundaries using a repo-wide symbol knowledge graph.
- **Live unsaved buffer support**: Checks run on unsaved editor content — no need to save files first.
- **Same-language only**: Cross-file checks only compare C-to-C and Python-to-Python (never cross-language).
- **Smart exclusions**: Python builtins (`print`, `len`, `range`, etc.), C standard library functions (`printf`, `malloc`, etc.), and common globals are excluded from undefined symbol checks.
- **Variadic support**: Functions with `*args`/`**kwargs` (Python) are correctly handled — any argument count is accepted.
- **Default parameter support**: Functions with default values correctly compute minimum and maximum argument counts.
- **Star import awareness**: Files containing `from X import *` suppress undefined symbol warnings since imported names can't be statically determined.
- **Diagnostic deduplication**: Duplicate diagnostics (same file, line, code, message) are automatically removed.
- **CERT C compliance**: 60+ dangerous C functions categorized by risk type, with specific reasons and safe alternatives per CERT C Secure Coding Standard.
