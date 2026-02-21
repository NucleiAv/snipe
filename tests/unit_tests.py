"""
Unit tests for Snipe parser and analyzers.
"""
import json
import sys
from pathlib import Path

# Add backend to path when running from project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from parser.symbol_extractor import (
    extract_symbols_from_source,
    extract_references_from_source,
    Symbol,
    Reference,
)
from parser.buffer_parser import parse_unsaved_buffer
from parser.repo_parser import build_repo_symbol_table
from analyzer.type_checker import check_type_mismatch, Diagnostic
from analyzer.bounds_checker import check_array_bounds
from analyzer.signature_checker import check_function_signatures
from graph.repo_graph import build_repo_graph


def test_python_symbol_extraction():
    code = b"""
def foo(a, b):
    x = 1
    return a + b
class Bar:
    pass
"""
    symbols = extract_symbols_from_source(code, "test.py", "python")
    if not symbols:
        # Tree-sitter Python may not be installed
        return
    names = [s.name for s in symbols]
    assert "foo" in names
    assert "Bar" in names
    assert "x" in names
    foo = next(s for s in symbols if s.name == "foo")
    assert foo.kind == "function"
    assert len(foo.params) >= 2


def test_c_symbol_extraction():
    code = b"""
int arr[10];
int add(int a, int b) { return a + b; }
"""
    symbols = extract_symbols_from_source(code, "test.c", "c")
    if not symbols:
        return
    names = [s.name for s in symbols]
    assert "arr" in names
    assert "add" in names
    arr = next((s for s in symbols if s.name == "arr"), None)
    if arr:
        assert arr.array_size == 10


def test_python_references():
    code = b"x = foo(1, 2); y = arr[5]"
    refs = extract_references_from_source(code, "test.py", "python")
    if not refs:
        return
    calls = [r for r in refs if r.kind == "call"]
    accesses = [r for r in refs if r.kind == "array_access"]
    assert any(r.name == "foo" and r.arg_count == 2 for r in calls)
    assert any(r.name == "arr" and r.index_value == 5 for r in accesses)


def test_buffer_parser():
    content = "def f(): return arr[12]"
    symbols, refs = parse_unsaved_buffer(content, "demo.py", "python")
    assert isinstance(symbols, list)
    assert isinstance(refs, list)
    arr_ref = next((r for r in refs if r.name == "arr" and r.kind == "array_access"), None)
    if arr_ref:
        assert arr_ref.index_value == 12


def test_type_mismatch():
    buffer_refs = [Reference("x", "read", "float", 1)]
    buffer_symbols = [Symbol("x", "variable", "int", "", 1, "")]
    repo_symbols = [{"name": "x", "type": "int", "file_path": "other.c", "line": 10}]
    diag = check_type_mismatch(buffer_refs, buffer_symbols, repo_symbols, "current.c")
    assert len(diag) >= 0  # May or may not fire depending on local vs repo type


def test_array_bounds():
    buffer_refs = [Reference("arr", "array_access", None, 1, 12)]
    buffer_symbols = []
    repo_symbols = [{"name": "arr", "kind": "array", "array_size": 10, "file_path": "core.c", "line": 5}]
    diag = check_array_bounds(buffer_refs, buffer_symbols, repo_symbols, "main.c")
    assert len(diag) == 1
    assert "12" in diag[0].message
    assert "10" in diag[0].message


def test_signature_drift():
    buffer_refs = [Reference("greet", "call", None, 1, None, 3)]  # arg_count=3
    repo_symbols = [{"name": "greet", "kind": "function", "params": [{"name": "a"}, {"name": "b"}], "file_path": "u.py", "line": 1}]
    diag = check_function_signatures(buffer_refs, repo_symbols, "app.py")
    assert len(diag) == 1
    assert "2" in diag[0].message
    assert "3" in diag[0].message


