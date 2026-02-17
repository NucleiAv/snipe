"""Debug: check main.c buffer symbols."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from parser.buffer_parser import parse_unsaved_buffer
from parser.repo_parser import build_repo_symbol_table
from analyzer.type_checker import check_type_mismatch

main_c = """
#include <stdio.h>
extern int arr[10];
extern float balance;
extern int add(int a, int b);
extern void process(int count);

int main(void) {
    process(5);
    int x = arr[9];
    printf("%d\\n", x);
    return add(1, 2);
}
"""

syms, refs = parse_unsaved_buffer(main_c, "demo_repo/main.c", "c")
print("Buffer symbols (main.c):")
for s in syms:
    print(f"  {s.name}: type={s.type}, is_extern={getattr(s, 'is_extern', '?')}")

# Build repo - use temp dir with core.c having char arr
import tempfile
with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    (tmp_path / "core.c").write_text("char arr[10];\nvoid process(int c) { for (int i=0;i<c;i++) arr[i]=i; }\n")
    (tmp_path / "main.c").write_text(main_c)
    repo = build_repo_symbol_table(str(tmp_path), output_json_path=None)

repo_dicts = [s if isinstance(s, dict) else s.to_dict() for s in repo]

# Get arr from core.c
arr_from_core = [s for s in repo_dicts if s.get("name") == "arr" and "core" in s.get("file_path", "")]
print("\nRepo arr from core.c:", arr_from_core)

diag = check_type_mismatch(refs, syms, repo_dicts, "demo_repo/main.c")
print("\nDiagnostics for main.c:", len(diag))
for d in diag:
    print(f"  {d.code}: {d.message}")
