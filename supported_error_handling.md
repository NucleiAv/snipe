# Snipe — Supported Error Handling

Snipe currently detects **19 categories of errors** across C and Python, using real-time cross-file semantic analysis powered by Tree-sitter AST parsing and a repo-wide knowledge graph.

---

## C Error Detection

| # | Error Code | Name | Severity | What It Detects | Example |
|---|-----------|------|----------|-----------------|---------|
| 1 | `SNIPE_TYPE_MISMATCH` | Cross-file type mismatch | ERROR | `extern` declaration type doesn't match the canonical definition in another file | `core.c`: `char arr[10];` / `main.c`: `extern int arr[10];` |
| 2 | `SNIPE_TYPE_MISMATCH` | Array write type mismatch | ERROR | Assigning a value of the wrong type into a typed array element | `char arr[10]; arr[0] = 42;` (assigning `int` to `char` array) |
| 3 | `SNIPE_ARRAY_BOUNDS` | Array out of bounds | ERROR | Static array index exceeds the declared size (cross-file aware) | `int arr[10];` in core.c / `arr[12]` accessed in main.c |
| 4 | `SNIPE_SIGNATURE_DRIFT` | Function signature drift | ERROR | Function called with wrong number of arguments vs its definition (supports defaults, variadic) | `def greet(name, greeting="Hi")` called as `greet("A", "B", "C")` |
| 5 | `SNIPE_UNDEFINED_SYMBOL` | Undefined function call | WARNING | Calling a function not defined anywhere in the repo or C standard library | `my_custom_func(42);` when `my_custom_func` is never defined |
| 6 | `SNIPE_FORMAT_STRING` | Format string argument mismatch | ERROR | Printf-family call has different number of format specifiers (`%d`, `%s`, etc.) vs actual arguments | `printf("%d %s", 42);` (2 specifiers, 1 argument) |
| 7 | `SNIPE_UNUSED_EXTERN` | Unused extern declaration | WARNING | An `extern` declaration is never referenced anywhere in the file | `extern int helper;` declared but `helper` never used |
| 8 | `SNIPE_UNSAFE_FUNCTION` | Unsafe function usage | WARNING | Use of C functions known to cause buffer overflows, with safe alternative suggestions | `strcpy(dst, src);` — suggests `strncpy()` or `strlcpy()` |
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

| Unsafe Function | Suggested Safe Alternative |
|----------------|---------------------------|
| `strcpy()` | `strncpy()` or `strlcpy()` |
| `strcat()` | `strncat()` or `strlcat()` |
| `sprintf()` | `snprintf()` |
| `gets()` | `fgets()` |
| `scanf()` | `fgets()` + `sscanf()` or limit field width (e.g. `%99s`) |
| `vsprintf()` | `vsnprintf()` |
| `tmpnam()` | `mkstemp()` |

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
| `SNIPE_UNSAFE_FUNCTION` | WARNING | C | Use of dangerous buffer functions |
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