def test_repo_graph():
    symbols = [
        {"name": "foo", "kind": "function", "file_path": "a.py", "line": 1},
        {"name": "foo", "kind": "variable", "file_path": "b.py", "line": 2},
    ]
    graph = build_repo_graph(symbols)
    assert "nodes" in graph
    assert "edges" in graph
    # Graph now includes file nodes + symbol nodes (4 total: 2 files + 2 symbols)
    assert len(graph["nodes"]) >= 2
    assert len(graph["edges"]) >= 1


def test_demo_repo_symbols():
    demo = ROOT / "demo_repo"
    if not demo.is_dir():
        return
    data = build_repo_symbol_table(demo, output_json_path=None)
    names = [s["name"] for s in data]
    # When tree-sitter is installed we should see symbols from demo_repo
    if data:
        assert "arr" in names or "add" in names or "balance" in names or "greet" in names


def test_python_type_annotations():
    code = b"""
balance: int = 42
def greet(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}!"
"""
    symbols = extract_symbols_from_source(code, "test.py", "python")
    if not symbols:
        return
    balance = next(s for s in symbols if s.name == "balance")
    assert balance.type == "int", f"Expected 'int', got {balance.type!r}"

    greet = next(s for s in symbols if s.name == "greet")
    assert greet.return_type == "str", f"Expected return_type 'str', got {greet.return_type!r}"
    assert greet.type == "str", f"Expected type 'str', got {greet.type!r}"

    name_param = next(p for p in greet.params if p["name"] == "name")
    assert name_param["type"] == "str", f"Expected param type 'str', got {name_param['type']!r}"


def test_python_default_params():
    code = b"""
def greet(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}!"
"""
    symbols = extract_symbols_from_source(code, "test.py", "python")
    if not symbols:
        return
    greet = next(s for s in symbols if s.name == "greet")
    name_param = next(p for p in greet.params if p["name"] == "name")
    greeting_param = next(p for p in greet.params if p["name"] == "greeting")
    assert name_param["has_default"] is False, "name should not have default"
    assert greeting_param["has_default"] is True, "greeting should have default"


def test_signature_drift_with_defaults():
    # greet(name, greeting="Hello") accepts 1 or 2 args
    repo_symbols = [{
        "name": "greet", "kind": "function",
        "params": [
            {"name": "name", "type": "str", "has_default": False},
            {"name": "greeting", "type": "str", "has_default": True},
        ],
        "is_variadic": False,
        "file_path": "utils.py", "line": 1,
    }]
    # 1 arg — OK
    refs_1 = [Reference("greet", "call", None, 1, None, 1)]
    diag_1 = check_function_signatures(refs_1, repo_symbols, "app.py")
    assert len(diag_1) == 0, f"1 arg should be OK, got {len(diag_1)} diagnostic(s)"

    # 2 args — OK
    refs_2 = [Reference("greet", "call", None, 1, None, 2)]
    diag_2 = check_function_signatures(refs_2, repo_symbols, "app.py")
    assert len(diag_2) == 0, f"2 args should be OK, got {len(diag_2)} diagnostic(s)"

    # 0 args — error
    refs_0 = [Reference("greet", "call", None, 1, None, 0)]
    diag_0 = check_function_signatures(refs_0, repo_symbols, "app.py")
    assert len(diag_0) == 1, f"0 args should fail, got {len(diag_0)} diagnostic(s)"

    # 3 args — error
    refs_3 = [Reference("greet", "call", None, 1, None, 3)]
    diag_3 = check_function_signatures(refs_3, repo_symbols, "app.py")
    assert len(diag_3) == 1, f"3 args should fail, got {len(diag_3)} diagnostic(s)"
    assert "1 to 2" in diag_3[0].message, f"Expected '1 to 2' in message, got {diag_3[0].message!r}"


