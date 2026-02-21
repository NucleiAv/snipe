"""
Dangerous C function detection.
#16: Flag use of unsafe/discouraged C functions per CERT C Secure Coding Standard.

- gets() is ERROR (removed from C standard in C11)
- All others are WARNING (discouraged but still in the standard)

Each entry includes the category, safe alternative, and reason.
"""
from __future__ import annotations
from typing import Any

from parser.symbol_extractor import Reference, Symbol
from analyzer.type_checker import Diagnostic


# ── Removed from C Standard (C11+) ──────────────────────────────────────────
# These produce severity ERROR because they are no longer part of the standard.
REMOVED_FUNCTIONS: dict[str, dict[str, str]] = {
    "gets": {
        "category": "Removed from C Standard (C11+)",
        "reason": "Removed in C11 — no bounds checking, guaranteed buffer overflow risk",
        "suggestion": "Use fgets(buf, size, stdin) instead",
    },
}


# ── Discouraged Functions (WARNING) ──────────────────────────────────────────
# Grouped by risk category per CERT C Secure Coding Standard.

UNSAFE_FUNCTIONS: dict[str, dict[str, str]] = {
    # ── Unsafe String Handling Functions ──────────────────────────────────────
    "strcpy": {
        "category": "Unsafe String Handling",
        "reason": "No bounds checking — writes past buffer if source is longer than destination",
        "suggestion": "Use strncpy() or strlcpy() instead",
    },
    "strcat": {
        "category": "Unsafe String Handling",
        "reason": "No bounds checking — concatenation can overflow destination buffer",
        "suggestion": "Use strncat() or strlcat() instead",
    },
    "stpcpy": {
        "category": "Unsafe String Handling",
        "reason": "No bounds checking — same risks as strcpy()",
        "suggestion": "Use strncpy() or strlcpy() instead",
    },
    "gets_s": {
        "category": "Unsafe String Handling",
        "reason": "Annex K optional function — not widely supported, still risky",
        "suggestion": "Use fgets(buf, size, stdin) instead",
    },
    "strtok": {
        "category": "Unsafe String Handling",
        "reason": "Uses internal static state — not thread-safe, modifies input string",
        "suggestion": "Use strtok_r() (POSIX) or manual parsing instead",
    },
    "strncpy": {
        "category": "Unsafe String Handling",
        "reason": "Does not guarantee null-termination if source >= n bytes",
        "suggestion": "Use strlcpy() or manually null-terminate after strncpy()",
    },
    "strncat": {
        "category": "Unsafe String Handling",
        "reason": "Easy to misuse — size parameter is remaining space, not total buffer size",
        "suggestion": "Use strlcat() or compute remaining size carefully",
    },
    "strdup": {
        "category": "Unsafe String Handling",
        "reason": "No input length limit — untrusted input can cause memory exhaustion",
        "suggestion": "Use strndup() with a max length, or validate input size first",
    },

    # ── Unsafe Formatted Output Functions ────────────────────────────────────
    "sprintf": {
        "category": "Unsafe Formatted Output",
        "reason": "No bounds checking — format output can overflow destination buffer",
        "suggestion": "Use snprintf(buf, size, fmt, ...) instead",
    },
    "vsprintf": {
        "category": "Unsafe Formatted Output",
        "reason": "No bounds checking — variadic format output can overflow buffer",
        "suggestion": "Use vsnprintf(buf, size, fmt, ap) instead",
    },

    # ── Potentially Unsafe Input Functions ───────────────────────────────────
    "scanf": {
        "category": "Potentially Unsafe Input",
        "reason": "Without field width limits, %s can overflow buffers",
        "suggestion": "Use fgets() + sscanf(), or limit field width (e.g. %99s)",
    },
    "fscanf": {
        "category": "Potentially Unsafe Input",
        "reason": "Without field width limits, %s can overflow buffers",
        "suggestion": "Use fgets() + sscanf() with bounded format specifiers",
    },
    "sscanf": {
        "category": "Potentially Unsafe Input",
        "reason": "Without field width limits, %s can overflow buffers",
        "suggestion": "Limit field width in format specifiers (e.g. %99s)",
    },
    "vscanf": {
        "category": "Potentially Unsafe Input",
        "reason": "Variadic version of scanf — same overflow risks without width limits",
        "suggestion": "Use fgets() + vsscanf() with bounded format specifiers",
    },
    "vfscanf": {
        "category": "Potentially Unsafe Input",
        "reason": "Variadic version of fscanf — same overflow risks without width limits",
        "suggestion": "Use fgets() + vsscanf() with bounded format specifiers",
    },
    "vsscanf": {
        "category": "Potentially Unsafe Input",
        "reason": "Variadic version of sscanf — same overflow risks without width limits",
        "suggestion": "Limit field width in format specifiers (e.g. %99s)",
    },

    # ── Temporary File Functions (Race Condition Risk) ───────────────────────
    "tmpnam": {
        "category": "Temporary File (Race Condition Risk)",
        "reason": "Race condition between name generation and file creation (TOCTOU)",
        "suggestion": "Use mkstemp() or tmpfile() instead",
    },
    "tempnam": {
        "category": "Temporary File (Race Condition Risk)",
        "reason": "Race condition between name generation and file creation (TOCTOU)",
        "suggestion": "Use mkstemp() or tmpfile() instead",
    },
    "tmpfile": {
        "category": "Temporary File (Race Condition Risk)",
        "reason": "Less risky than tmpnam() but still implementation-sensitive",
        "suggestion": "Use mkstemp() for full control over temp file creation",
    },

    # ── Memory / Environment Related Risk ────────────────────────────────────
    "getenv": {
        "category": "Memory / Environment Risk",
        "reason": "Returns pointer to environment which can be attacker-controlled or modified",
        "suggestion": "Use secure_getenv() (glibc) or validate/sanitize the returned value",
    },
    "alloca": {
        "category": "Memory Risk",
        "reason": "Allocates on the stack — no failure indication, stack overflow risk",
        "suggestion": "Use malloc() / calloc() with proper size checks instead",
    },

    # ── Weak Random Number Functions ─────────────────────────────────────────
    "rand": {
        "category": "Weak Random Number Generation",
        "reason": "Predictable PRNG — not suitable for security-sensitive contexts",
        "suggestion": "Use arc4random(), getrandom(), or /dev/urandom for secure randomness",
    },
    "srand": {
        "category": "Weak Random Number Generation",
        "reason": "Seeds the predictable rand() PRNG — not cryptographically secure",
        "suggestion": "Use arc4random() or getrandom() which don't need manual seeding",
    },
    "random": {
        "category": "Weak Random Number Generation",
        "reason": "Better than rand() but still not cryptographically secure",
        "suggestion": "Use arc4random() or getrandom() for security-sensitive contexts",
    },
    "drand48": {
        "category": "Weak Random Number Generation",
        "reason": "Predictable PRNG — not suitable for security-sensitive contexts",
        "suggestion": "Use arc4random() or getrandom() for secure randomness",
    },

    # ── Unsafe Type Conversion ───────────────────────────────────────────────
    "atoi": {
        "category": "Unsafe Type Conversion",
        "reason": "No error detection — undefined behavior on overflow, no way to detect failure",
        "suggestion": "Use strtol() with errno checking instead",
    },
    "atol": {
        "category": "Unsafe Type Conversion",
        "reason": "No error detection — undefined behavior on overflow, no way to detect failure",
        "suggestion": "Use strtol() with errno checking instead",
    },
    "atoll": {
        "category": "Unsafe Type Conversion",
        "reason": "No error detection — undefined behavior on overflow, no way to detect failure",
        "suggestion": "Use strtoll() with errno checking instead",
    },
    "atof": {
        "category": "Unsafe Type Conversion",
        "reason": "No error detection — no way to distinguish '0.0' input from conversion failure",
        "suggestion": "Use strtod() with errno checking instead",
    },

    # ── Process / Execution Functions (Command Injection Risk) ───────────────
    "system": {
        "category": "Process Execution (Command Injection Risk)",
        "reason": "Passes string to shell — vulnerable to command injection",
        "suggestion": "Use execve() or posix_spawn() with explicit argument arrays",
    },
    "popen": {
        "category": "Process Execution (Command Injection Risk)",
        "reason": "Passes string to shell — vulnerable to command injection",
        "suggestion": "Use pipe() + fork() + exec() with explicit argument arrays",
    },
    "execl": {
        "category": "Process Execution Risk",
        "reason": "Inherits environment — can be exploited via PATH or env manipulation",
        "suggestion": "Use execve() with explicit environment, or validate all arguments",
    },
    "execle": {
        "category": "Process Execution Risk",
        "reason": "Safer than execl() but still requires careful argument validation",
        "suggestion": "Validate all arguments and use absolute paths",
    },
    "execlp": {
        "category": "Process Execution Risk",
        "reason": "Searches PATH — attacker can place malicious binary in PATH",
        "suggestion": "Use execve() with absolute paths instead",
    },
    "execv": {
        "category": "Process Execution Risk",
        "reason": "Inherits environment — can be exploited via env manipulation",
        "suggestion": "Use execve() with explicit environment",
    },
    "execvp": {
        "category": "Process Execution Risk",
        "reason": "Searches PATH — attacker can place malicious binary in PATH",
        "suggestion": "Use execve() with absolute paths instead",
    },
    "execve": {
        "category": "Process Execution Risk",
        "reason": "Safest exec variant but still requires careful argument validation",
        "suggestion": "Validate all arguments and paths before calling",
    },

    # ── Signal Handling (Risky Usage) ────────────────────────────────────────
    "signal": {
        "category": "Unsafe Signal Handling",
        "reason": "Behavior varies across platforms — can cause race conditions",
        "suggestion": "Use sigaction() for reliable, portable signal handling",
    },

    # ── Dangerous Memory Functions ───────────────────────────────────────────
    "memcpy": {
        "category": "Dangerous Memory Operations",
        "reason": "Undefined behavior if source and destination buffers overlap",
        "suggestion": "Use memmove() if buffers may overlap, or verify non-overlap",
    },
    "memmove": {
        "category": "Dangerous Memory Operations",
        "reason": "Safer than memcpy() for overlapping buffers but still dangerous if size is wrong",
        "suggestion": "Always validate the size parameter against actual buffer sizes",
    },
    "memcmp": {
        "category": "Dangerous Memory Operations",
        "reason": "Not constant-time — unsafe for comparing secrets (timing side-channel attack)",
        "suggestion": "Use a constant-time comparison function for passwords/keys/tokens",
    },
    "bcopy": {
        "category": "Legacy / Obsolete",
        "reason": "Non-standard legacy BSD function — removed from POSIX.1-2008",
        "suggestion": "Use memmove() instead",
    },
    "bzero": {
        "category": "Legacy / Obsolete",
        "reason": "Deprecated BSD function — removed from POSIX.1-2008",
        "suggestion": "Use memset(buf, 0, size) instead",
    },

    # ── Dangerous File / I/O Functions ───────────────────────────────────────
    "getc": {
        "category": "Potentially Unsafe I/O",
        "reason": "Macro implementation can evaluate stream argument multiple times",
        "suggestion": "Use fgetc() for side-effect-safe single character reads",
    },
    "putc": {
        "category": "Potentially Unsafe I/O",
        "reason": "Macro implementation can evaluate arguments multiple times",
        "suggestion": "Use fputc() for side-effect-safe single character writes",
    },
    "getchar": {
        "category": "Potentially Unsafe I/O",
        "reason": "No input size control — may block or read unbounded input",
        "suggestion": "Use fgets() for controlled input reading",
    },
    "putchar": {
        "category": "Potentially Unsafe I/O",
        "reason": "No output error checking by default",
        "suggestion": "Check return value or use fputc() with error handling",
    },
    "rewind": {
        "category": "Potentially Unsafe I/O",
        "reason": "Silently clears error indicator — hides I/O failures",
        "suggestion": "Use fseek(fp, 0, SEEK_SET) and check return value for errors",
    },
    "freopen": {
        "category": "Potentially Unsafe I/O",
        "reason": "Can redirect critical streams (stdin/stdout/stderr) unexpectedly",
        "suggestion": "Use fopen() for new streams; avoid redirecting standard streams",
    },

    # ── Environment / User Info ──────────────────────────────────────────────
    "getlogin": {
        "category": "Unreliable Environment Info",
        "reason": "Not reliable — can be spoofed, may return NULL on some systems",
        "suggestion": "Use getpwuid(getuid()) for reliable user identification",
    },

    # ── Legacy / Obsolete ────────────────────────────────────────────────────
    "setbuf": {
        "category": "Legacy / Obsolete",
        "reason": "Cannot report errors — if buffer is too small, undefined behavior",
        "suggestion": "Use setvbuf() which returns an error code on failure",
    },
    "ctime": {
        "category": "Legacy / Obsolete (Not Thread-Safe)",
        "reason": "Returns pointer to static internal buffer — not thread-safe",
        "suggestion": "Use ctime_r() (POSIX) or strftime() instead",
    },
    "asctime": {
        "category": "Legacy / Obsolete (Not Thread-Safe)",
        "reason": "Returns pointer to static internal buffer — not thread-safe",
        "suggestion": "Use asctime_r() (POSIX) or strftime() instead",
    },
    "gmtime": {
        "category": "Legacy / Obsolete (Not Thread-Safe)",
        "reason": "Returns pointer to static internal buffer — not thread-safe",
        "suggestion": "Use gmtime_r() (POSIX) instead",
    },
    "localtime": {
        "category": "Legacy / Obsolete (Not Thread-Safe)",
        "reason": "Returns pointer to static internal buffer — not thread-safe",
        "suggestion": "Use localtime_r() (POSIX) instead",
    },
}


def check_unsafe_functions(
    buffer_refs: list[Reference],
    buffer_symbols: list[Symbol],
    repo_symbols: list[dict[str, Any]],
    current_file: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not current_file.endswith((".c", ".h")):
        return diagnostics

    for ref in buffer_refs:
        if ref.kind != "call":
            continue

        # Check removed-from-standard functions (ERROR)
        removed = REMOVED_FUNCTIONS.get(ref.name)
        if removed:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="ERROR",
                code="SNIPE_UNSAFE_FUNCTION",
                message=(
                    f"'{ref.name}()' — {removed['category']}. "
                    f"{removed['reason']}. "
                    f"{removed['suggestion']}."
                ),
            ))
            continue

        # Check discouraged functions (WARNING)
        unsafe = UNSAFE_FUNCTIONS.get(ref.name)
        if unsafe:
            diagnostics.append(Diagnostic(
                file=current_file,
                line=ref.line,
                severity="WARNING",
                code="SNIPE_UNSAFE_FUNCTION",
                message=(
                    f"'{ref.name}()' — {unsafe['category']}. "
                    f"{unsafe['reason']}. "
                    f"{unsafe['suggestion']}."
                ),
            ))

    return diagnostics
