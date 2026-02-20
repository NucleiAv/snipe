
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
    is_extern: bool = False
    members: list[dict[str, Any]] = field(default_factory=list)  # struct members [{name, type}]

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
            "is_extern": self.is_extern,
            "members": self.members,
        }


@dataclass
class Reference:
    name: str
    kind: str  # call, read, array_access, array_write, import, return_value, format_call, assignment, member_access
    inferred_type: Optional[str] = None
    line: int = 0
    index_value: Optional[int] = None  # for array[index]
    arg_count: Optional[int] = None  # for function calls
    rhs_name: Optional[str] = None  # for array_write: RHS identifier when inferred_type is None
    # --- New fields for checks #9-#19 ---
    format_specifiers: Optional[int] = None      # #12: count of format specifiers in printf
    format_string: Optional[str] = None           # #12: raw format string for diagnostics
    imported_names: Optional[list[str]] = None    # #14: names from import statement
    module_name: Optional[str] = None             # #14: module being imported
    return_value_type: Optional[str] = None       # #15: inferred type of return expression
    declared_return_type: Optional[str] = None    # #15: function's declared return type
    scope: Optional[str] = None                   # #11, #15: enclosing function/class scope
    annotation_type: Optional[str] = None         # #17: type annotation on LHS of assignment
    arg_types: Optional[list[Optional[str]]] = None  # #18: inferred types of each call argument
    member_name: Optional[str] = None             # #19: member being accessed


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