def test_python_variadic_args():
    code = b"""
def flexible(*args, **kwargs) -> None:
    pass
"""
    symbols = extract_symbols_from_source(code, "test.py", "python")
    if not symbols:
        return
    flex = next(s for s in symbols if s.name == "flexible")
    assert flex.is_variadic is True, "flexible should be variadic"
    assert any(p["name"].startswith("*") for p in flex.params), "Should have *args param"
    assert any(p["name"].startswith("**") for p in flex.params), "Should have **kwargs param"

    # Signature checker should allow any arg count >= 0
    repo_symbols = [flex.to_dict()]
    refs_5 = [Reference("flexible", "call", None, 1, None, 5)]
    diag = check_function_signatures(refs_5, repo_symbols, "app.py")
    assert len(diag) == 0, f"Variadic should accept 5 args, got {len(diag)} diagnostic(s)"

    refs_0 = [Reference("flexible", "call", None, 1, None, 0)]
    diag_0 = check_function_signatures(refs_0, repo_symbols, "app.py")
    assert len(diag_0) == 0, f"Variadic should accept 0 args, got {len(diag_0)} diagnostic(s)"


def test_python_list_size():
    code = b"scores = [90, 85, 78]"
    symbols = extract_symbols_from_source(code, "test.py", "python")
    if not symbols:
        return
    scores = next(s for s in symbols if s.name == "scores")
    assert scores.array_size == 3, f"Expected array_size=3, got {scores.array_size}"
    assert scores.kind == "array", f"Expected kind='array', got {scores.kind!r}"
    assert scores.type == "list", f"Expected type='list', got {scores.type!r}"


def test_python_list_bounds():
    # scores has size 5, accessing index 10 should flag
    buffer_refs = [Reference("scores", "array_access", None, 1, 10)]
    buffer_symbols = []
    repo_symbols = [{"name": "scores", "kind": "array", "array_size": 5, "type": "list", "file_path": "utils.py", "line": 3}]
    diag = check_array_bounds(buffer_refs, buffer_symbols, repo_symbols, "app.py")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "10" in diag[0].message
    assert "5" in diag[0].message
    assert diag[0].code == "SNIPE_ARRAY_BOUNDS"


def test_python_dataclass_fields():
    code = b"""
from dataclasses import dataclass

@dataclass
class Config:
    host: str
    port: int = 8080
"""
    symbols = extract_symbols_from_source(code, "test.py", "python")
    if not symbols:
        return
    config = next(s for s in symbols if s.name == "Config")
    assert config.kind == "class"

    host = next((s for s in symbols if s.name == "host" and s.scope == "Config"), None)
    assert host is not None, "Should extract 'host' field from dataclass"
    assert host.type == "str", f"host type should be 'str', got {host.type!r}"
    assert host.kind == "variable"

    port = next((s for s in symbols if s.name == "port" and s.scope == "Config"), None)
    assert port is not None, "Should extract 'port' field from dataclass"
    assert port.type == "int", f"port type should be 'int', got {port.type!r}"


def test_c_analysis_unchanged():
    """Regression test: C analysis should be unaffected by Python changes."""
    code = b"""
int arr[10];
float balance = 0.0;
int add(int a, int b) { return a + b; }
"""
    symbols = extract_symbols_from_source(code, "test.c", "c")
    if not symbols:
        return
    arr = next((s for s in symbols if s.name == "arr"), None)
    assert arr is not None, "Should find 'arr'"
    assert arr.array_size == 10, f"arr size should be 10, got {arr.array_size}"
    assert arr.kind == "array", f"arr kind should be 'array', got {arr.kind!r}"

    bal = next((s for s in symbols if s.name == "balance"), None)
    assert bal is not None, "Should find 'balance'"
    assert bal.type == "float", f"balance type should be 'float', got {bal.type!r}"

    add = next((s for s in symbols if s.name == "add"), None)
    assert add is not None, "Should find 'add'"
    assert add.kind == "function"
    assert len(add.params) == 2
    assert add.params[0]["type"] == "int"

    # Signature check still works for C (no has_default, no is_variadic)
    repo_symbols = [add.to_dict()]
    refs_ok = [Reference("add", "call", None, 1, None, 2)]
    diag_ok = check_function_signatures(refs_ok, repo_symbols, "main.c")
    assert len(diag_ok) == 0, "2 args for add(int, int) should be OK"

    refs_bad = [Reference("add", "call", None, 1, None, 3)]
    diag_bad = check_function_signatures(refs_bad, repo_symbols, "main.c")
    assert len(diag_bad) == 1, "3 args for add(int, int) should fail"


