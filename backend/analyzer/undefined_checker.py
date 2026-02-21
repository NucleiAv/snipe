"""
Undefined symbol/function detection.
#9:  Undefined symbol reference (Python read refs not in repo/buffer/builtins)
#10: Undefined function call (C + Python calls not in repo/buffer/stdlib)
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic

# Python builtins that should never be flagged
PYTHON_BUILTINS = {
    "print", "len", "range", "int", "str", "float", "bool", "list", "dict",
    "tuple", "set", "frozenset", "type", "isinstance", "issubclass", "hasattr",
    "getattr", "setattr", "delattr", "property", "staticmethod", "classmethod",
    "super", "object", "None", "True", "False", "abs", "all", "any", "ascii",
    "bin", "breakpoint", "bytearray", "bytes", "callable", "chr", "compile",
    "complex", "copyright", "credits", "delattr", "dir", "divmod", "enumerate",
    "eval", "exec", "exit", "filter", "format", "globals", "hash", "help",
    "hex", "id", "input", "iter", "license", "locals", "map", "max", "memoryview",
    "min", "next", "oct", "open", "ord", "pow", "quit", "repr", "reversed",
    "round", "slice", "sorted", "sum", "vars", "zip", "__import__",
    "NotImplemented", "Ellipsis", "__name__", "__file__", "__doc__",
    "__package__", "__spec__", "__loader__", "__builtins__",
    # Exception types
    "Exception", "BaseException", "ValueError", "TypeError", "KeyError",
    "IndexError", "AttributeError", "ImportError", "ModuleNotFoundError",
    "FileNotFoundError", "OSError", "IOError", "RuntimeError", "StopIteration",
    "GeneratorExit", "SystemExit", "KeyboardInterrupt", "ArithmeticError",
    "ZeroDivisionError", "OverflowError", "FloatingPointError",
    "LookupError", "NameError", "UnboundLocalError", "SyntaxError",
    "IndentationError", "TabError", "SystemError", "UnicodeError",
    "UnicodeDecodeError", "UnicodeEncodeError", "UnicodeTranslateError",
    "Warning", "DeprecationWarning", "PendingDeprecationWarning",
    "RuntimeWarning", "SyntaxWarning", "ResourceWarning", "FutureWarning",
    "ImportWarning", "UnicodeWarning", "BytesWarning", "UserWarning",
    "AssertionError", "AssertionError", "NotImplementedError", "RecursionError",
    "StopAsyncIteration", "ConnectionError", "BrokenPipeError",
    "ConnectionAbortedError", "ConnectionRefusedError", "ConnectionResetError",
    "BlockingIOError", "ChildProcessError", "FileExistsError",
    "InterruptedError", "IsADirectoryError", "NotADirectoryError",
    "PermissionError", "ProcessLookupError", "TimeoutError",
    # Common decorators and typing
    "dataclass", "field", "abstractmethod", "override",
    "Optional", "Union", "List", "Dict", "Tuple", "Set", "Any",
    "Callable", "Iterator", "Generator", "Iterable", "Sequence",
    "Mapping", "MutableMapping", "TypeVar", "Generic", "Protocol",
}

PYTHON_COMMON_GLOBALS = {
    "self", "cls", "__name__", "__file__", "__doc__", "__all__",
    "__version__", "__author__", "__package__",
}

# C standard library / POSIX / common functions that should never be flagged as undefined.
# This includes unsafe functions (they ARE defined — just discouraged).
C_STDLIB_FUNCTIONS = {
    # stdio
    "printf", "fprintf", "sprintf", "snprintf", "scanf", "fscanf", "sscanf",
    "vsprintf", "vsnprintf", "vscanf", "vfscanf", "vsscanf",
    "fopen", "fclose", "fread", "fwrite", "fgets", "fputs", "feof", "fseek", "ftell",
    "perror", "puts", "getchar", "putchar", "getc", "putc", "fgetc", "fputc",
    "gets", "gets_s", "rewind", "freopen", "tmpfile", "tmpnam", "tempnam",
    "setbuf", "setvbuf", "ungetc", "fflush", "ferror", "clearerr",
    # stdlib
    "malloc", "calloc", "realloc", "free", "alloca",
    "exit", "abort", "atexit", "_exit", "at_quick_exit", "quick_exit",
    "system", "getenv", "secure_getenv",
    "abs", "labs", "llabs", "div", "ldiv", "lldiv",
    "rand", "srand", "random", "srandom", "drand48", "srand48",
    "atoi", "atol", "atoll", "atof",
    "strtol", "strtoul", "strtoll", "strtoull", "strtod", "strtof", "strtold",
    "qsort", "bsearch",
    # string
    "memcpy", "memset", "memmove", "memcmp", "memchr",
    "strcpy", "strncpy", "strcat", "strncat", "strcmp", "strncmp", "strlen",
    "strstr", "strchr", "strrchr", "strtok", "strtok_r",
    "strdup", "strndup", "stpcpy", "strlcpy", "strlcat",
    "bcopy", "bzero",
    # ctype
    "isalpha", "isdigit", "isalnum", "isspace", "isupper", "islower",
    "isprint", "iscntrl", "ispunct", "isxdigit", "isgraph",
    "toupper", "tolower",
    # time
    "time", "clock", "difftime", "mktime",
    "ctime", "ctime_r", "asctime", "asctime_r",
    "gmtime", "gmtime_r", "localtime", "localtime_r",
    "strftime",
    # process / exec
    "fork", "vfork", "execl", "execle", "execlp", "execv", "execvp", "execve",
    "popen", "pclose", "wait", "waitpid",
    "pipe", "dup", "dup2",
    # signal
    "signal", "sigaction", "raise", "kill",
    # io
    "open", "close", "read", "write", "lseek", "ioctl",
    "select", "poll",
    # misc
    "getlogin", "getpwuid", "getuid", "geteuid",
    "sleep", "usleep", "nanosleep",
    "mkstemp", "mkdtemp",
    # variadic
    "va_start", "va_end", "va_arg", "va_copy",
    # keywords / macros
    "assert", "sizeof", "offsetof",
    "NULL", "EOF", "main",
}


def _get_language_from_path(file_path: str):
    ext = Path(file_path).suffix.lower()
    if ext in (".c", ".h"):
        return "c"
    if ext == ".py":
        return "python"
    return None


def check_undefined_symbols(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    lang = _get_language_from_path(current_file)
    if lang is None:
        return diagnostics

    # Build set of known symbol names
    buffer_names = {s.name for s in buffer_symbols}
    repo_names = {s.get("name") for s in repo_symbols if s.get("name")}

    # Collect imported names from import references
    imported_names: set[str] = set()
    for ref in buffer_refs:
        if ref.kind == "import" and ref.imported_names:
            imported_names.update(ref.imported_names)

    all_known = buffer_names | repo_names | imported_names

    if lang == "python":
        all_known |= PYTHON_BUILTINS | PYTHON_COMMON_GLOBALS

        # Check if file has a star import — if so, suppress undefined warnings
        has_star_import = False
        for ref in buffer_refs:
            if ref.kind == "import" and ref.imported_names:
                if "*" in ref.imported_names:
                    has_star_import = True
                    break
        if has_star_import:
            return diagnostics

        # #9: Undefined symbol reference (read refs)
        for ref in buffer_refs:
            if ref.kind != "read":
                continue
            if ref.name in all_known:
                continue
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="WARNING",
                code="SNIPE_UNDEFINED_SYMBOL",
                message=f"'{ref.name}' is not defined in this file, the repository, or Python builtins.",
            ))

        # #10: Undefined function call (Python)
        for ref in buffer_refs:
            if ref.kind != "call":
                continue
            # Skip method calls (contain dots like obj.method)
            if "." in ref.name:
                continue
            if ref.name in all_known:
                continue
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="WARNING",
                code="SNIPE_UNDEFINED_SYMBOL",
                message=f"Function '{ref.name}' is not defined in this file, the repository, or Python builtins.",
            ))

    elif lang == "c":
        all_known |= C_STDLIB_FUNCTIONS

        # #10: Undefined function call (C)
        for ref in buffer_refs:
            if ref.kind != "call":
                continue
            if ref.name in all_known:
                continue
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="WARNING",
                code="SNIPE_UNDEFINED_SYMBOL",
                message=f"Function '{ref.name}' is not defined in this file, the repository, or the C standard library.",
            ))

    return diagnostics
