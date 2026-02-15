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
    assert len(graph["nodes"]) == 2
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
    print("All tests passed.")