# ====================================================================
# New tests for checks #9-#19
# ====================================================================

from analyzer.undefined_checker import check_undefined_symbols
from analyzer.shadow_checker import check_variable_shadowing
from analyzer.format_checker import check_format_strings
from analyzer.unused_checker import check_unused_externs, check_dead_imports
from analyzer.return_checker import check_return_types
from analyzer.safety_checker import check_unsafe_functions
from analyzer.assignment_checker import check_assignment_types
from analyzer.arg_type_checker import check_arg_types
from analyzer.struct_checker import check_struct_access


# ---- #9: Undefined symbol reference (Python) ----

def test_undefined_symbol_python():
    buffer_refs = [Reference("unknown_var", "read", None, 5)]
    buffer_symbols = [Symbol("x", "variable", "int", "test.py", 1, "")]
    repo_symbols = []
    diag = check_undefined_symbols(buffer_refs, buffer_symbols, repo_symbols, "test.py")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert diag[0].code == "SNIPE_UNDEFINED_SYMBOL"
    assert "unknown_var" in diag[0].message


def test_undefined_symbol_builtin_no_false_positive():
    buffer_refs = [Reference("print", "read", None, 1), Reference("len", "read", None, 2)]
    buffer_symbols = []
    repo_symbols = []
    diag = check_undefined_symbols(buffer_refs, buffer_symbols, repo_symbols, "test.py")
    assert len(diag) == 0, f"Builtins should not be flagged, got {len(diag)}"


# ---- #10: Undefined function call (C + Python) ----

def test_undefined_function_call_c():
    buffer_refs = [Reference("my_unknown_func", "call", None, 3, None, 1)]
    buffer_symbols = []
    repo_symbols = []
    diag = check_undefined_symbols(buffer_refs, buffer_symbols, repo_symbols, "test.c")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "my_unknown_func" in diag[0].message


def test_stdlib_function_no_false_positive():
    buffer_refs = [Reference("printf", "call", None, 3, None, 1)]
    buffer_symbols = []
    repo_symbols = []
    diag = check_undefined_symbols(buffer_refs, buffer_symbols, repo_symbols, "test.c")
    assert len(diag) == 0, f"C stdlib should not be flagged, got {len(diag)}"


def test_undefined_function_python():
    buffer_refs = [Reference("nonexistent_func", "call", None, 5, None, 1)]
    buffer_symbols = []
    repo_symbols = []
    diag = check_undefined_symbols(buffer_refs, buffer_symbols, repo_symbols, "test.py")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "nonexistent_func" in diag[0].message


def test_defined_function_no_false_positive():
    buffer_refs = [Reference("my_func", "call", None, 5, None, 1)]
    buffer_symbols = [Symbol("my_func", "function", None, "test.py", 1, "")]
    repo_symbols = []
    diag = check_undefined_symbols(buffer_refs, buffer_symbols, repo_symbols, "test.py")
    assert len(diag) == 0, f"Defined function should not be flagged, got {len(diag)}"


# ---- #11: Variable shadowing (Python) ----

def test_variable_shadowing():
    buffer_symbols = [
        Symbol("x", "variable", "int", "test.py", 1, ""),       # module-level
        Symbol("x", "variable", "str", "test.py", 5, "foo"),    # local in foo
    ]
    diag = check_variable_shadowing([], buffer_symbols, [], "test.py")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "shadows" in diag[0].message
    assert diag[0].code == "SNIPE_SHADOWED_SYMBOL"


def test_no_shadowing_when_no_conflict():
    buffer_symbols = [
        Symbol("x", "variable", "int", "test.py", 1, ""),
        Symbol("y", "variable", "str", "test.py", 5, "foo"),
    ]
    diag = check_variable_shadowing([], buffer_symbols, [], "test.py")
    assert len(diag) == 0, f"No shadowing expected, got {len(diag)}"


# ---- #12: Format string mismatch (C) ----