def _infer_c_expr_type(node: Node, source: bytes) -> Optional[str]:
    """Infer C expression type for array write RHS: number_literal -> int, etc."""
    if not node:
        return None
    if node.type == "number_literal":
        txt = _source_at(node, source)
        if "." in txt or "e" in txt.lower() or "f" in txt.lower():
            return "float"
        return "int"
    if node.type in ("char_literal", "string_literal"):
        return "char"
    if node.type == "identifier":
        return None  # caller looks up from symbols
    # binary_expression, conditional_expression, unary_expression, etc. – recurse
    for c in node.children:
        t = _infer_c_expr_type(c, source)
        if t:
            return t
    return "int"


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
            is_extern = any(
                c.type == "storage_class_specifier" and _source_at(c, source).strip() == "extern"
                for c in node.children
            )
            decl_list = node.child_by_field_name("declarator") or node.child_by_field_name("init_declarator_list")
            if decl_list:
                # If declarator is directly an identifier (e.g. "struct Point p;"), handle it
                if decl_list.type == "identifier":
                    name = _source_at(decl_list, source).strip()
                    symbols.append(Symbol(
                        name=name, kind="variable",
                        type=type_str, file_path=file_path, line=_line_of(node, source),
                        scope="", array_size=None, is_extern=is_extern,
                    ))
                else:
                    for c in decl_list.children:
                        if c.type == "init_declarator":
                            d = c.child_by_field_name("declarator") or c
                            size = get_array_size_from_declarator(d)
                            name = _identifier_from_declarator(d, source)
                            if name:
                                symbols.append(Symbol(
                                    name=name, kind="array" if size is not None else "variable",
                                    type=type_str, file_path=file_path, line=_line_of(node, source),
                                    scope="", array_size=size, is_extern=is_extern,
                                ))
                        elif c.type == "identifier":
                            name = _source_at(c, source).strip()
                            symbols.append(Symbol(
                                name=name, kind="variable",
                                type=type_str, file_path=file_path, line=_line_of(node, source),
                                scope="", array_size=None, is_extern=is_extern,
                            ))
        if node.type == "struct_specifier":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source_at(name_node, source).strip()
                # #19: Extract struct members from body (field_declaration_list)
                members = []
                body = node.child_by_field_name("body")
                if body:
                    for field_decl in body.children:
                        if field_decl.type == "field_declaration":
                            field_type = get_type_str(field_decl)
                            field_declarator = field_decl.child_by_field_name("declarator")
                            if field_declarator:
                                # tree-sitter uses field_identifier for struct members
                                if field_declarator.type == "field_identifier":
                                    field_name = _source_at(field_declarator, source).strip()
                                else:
                                    field_name = _identifier_from_declarator(field_declarator, source)
                                if field_name:
                                    members.append({"name": field_name, "type": field_type})
                symbols.append(Symbol(
                    name=name, kind="struct", type="struct",
                    file_path=file_path, line=_line_of(node, source), scope="",
                    members=members,
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


def _get_comment_and_string_ranges_c(source: bytes) -> list[tuple[int, int]]:
    """Return (start_byte, end_byte) ranges for C comments and string literals.
    Used to skip regex matches that fall inside comments or strings."""
    ranges: list[tuple[int, int]] = []
    i = 0
    n = len(source)
    while i < n:
        if i < n - 1 and source[i : i + 2] == b"//":
            start = i
            i += 2
            while i < n and source[i : i + 1] != b"\n":
                i += 1
            ranges.append((start, i))
            continue
        if i < n - 1 and source[i : i + 2] == b"/*":
            start = i
            i += 2
            while i < n - 1 and source[i : i + 2] != b"*/":
                i += 1
            i = min(i + 2, n)
            ranges.append((start, i))
            continue
        if source[i : i + 1] in (b'"', b"'"):
            quote = source[i : i + 1]
            start = i
            i += 1
            while i < n:
                if source[i : i + 1] == b"\\":
                    i += 2
                    continue
                if source[i : i + 1] == quote:
                    i += 1
                    break
                i += 1
            ranges.append((start, i))
            continue
        i += 1
    return ranges


def _position_in_ranges(pos: int, ranges: list[tuple[int, int]]) -> bool:
    """Return True if pos (byte offset) falls inside any range."""
    for start, end in ranges:
        if start <= pos < end:
            return True
    return False


def _is_array_declarator_context_c(source: bytes, match_end: int) -> bool:
    """Return True if identifier[number] at match_end is in declaration context
    (array size in declarator), not an array access. E.g. 'extern int arr[10];'
    has [10] as size, not access."""
    n = len(source)
    i = match_end
    while i < n and source[i : i + 1] in b" \t\n\r":
        i += 1
    if i < n and source[i : i + 1] == b";":
        return True
    return False


def extract_includes(code: str, file_path: str) -> list[dict]:
    """Extract #include statements from C/C++ source code."""
    includes = []
    for match in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', code):
        included_file = match.group(1)
        includes.append({
            'type': 'include',
            'file': included_file,
            'line': code[:match.start()].count('\n') + 1
        })
    return includes


def extract_imports(code: str, file_path: str) -> list[dict]:
    """Extract import statements from Python source code."""
    imports = []
    for match in re.finditer(r'(?:from\s+(\S+)\s+)?import\s+([^#\n]+)', code):
        module = match.group(1) or match.group(2).split()[0]
        module = module.strip().rstrip(';').strip()
        if module:
            imports.append({
                'type': 'import',
                'module': module,
                'line': code[:match.start()].count('\n') + 1
            })
    return imports


def extract_function_calls(code: str, symbols: list[dict]) -> list[dict]:
    """Find intra-file function calls in source code."""
    calls = []
    function_names = [s['name'] for s in symbols if s.get('kind') == 'function']
    for func_name in function_names:
        pattern = rf'\b{re.escape(func_name)}\s*\('
        for match in re.finditer(pattern, code):
            line_num = code[:match.start()].count('\n') + 1
            calls.append({
                'function': func_name,
                'line': line_num
            })
    return calls


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
                arg_children = [c for c in args.children if c.type not in ("(", ")", ",")] if args else []
                nargs = len(arg_children)
                # #18: Infer argument types for type checking
                inferred_arg_types: list[Optional[str]] = []
                for ac in arg_children:
                    t = _infer_type_from_rhs(ac)
                    if t is None and ac.type == "identifier":
                        t = None  # checker will look up from symbols
                    inferred_arg_types.append(t)
                refs.append(Reference(name=name, kind="call", line=_line_of(node, source),
                                      arg_count=nargs, arg_types=inferred_arg_types if any(t is not None for t in inferred_arg_types) else None))
        if node.type in ("call_expression", "call") and language == "c":
            fn = node.child_by_field_name("function")
            if fn and fn.type == "identifier":
                name = _source_at(fn, source).strip()
                args = node.child_by_field_name("arguments")
                arg_children = [c for c in args.children if c.type not in ("(", ")", ",")] if args else []
                nargs = len(arg_children)
                refs.append(Reference(name=name, kind="call", line=_line_of(node, source), arg_count=nargs))
                # #12: Format string detection for printf family
                _PRINTF_FAMILY = {"printf", "fprintf", "sprintf", "snprintf", "scanf", "fscanf", "sscanf"}
                if name in _PRINTF_FAMILY and arg_children:
                    fmt_arg_idx = 0
                    if name in ("fprintf", "fscanf", "sprintf", "sscanf"):
                        fmt_arg_idx = 1
                    elif name == "snprintf":
                        fmt_arg_idx = 2
                    if fmt_arg_idx < len(arg_children):
                        fmt_node = arg_children[fmt_arg_idx]
                        if fmt_node.type == "string_literal":
                            fmt_str = _source_at(fmt_node, source).strip().strip('"')
                            specs = re.findall(r'%(?!%)[diouxXeEfFgGaAcspnl*]', fmt_str)
                            num_specs = len(specs)
                            actual_fmt_args = nargs - fmt_arg_idx - 1
                            refs.append(Reference(
                                name=name, kind="format_call",
                                line=_line_of(node, source),
                                arg_count=actual_fmt_args,
                                format_specifiers=num_specs,
                                format_string=fmt_str,
                            ))
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
        # C: arr[i] = expr – detect array write for type mismatch (e.g. assigning int to char[])
        if node.type == "assignment_expression" and language == "c":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left and left.type in ("subscript_expression", "subscript") and right:
                arr_node = left.child_by_field_name("argument")
                idx_node = left.child_by_field_name("index")
                if (not arr_node or not idx_node) and len(left.children) >= 4:
                    arr_node = left.children[0]
                    idx_node = left.children[2]
                if arr_node and idx_node:
                    name = _source_at(arr_node, source).strip()
                    idx_str = _source_at(idx_node, source).strip()
                    try:
                        index_val = int(idx_str, 0)
                    except ValueError:
                        index_val = None
                    rhs_type = _infer_c_expr_type(right, source)
                    rhs_name = _source_at(right, source).strip() if right.type == "identifier" else None
                    refs.append(Reference(
                        name=name, kind="array_write", line=_line_of(node, source),
                        index_value=index_val, inferred_type=rhs_type, rhs_name=rhs_name,
                    ))

        # #14: Python import extraction
        if node.type == "import_statement" and language == "python":
            imported = []
            for c in node.children:
                if c.type == "dotted_name":
                    imported.append(_source_at(c, source).strip())
                elif c.type == "aliased_import":
                    alias_node = c.child_by_field_name("alias")
                    name_node = c.child_by_field_name("name")
                    local = alias_node if alias_node else name_node
                    if local:
                        imported.append(_source_at(local, source).strip())
            if imported:
                refs.append(Reference(
                    name="__import__", kind="import",
                    line=_line_of(node, source),
                    imported_names=imported,
                ))

        if node.type == "import_from_statement" and language == "python":
            module_node = node.child_by_field_name("module_name")
            mod_name = _source_at(module_node, source).strip() if module_node else ""
            imported = []
            for c in node.children:
                if c.type == "dotted_name" and c != module_node:
                    imported.append(_source_at(c, source).strip())
                elif c.type == "aliased_import":
                    alias_node = c.child_by_field_name("alias")
                    name_node = c.child_by_field_name("name")
                    local = alias_node if alias_node else name_node
                    if local:
                        imported.append(_source_at(local, source).strip())
                elif c.type == "identifier" and c != module_node:
                    imported.append(_source_at(c, source).strip())
            if imported:
                refs.append(Reference(
                    name="__import__", kind="import",
                    line=_line_of(node, source),
                    imported_names=imported,
                    module_name=mod_name,
                ))

        # #15: Python return statement extraction
        if node.type == "return_statement" and language == "python":
            parent = node.parent
            func_name = ""
            declared_ret = None
            while parent:
                if parent.type == "function_definition":
                    name_node = parent.child_by_field_name("name")
                    if name_node:
                        func_name = _source_at(name_node, source).strip()
                    ret_node = parent.child_by_field_name("return_type")
                    if ret_node:
                        declared_ret = _get_python_type_annotation(ret_node, source)
                    break
                parent = parent.parent
            ret_value = None
            for c in node.children:
                if c.type != "return":
                    ret_value = c
                    break
            ret_type = None
            if ret_value:
                ret_type = _infer_type_from_rhs(ret_value)
            else:
                ret_type = "None"
            if declared_ret:
                refs.append(Reference(
                    name=func_name, kind="return_value",
                    line=_line_of(node, source),
                    return_value_type=ret_type,
                    declared_return_type=declared_ret,
                    scope=func_name,
                ))

        # #17: Python annotated assignment type tracking
        if node.type == "assignment" and language == "python":
            type_node = node.child_by_field_name("type")
            if type_node:
                annotation = _get_python_type_annotation(type_node, source)
                rhs_node = node.child_by_field_name("right") or (
                    node.children[-1] if len(node.children) >= 3 else None)
                rhs_type = _infer_type_from_rhs(rhs_node) if rhs_node else None
                lhs_node = None
                for c in node.children:
                    if c.type == "identifier":
                        lhs_node = c
                        break
                if lhs_node and annotation and rhs_type:
                    refs.append(Reference(
                        name=_source_at(lhs_node, source).strip(),
                        kind="assignment",
                        line=_line_of(node, source),
                        annotation_type=annotation,
                        inferred_type=rhs_type,
                    ))

        # #19: C struct member access (field_expression: obj.member or ptr->member)
        if node.type == "field_expression" and language == "c":
            obj = node.child_by_field_name("argument")
            field_node = node.child_by_field_name("field")
            if obj and field_node:
                obj_name = _source_at(obj, source).strip()
                field_name = _source_at(field_node, source).strip()
                refs.append(Reference(
                    name=obj_name, kind="member_access",
                    line=_line_of(node, source),
                    member_name=field_name,
                ))

        for c in node.children:
            walk(c)

    walk(tree.root_node)

    # Fallback for C: scan with regex for identifier[number] (tree-sitter often misses subscript in C)
    # Skip matches inside comments/strings, skip declaration context (array size), dedup with tree-sitter refs
    if language == "c":
        import logging
        skip_ranges = _get_comment_and_string_ranges_c(source)
        # Build set of existing (name, line, index) to avoid duplicates
        existing_refs = {(r.name, r.line, r.index_value) for r in refs if r.kind == "array_access"}
        n_before = len(refs)
        for m in re.finditer(rb"([a-zA-Z_][a-zA-Z0-9_]*)\s*\[\s*(\d+)\s*\]", source):
            if _position_in_ranges(m.start(), skip_ranges):
                continue
            if _is_array_declarator_context_c(source, m.end()):
                continue
            name = m.group(1).decode("utf-8", errors="replace")
            try:
                index_val = int(m.group(2), 10)
            except ValueError:
                index_val = None
            line = source[: m.start()].count(b"\n") + 1
            if (name, line, index_val) in existing_refs:
                continue
            existing_refs.add((name, line, index_val))
            refs.append(Reference(name=name, kind="array_access", line=line, index_value=index_val))
        if len(refs) > n_before:
            logging.getLogger(__name__).info("C regex fallback added %d array_access ref(s)", len(refs) - n_before)

    return refs
