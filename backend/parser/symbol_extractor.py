"""
AST symbol extraction using Tree-sitter.
Extracts variables, functions, arrays, types with metadata (name, type, file, line, scope).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import tree_sitter
    from tree_sitter import Language, Parser, Node
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
    tree_sitter = None
    Language = Parser = Node = None


@dataclass
class Symbol:
    name: str
    kind: str  # variable, function, array, class, struct
    type: Optional[str] = None
    file_path: str = ""
    line: int = 0
    scope: str = ""
    array_size: Optional[int] = None
    params: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    return_type: Optional[str] = None
    is_variadic: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "type": self.type,
            "file_path": self.file_path,
            "line": self.line,
            "scope": self.scope,
            "array_size": self.array_size,
            "params": self.params,
            "references": self.references,
            "return_type": self.return_type,
            "is_variadic": self.is_variadic,
        }


@dataclass
class Reference:
    name: str
    kind: str  # call, read, array_access
    inferred_type: Optional[str] = None
    line: int = 0
    index_value: Optional[int] = None  # for array[index]
    arg_count: Optional[int] = None  # for function calls


def _get_language(lang_name: str):
    if not HAS_TREE_SITTER:
        return None
    try:
        if lang_name == "python":
            import tree_sitter_python as py_mod
            lang = getattr(py_mod, "LANGUAGE", None)
            if lang is None and callable(getattr(py_mod, "language", None)):
                lang = py_mod.language()
            return lang
        if lang_name == "c":
            import tree_sitter_c as c_mod
            lang = getattr(c_mod, "LANGUAGE", None)
            if lang is None and callable(getattr(c_mod, "language", None)):
                lang = c_mod.language()
            return lang
    except ImportError:
        pass
    return None


def _wrap_language(lang) -> Optional[Any]:
    """Wrap PyCapsule from language packages into tree_sitter.Language if needed."""
    if not HAS_TREE_SITTER or lang is None:
        return None
    if isinstance(lang, Language):
        return lang
    # Newer tree-sitter-python / tree-sitter-c expose a PyCapsule; Parser() needs Language.
    try:
        return Language(lang)
    except TypeError:
        return None


def _get_parser(lang_name: str) -> Optional[Parser]:
    if not HAS_TREE_SITTER:
        return None
    lang = _get_language(lang_name)
    lang = _wrap_language(lang)
    if lang is None:
        return None
    parser = Parser(lang)
    return parser


def _source_at(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _line_of(node: Node, source: bytes) -> int:
    return source[:node.start_byte].count(b"\n") + 1


def _get_python_type_annotation(node: Node, source: bytes) -> Optional[str]:
    """Extract type string from a tree-sitter annotation node."""
    if node is None:
        return None
    text = _source_at(node, source).strip()
    # Strip leading ': ' or '-> ' that tree-sitter may include
    if text.startswith("->"):
        text = text[2:].strip()
    if text.startswith(":"):
        text = text[1:].strip()
    return text if text else None


def _infer_type_from_rhs(node: Node) -> Optional[str]:
    """Infer Python type from a right-hand-side literal node type."""
    _TYPE_MAP = {
        "list": "list",
        "tuple": "tuple",
        "integer": "int",
        "float": "float",
        "string": "str",
        "true": "bool",
        "false": "bool",
        "dictionary": "dict",
    }
    return _TYPE_MAP.get(node.type)


def _count_elements(node: Node) -> int:
    """Count element children of a list/tuple node (skip brackets and commas)."""
    skip = {"(", ")", "[", "]", ","}
    return sum(1 for c in node.children if c.type not in skip)


def _extract_python_symbols(source: bytes, file_path: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    parser = _get_parser("python")
    if parser is None:
        return symbols
    tree = parser.parse(source)
    if tree.root_node is None:
        return symbols

    def walk(node: Node, scope: str):
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source_at(name_node, source).strip()
                params_node = node.child_by_field_name("parameters")
                params = []
                is_variadic = False
                if params_node:
                    for c in params_node.children:
                        pname = _source_at(c, source).strip()
                        if c.type == "identifier":
                            if pname in ("self", "cls"):
                                continue
                            params.append({"name": pname, "type": None, "has_default": False})
                        elif c.type == "typed_parameter":
                            id_node = c.child_by_field_name("name") or next((sc for sc in c.children if sc.type == "identifier"), None)
                            ptype_node = c.child_by_field_name("type")
                            id_name = _source_at(id_node, source).strip() if id_node else pname
                            if id_name in ("self", "cls"):
                                continue
                            ptype = _get_python_type_annotation(ptype_node, source) if ptype_node else None
                            params.append({"name": id_name, "type": ptype, "has_default": False})
                        elif c.type == "default_parameter":
                            id_node = c.child_by_field_name("name") or next((sc for sc in c.children if sc.type == "identifier"), None)
                            id_name = _source_at(id_node, source).strip() if id_node else pname
                            if id_name in ("self", "cls"):
                                continue
                            params.append({"name": id_name, "type": None, "has_default": True})
                        elif c.type == "typed_default_parameter":
                            id_node = c.child_by_field_name("name") or next((sc for sc in c.children if sc.type == "identifier"), None)
                            ptype_node = c.child_by_field_name("type")
                            id_name = _source_at(id_node, source).strip() if id_node else pname
                            if id_name in ("self", "cls"):
                                continue
                            ptype = _get_python_type_annotation(ptype_node, source) if ptype_node else None
                            params.append({"name": id_name, "type": ptype, "has_default": True})
                        elif c.type == "list_splat_pattern":
                            is_variadic = True
                            id_node = next((sc for sc in c.children if sc.type == "identifier"), None)
                            id_name = _source_at(id_node, source).strip() if id_node else "args"
                            params.append({"name": f"*{id_name}", "type": None, "has_default": False})
                        elif c.type == "dictionary_splat_pattern":
                            is_variadic = True
                            id_node = next((sc for sc in c.children if sc.type == "identifier"), None)
                            id_name = _source_at(id_node, source).strip() if id_node else "kwargs"
                            params.append({"name": f"**{id_name}", "type": None, "has_default": False})

                # Extract return type annotation
                ret_type_node = node.child_by_field_name("return_type")
                ret_type = _get_python_type_annotation(ret_type_node, source) if ret_type_node else None

                symbols.append(Symbol(
                    name=name, kind="function", type=ret_type,
                    file_path=file_path, line=_line_of(node, source), scope=scope,
                    params=params, return_type=ret_type, is_variadic=is_variadic,
                ))
                inner_scope = f"{scope}.{name}" if scope else name
                for c in node.children:
                    walk(c, inner_scope)
            return

        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source_at(name_node, source).strip()
                symbols.append(Symbol(
                    name=name, kind="class", type=None,
                    file_path=file_path, line=_line_of(node, source), scope=scope
                ))
                inner_scope = f"{scope}.{name}" if scope else name
                # Walk children — assignments (including annotated ones like
                # dataclass fields) are handled by the assignment branch below.
                for c in node.children:
                    walk(c, inner_scope)
            return

        if node.type == "assignment":
            # Get the RHS value node
            rhs_node = node.child_by_field_name("right") or (node.children[-1] if len(node.children) >= 3 else None)
            # Get the type annotation node (for annotated assignments like `x: int = 5`)
            type_node = node.child_by_field_name("type")
            explicit_type = _get_python_type_annotation(type_node, source) if type_node else None

            for c in node.children:
                if c.type == "identifier":
                    name = _source_at(c, source).strip()
                    if name and not name.startswith("_"):
                        inferred_type = explicit_type
                        array_size = None
                        kind = "variable"
                        if rhs_node and inferred_type is None:
                            inferred_type = _infer_type_from_rhs(rhs_node)
                        if rhs_node and rhs_node.type in ("list", "tuple"):
                            array_size = _count_elements(rhs_node)
                            kind = "array"
                        symbols.append(Symbol(
                            name=name, kind=kind, type=inferred_type,
                            file_path=file_path, line=_line_of(node, source), scope=scope,
                            array_size=array_size,
                        ))
                    break
                if c.type in ("tuple_pattern", "list_pattern"):
                    for sub in c.children:
                        if sub.type == "identifier":
                            name = _source_at(sub, source).strip()
                            if name and not name.startswith("_"):
                                symbols.append(Symbol(
                                    name=name, kind="variable", type=None,
                                    file_path=file_path, line=_line_of(node, source), scope=scope
                                ))

        for c in node.children:
            walk(c, scope)

    walk(tree.root_node, "")
    return symbols


def _extract_c_symbols(source: bytes, file_path: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    parser = _get_parser("c")
    if parser is None:
        return symbols
    tree = parser.parse(source)
    if tree.root_node is None:
        return symbols

    def get_type_str(decl_node: Node) -> str:
        type_parts = []
        for c in decl_node.children:
            if c.type in ("primitive_type", "sized_type_specifier", "type_identifier", "struct_specifier"):
                type_parts.append(_source_at(c, source).strip())
            if c.type == "pointer_declarator" and c.child_count:
                type_parts.append("*")
        return " ".join(type_parts) if type_parts else "int"

    def get_array_size(decl_node: Node) -> Optional[int]:
        declarator = decl_node.child_by_field_name("declarator")
        if not declarator:
            return None
        return get_array_size_from_declarator(declarator)

    def get_array_size_from_declarator(decl_node: Node) -> Optional[int]:
        if decl_node.type == "array_declarator":
            size_node = decl_node.child_by_field_name("size")
            if size_node:
                try:
                    return int(_source_at(size_node, source).strip(), 0)
                except ValueError:
                    pass
            for sub in decl_node.children:
                if sub.type == "number_literal":
                    try:
                        return int(_source_at(sub, source).strip(), 0)
                    except ValueError:
                        return None
        for c in decl_node.children:
            if c.type == "array_declarator":
                return get_array_size_from_declarator(c)
        return None

    def _identifier_from_declarator(decl_node: Node, src: bytes) -> Optional[str]:
        if decl_node.type == "identifier":
            return _source_at(decl_node, src).strip()
        for c in decl_node.children:
            if c.type == "identifier":
                return _source_at(c, src).strip()
            sub = _identifier_from_declarator(c, src)
            if sub:
                return sub
        return None

    def walk(node: Node):
        if node.type == "function_definition":
            declarator = node.child_by_field_name("declarator")
            if declarator and declarator.type == "function_declarator":
                id_node = declarator.child_by_field_name("declarator")
                if id_node and id_node.type == "identifier":
                    name = _source_at(id_node, source).strip()
                    params_node = declarator.child_by_field_name("parameters")
                    params = []
                    if params_node:
                        for c in params_node.children:
                            if c.type == "parameter_declaration":
                                pdecl = c.child_by_field_name("declarator")
                                if pdecl and pdecl.type == "identifier":
                                    params.append({"name": _source_at(pdecl, source).strip(), "type": get_type_str(c)})
                    symbols.append(Symbol(
                        name=name, kind="function", type=get_type_str(node),
                        file_path=file_path, line=_line_of(node, source), scope="",
                        params=params
                    ))
        if node.type == "declaration":
            type_str = get_type_str(node)
            decl_list = node.child_by_field_name("declarator") or node.child_by_field_name("init_declarator_list")
            if decl_list:
                for c in decl_list.children:
                    if c.type == "init_declarator":
                        d = c.child_by_field_name("declarator") or c
                        size = get_array_size_from_declarator(d)
                        name = _identifier_from_declarator(d, source)
                        if name:
                            symbols.append(Symbol(
                                name=name, kind="array" if size is not None else "variable",
                                type=type_str, file_path=file_path, line=_line_of(node, source),
                                scope="", array_size=size
                            ))
                    elif c.type == "identifier":
                        name = _source_at(c, source).strip()
                        symbols.append(Symbol(
                            name=name, kind="variable",
                            type=type_str, file_path=file_path, line=_line_of(node, source),
                            scope="", array_size=None
                        ))
        if node.type == "struct_specifier":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source_at(name_node, source).strip()
                symbols.append(Symbol(
                    name=name, kind="struct", type="struct",
                    file_path=file_path, line=_line_of(node, source), scope=""
                ))
        for c in node.children:
            walk(c)

    walk(tree.root_node)

    # Set array_size from source line when tree didn't give it (e.g. "int arr[10];")
    try:
        lines = source.decode("utf-8", errors="replace").splitlines()
    except Exception:
        lines = []
    for s in symbols:
        if s.array_size is not None:
            continue
        idx = s.line - 1
        if 0 <= idx < len(lines):
            line = lines[idx]
            m = re.search(r"\b" + re.escape(s.name) + r"\s*\[\s*(\d+)\s*\]", line)
            if m:
                try:
                    s.array_size = int(m.group(1), 10)
                    s.kind = "array"
                except ValueError:
                    pass
    return symbols


def extract_symbols_from_source(source: bytes, file_path: str, language: Optional[str] = None) -> list[Symbol]:
    if language is None:
        ext = Path(file_path).suffix.lower()
        if ext == ".py":
            language = "python"
        elif ext in (".c", ".h"):
            language = "c"
        else:
            return []
    if language == "python":
        return _extract_python_symbols(source, file_path)
    if language == "c":
        return _extract_c_symbols(source, file_path)
    return []


def extract_references_from_source(source: bytes, file_path: str, language: Optional[str] = None) -> list[Reference]:
    refs: list[Reference] = []
    if language is None:
        ext = Path(file_path).suffix.lower()
        if ext == ".py":
            language = "python"
        elif ext in (".c", ".h"):
            language = "c"
        else:
            return refs

    parser = _get_parser(language)
    if parser is None:
        return refs
    tree = parser.parse(source)
    if tree.root_node is None:
        return refs

    def walk(node: Node):
        if node.type in ("call_expression", "call") and language == "python":
            fn = node.child_by_field_name("function")
            if fn:
                name = _source_at(fn, source).strip()
                args = node.child_by_field_name("arguments")
                nargs = len([c for c in args.children if c.type not in ("(", ")", ",")]) if args else 0
                refs.append(Reference(name=name, kind="call", line=_line_of(node, source), arg_count=nargs))
        if node.type in ("call_expression", "call") and language == "c":
            fn = node.child_by_field_name("function")
            if fn and fn.type == "identifier":
                name = _source_at(fn, source).strip()
                args = node.child_by_field_name("arguments")
                nargs = len([c for c in args.children if c.type not in ("(", ")", ",")]) if args else 0
                refs.append(Reference(name=name, kind="call", line=_line_of(node, source), arg_count=nargs))
        if node.type in ("subscript_expression", "subscript") and language == "python":
            obj = node.child_by_field_name("value")
            idx = node.child_by_field_name("subscript") or node.child_by_field_name("index")
            if obj and idx:
                name = _source_at(obj, source).strip()
                idx_str = _source_at(idx, source).strip()
                try:
                    index_val = int(idx_str, 0)
                except ValueError:
                    index_val = None
                refs.append(Reference(name=name, kind="array_access", line=_line_of(node, source), index_value=index_val))
        if node.type == "array_declarator" or (node.type in ("subscript_expression", "subscript") and language == "c"):
            if language == "c" and node.type in ("subscript_expression", "subscript"):
                arr = node.child_by_field_name("argument")
                idx = node.child_by_field_name("index")
                # Some tree-sitter-c versions use different fields; try positional fallback (array, '[', index, ']').
                if (not arr or not idx) and len(node.children) >= 4:
                    arr = node.children[0]
                    idx = node.children[2]
                if arr and idx:
                    name = _source_at(arr, source).strip()
                    idx_str = _source_at(idx, source).strip()
                    try:
                        index_val = int(idx_str, 0)
                    except ValueError:
                        index_val = None
                    refs.append(Reference(name=name, kind="array_access", line=_line_of(node, source), index_value=index_val))
        if node.type == "identifier" and language == "python":
            parent = node.parent
            if parent and parent.type not in ("call_expression", "call", "function_definition", "parameters", "attribute"):
                name = _source_at(node, source).strip()
                if name and not name.startswith("_"):
                    refs.append(Reference(name=name, kind="read", line=_line_of(node, source)))
        for c in node.children:
            walk(c)

    walk(tree.root_node)

    # Fallback for C: always scan with regex for identifier[number] (tree-sitter often misses subscript in C)
    if language == "c":
        import logging
        n_before = len(refs)
        for m in re.finditer(rb"([a-zA-Z_][a-zA-Z0-9_]*)\s*\[\s*(\d+)\s*\]", source):
            name = m.group(1).decode("utf-8", errors="replace")
            try:
                index_val = int(m.group(2), 10)
            except ValueError:
                index_val = None
            line = source[: m.start()].count(b"\n") + 1
            refs.append(Reference(name=name, kind="array_access", line=line, index_value=index_val))
        if len(refs) > n_before:
            logging.getLogger(__name__).info("C regex fallback added %d array_access ref(s)", len(refs) - n_before)

    return refs