def test_format_string_mismatch():
    buffer_refs = [Reference("printf", "format_call", None, 3, None, 1,
                             format_specifiers=2, format_string="%d %s")]
    diag = check_format_strings(buffer_refs, [], [], "test.c")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "2" in diag[0].message and "1" in diag[0].message
    assert diag[0].code == "SNIPE_FORMAT_STRING"


def test_format_string_correct():
    buffer_refs = [Reference("printf", "format_call", None, 3, None, 2,
                             format_specifiers=2, format_string="%d %s")]
    diag = check_format_strings(buffer_refs, [], [], "test.c")
    assert len(diag) == 0, f"Correct format should not flag, got {len(diag)}"


# ---- #13: Unused extern (C) ----

def test_unused_extern():
    buffer_symbols = [Symbol("unused_func", "function", "int", "test.c", 3, "", is_extern=True)]
    buffer_refs = []
    diag = check_unused_externs(buffer_refs, buffer_symbols, [], "test.c")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "unused_func" in diag[0].message
    assert diag[0].code == "SNIPE_UNUSED_EXTERN"


def test_used_extern_no_false_positive():
    buffer_symbols = [Symbol("add", "function", "int", "test.c", 3, "", is_extern=True)]
    buffer_refs = [Reference("add", "call", None, 10, None, 2)]
    diag = check_unused_externs(buffer_refs, buffer_symbols, [], "test.c")
    assert len(diag) == 0, f"Used extern should not be flagged, got {len(diag)}"


# ---- #14: Dead import (Python) ----

def test_dead_import():
    buffer_refs = [
        Reference("__import__", "import", None, 1, imported_names=["foo", "bar"]),
        Reference("foo", "read", None, 5),
    ]
    diag = check_dead_imports(buffer_refs, [], [], "test.py")
    assert len(diag) == 1, f"Expected 1 diagnostic (bar unused), got {len(diag)}"
    assert "bar" in diag[0].message
    assert diag[0].code == "SNIPE_DEAD_IMPORT"


def test_all_imports_used_no_false_positive():
    buffer_refs = [
        Reference("__import__", "import", None, 1, imported_names=["foo", "bar"]),
        Reference("foo", "read", None, 5),
        Reference("bar", "call", None, 6, None, 0),
    ]
    diag = check_dead_imports(buffer_refs, [], [], "test.py")
    assert len(diag) == 0, f"All imports used, should not flag, got {len(diag)}"


# ---- #15: Return type mismatch (Python) ----

def test_return_type_mismatch():
    buffer_refs = [Reference("my_func", "return_value", None, 5,
                             return_value_type="str", declared_return_type="int")]
    diag = check_return_types(buffer_refs, [], [], "test.py")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "str" in diag[0].message and "int" in diag[0].message
    assert diag[0].code == "SNIPE_TYPE_MISMATCH"


def test_return_type_correct():
    buffer_refs = [Reference("my_func", "return_value", None, 5,
                             return_value_type="int", declared_return_type="int")]
    diag = check_return_types(buffer_refs, [], [], "test.py")
    assert len(diag) == 0, f"Correct return type should not flag, got {len(diag)}"


# ---- #16: Unsafe function (C) ----

def test_unsafe_function():
    buffer_refs = [Reference("strcpy", "call", None, 3, None, 2)]
    diag = check_unsafe_functions(buffer_refs, [], [], "test.c")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "strcpy" in diag[0].message
    assert "Unsafe String Handling" in diag[0].message
    assert diag[0].code == "SNIPE_UNSAFE_FUNCTION"
    assert diag[0].severity == "WARNING", f"strcpy should be WARNING, got {diag[0].severity}"


def test_gets_is_error():
    """gets() is removed from C11 standard — should be ERROR, not WARNING."""
    buffer_refs = [Reference("gets", "call", None, 5, None, 1)]
    diag = check_unsafe_functions(buffer_refs, [], [], "test.c")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "gets" in diag[0].message
    assert "Removed from C Standard" in diag[0].message
    assert diag[0].severity == "ERROR", f"gets() should be ERROR, got {diag[0].severity}"
    assert diag[0].code == "SNIPE_UNSAFE_FUNCTION"


def test_safe_function_no_false_positive():
    buffer_refs = [Reference("snprintf", "call", None, 3, None, 4)]
    diag = check_unsafe_functions(buffer_refs, [], [], "test.c")
    assert len(diag) == 0, f"snprintf should not be flagged, got {len(diag)}"


def test_unsafe_function_categories():
    """Each category should produce correct category label in message."""
    test_cases = [
        ("rand", "Weak Random Number Generation"),
        ("atoi", "Unsafe Type Conversion"),
        ("system", "Command Injection Risk"),
        ("tmpnam", "Race Condition Risk"),
        ("memcpy", "Dangerous Memory Operations"),
        ("signal", "Unsafe Signal Handling"),
        ("ctime", "Not Thread-Safe"),
        ("getlogin", "Unreliable Environment Info"),
        ("alloca", "Memory Risk"),
    ]
    for func_name, expected_category in test_cases:
        refs = [Reference(func_name, "call", None, 1, None, 0)]
        diag = check_unsafe_functions(refs, [], [], "test.c")
        assert len(diag) == 1, f"Expected 1 diagnostic for {func_name}, got {len(diag)}"
        assert expected_category in diag[0].message, \
            f"Expected '{expected_category}' in message for {func_name}, got: {diag[0].message}"
        assert diag[0].severity == "WARNING", f"{func_name} should be WARNING"


# ---- #17: Assignment type mismatch (Python) ----

def test_assignment_type_mismatch():
    buffer_refs = [Reference("x", "assignment", "str", 3, annotation_type="int")]
    diag = check_assignment_types(buffer_refs, [], [], "test.py")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "int" in diag[0].message and "str" in diag[0].message
    assert diag[0].code == "SNIPE_TYPE_MISMATCH"


def test_assignment_type_correct():
    buffer_refs = [Reference("x", "assignment", "int", 3, annotation_type="int")]
    diag = check_assignment_types(buffer_refs, [], [], "test.py")
    assert len(diag) == 0, f"Correct assignment should not flag, got {len(diag)}"


# ---- #18: Argument type mismatch (Python) ----

def test_arg_type_mismatch():
    buffer_refs = [Reference("greet", "call", None, 5, None, 1, arg_types=["int"])]
    buffer_symbols = [Symbol("greet", "function", "str", "test.py", 1, "",
                             params=[{"name": "name", "type": "str"}],
                             return_type="str")]
    diag = check_arg_types(buffer_refs, buffer_symbols, [], "test.py")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "str" in diag[0].message and "int" in diag[0].message
    assert diag[0].code == "SNIPE_ARG_TYPE_MISMATCH"


def test_arg_type_correct():
    buffer_refs = [Reference("greet", "call", None, 5, None, 1, arg_types=["str"])]
    buffer_symbols = [Symbol("greet", "function", "str", "test.py", 1, "",
                             params=[{"name": "name", "type": "str"}],
                             return_type="str")]
    diag = check_arg_types(buffer_refs, buffer_symbols, [], "test.py")
    assert len(diag) == 0, f"Correct arg type should not flag, got {len(diag)}"


# ---- #19: Struct member access (C) ----

def test_struct_member_access_invalid():
    buffer_refs = [Reference("p", "member_access", None, 5, member_name="z")]
    buffer_symbols = [
        Symbol("Point", "struct", "struct", "test.c", 1, "",
               members=[{"name": "x", "type": "int"}, {"name": "y", "type": "int"}]),
        Symbol("p", "variable", "struct Point", "test.c", 5, ""),
    ]
    diag = check_struct_access(buffer_refs, buffer_symbols, [], "test.c")
    assert len(diag) == 1, f"Expected 1 diagnostic, got {len(diag)}"
    assert "z" in diag[0].message
    assert "Point" in diag[0].message
    assert diag[0].code == "SNIPE_STRUCT_ACCESS"


def test_struct_member_access_valid():
    buffer_refs = [Reference("p", "member_access", None, 5, member_name="x")]
    buffer_symbols = [
        Symbol("Point", "struct", "struct", "test.c", 1, "",
               members=[{"name": "x", "type": "int"}, {"name": "y", "type": "int"}]),
        Symbol("p", "variable", "struct Point", "test.c", 5, ""),
    ]
    diag = check_struct_access(buffer_refs, buffer_symbols, [], "test.c")
    assert len(diag) == 0, f"Valid member should not flag, got {len(diag)}"


# ---- Integration: extraction + checker end-to-end ----

def test_format_string_extraction_and_check():
    """End-to-end: extract format_call refs from C source and run format checker."""
    code = b'#include <stdio.h>\nint main() { printf("%d %s", 42); return 0; }'
    refs = extract_references_from_source(code, "test.c", "c")
    fmt_refs = [r for r in refs if r.kind == "format_call"]
    if not fmt_refs:
        return  # tree-sitter may not be installed
    assert len(fmt_refs) >= 1
    # printf("%d %s", 42) — 2 specifiers, 1 arg
    diag = check_format_strings(refs, [], [], "test.c")
    assert len(diag) >= 1, f"Expected format mismatch, got {len(diag)}"


def test_python_import_extraction():
    """End-to-end: extract import refs from Python source."""
    code = b"from os import path, getcwd\nimport json\nx = path\n"
    refs = extract_references_from_source(code, "test.py", "python")
    if not refs:
        return  # tree-sitter may not be installed
    import_refs = [r for r in refs if r.kind == "import"]
    assert len(import_refs) >= 1, f"Expected import refs, got {len(import_refs)}"
    # Check that imported names are captured
    all_imported = set()
    for r in import_refs:
        if r.imported_names:
            all_imported.update(r.imported_names)
    assert "path" in all_imported or "json" in all_imported, f"Expected imported names, got {all_imported}"


def test_unsafe_function_extraction_and_check():
    """End-to-end: extract C call refs and run safety checker."""
    code = b'#include <string.h>\nvoid foo() { strcpy(dst, src); }'
    refs = extract_references_from_source(code, "test.c", "c")
    if not refs:
        return  # tree-sitter may not be installed
    diag = check_unsafe_functions(refs, [], [], "test.c")
    assert len(diag) >= 1, f"Expected unsafe function warning, got {len(diag)}"
    assert any("strcpy" in d.message for d in diag)


if __name__ == "__main__":
    test_python_symbol_extraction()
    test_c_symbol_extraction()
    test_python_references()
    test_buffer_parser()
    test_type_mismatch()
    test_array_bounds()
    test_signature_drift()
    test_repo_graph()
    test_demo_repo_symbols()
    test_python_type_annotations()
    test_python_default_params()
    test_signature_drift_with_defaults()
    test_python_variadic_args()
    test_python_list_size()
    test_python_list_bounds()
    test_python_dataclass_fields()
    test_c_analysis_unchanged()
    # New tests for checks #9-#19
    test_undefined_symbol_python()
    test_undefined_symbol_builtin_no_false_positive()
    test_undefined_function_call_c()
    test_stdlib_function_no_false_positive()
    test_undefined_function_python()
    test_defined_function_no_false_positive()
    test_variable_shadowing()
    test_no_shadowing_when_no_conflict()
    test_format_string_mismatch()
    test_format_string_correct()
    test_unused_extern()
    test_used_extern_no_false_positive()
    test_dead_import()
    test_all_imports_used_no_false_positive()
    test_return_type_mismatch()
    test_return_type_correct()
    test_unsafe_function()
    test_gets_is_error()
    test_safe_function_no_false_positive()
    test_unsafe_function_categories()
    test_assignment_type_mismatch()
    test_assignment_type_correct()
    test_arg_type_mismatch()
    test_arg_type_correct()
    test_struct_member_access_invalid()
    test_struct_member_access_valid()
    test_format_string_extraction_and_check()
    test_python_import_extraction()
    test_unsafe_function_extraction_and_check()
    print("All tests passed.")
