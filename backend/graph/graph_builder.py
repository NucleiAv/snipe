"""
Repository graph builder for D3.js visualization.
Creates file nodes and symbol nodes with relationships for dependency graph visualization.
"""
from __future__ import annotations
from typing import Any
from collections import defaultdict

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False
    nx = None


class RepoGraphBuilder:
    """
    Builds a D3.js-compatible graph from repository symbols.

    Node types:
    - File nodes: Represent source files
    - Symbol nodes: Represent functions, variables, arrays, etc.

    Edge types:
    - BELONGS_TO: Symbol belongs to a file
    - CALLS: Function calls another function
    - REFERENCES: Symbol references another symbol
    - DEFINES: Symbol defines another symbol
    """

    def __init__(self):
        self.nodes = []
        self.links = []
        self.node_ids = set()
        self.symbols_by_file = defaultdict(list)
        self.symbols_by_name = defaultdict(list)
        self.graph = None

        if HAS_NX:
            self.graph = nx.DiGraph()

    def build(self, symbols: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Build graph from symbol list.

        Args:
            symbols: List of symbol dictionaries with keys:
                - name: Symbol name
                - kind: Symbol type (function, variable, array, etc.)
                - type: Data type
                - file_path: Source file path
                - line: Line number
                - references: List of references (optional)

        Returns:
            Dictionary with "nodes" and "links" arrays for D3.js
        """
        self._reset()

        # Step 1: Group symbols by file
        self._group_symbols_by_file(symbols)

        # Step 2: Create file nodes
        self._create_file_nodes()

        # Step 3: Create symbol nodes
        self._create_symbol_nodes(symbols)

        # Step 4: Create BELONGS_TO edges (symbol → file)
        self._create_belongs_to_edges(symbols)

        # Step 5: Create relationship edges (CALLS, REFERENCES, DEFINES)
        self._create_relationship_edges(symbols)

        return {
            "nodes": self.nodes,
            "links": self.links
        }

    def _reset(self):
        """Reset internal state for new build."""
        self.nodes = []
        self.links = []
        self.node_ids = set()
        self.symbols_by_file = defaultdict(list)
        self.symbols_by_name = defaultdict(list)

        if HAS_NX:
            self.graph = nx.DiGraph()

    def _group_symbols_by_file(self, symbols: list[dict[str, Any]]):
        """Group symbols by their file path."""
        for symbol in symbols:
            file_path = symbol.get('file_path', '')
            if file_path:
                self.symbols_by_file[file_path].append(symbol)

                # Also index by name for reference resolution
                name = symbol.get('name', '')
                if name:
                    self.symbols_by_name[name].append(symbol)

    def _create_file_nodes(self):
        """Create file nodes with metadata."""
        for file_path, symbols in self.symbols_by_file.items():
            node_id = f"file:{file_path}"

            # Check if any symbols in this file might have errors
            # For now, hasErrors is False (could be enhanced with error detection)
            has_errors = False
            symbol_count = len(symbols)

            file_node = {
                "id": node_id,
                "label": file_path.split('/')[-1],  # Just filename for label
                "type": "file",
                "file": file_path,
                "hasErrors": has_errors,
                "symbolCount": symbol_count
            }

            self.nodes.append(file_node)
            self.node_ids.add(node_id)

            if HAS_NX and self.graph:
                self.graph.add_node(node_id, **file_node)

    def _create_symbol_nodes(self, symbols: list[dict[str, Any]]):
        """Create symbol nodes from symbol table."""
        for symbol in symbols:
            # Create unique ID: file:line:name
            file_path = symbol.get('file_path', '')
            line = symbol.get('line', 0)
            name = symbol.get('name', '')

            node_id = f"{file_path}:{line}:{name}"

            # Skip duplicates
            if node_id in self.node_ids:
                continue

            kind = symbol.get('kind', 'unknown')
            symbol_type = symbol.get('type')

            symbol_node = {
                "id": node_id,
                "label": name,
                "type": kind,  # function, variable, array, etc.
                "file": file_path,
                "line": line
            }

            # Add optional type information
            if symbol_type:
                symbol_node["dataType"] = symbol_type

            # Add array size if applicable
            if kind == "array" and symbol.get('array_size'):
                symbol_node["arraySize"] = symbol.get('array_size')

            # Add parameters for functions
            if kind == "function" and symbol.get('params'):
                symbol_node["params"] = symbol.get('params')

            self.nodes.append(symbol_node)
            self.node_ids.add(node_id)

            if HAS_NX and self.graph:
                self.graph.add_node(node_id, **symbol_node)

    def _create_belongs_to_edges(self, symbols: list[dict[str, Any]]):
        """Create BELONGS_TO edges from symbols to their files."""
        for symbol in symbols:
            file_path = symbol.get('file_path', '')
            line = symbol.get('line', 0)
            name = symbol.get('name', '')

            symbol_id = f"{file_path}:{line}:{name}"
            file_id = f"file:{file_path}"

            # Only create edge if both nodes exist
            if symbol_id in self.node_ids and file_id in self.node_ids:
                link = {
                    "source": symbol_id,
                    "target": file_id,
                    "relationship": "BELONGS_TO"
                }

                self.links.append(link)

                if HAS_NX and self.graph:
                    self.graph.add_edge(symbol_id, file_id, relationship="BELONGS_TO")

    def _create_relationship_edges(self, symbols: list[dict[str, Any]]):
        """
        Create CALLS, REFERENCES, and DEFINES edges based on symbol references.

        This analyzes the references field and infers relationships.
        For MVP, we use heuristics:
        - If a function references another function → CALLS
        - If a variable references another symbol → REFERENCES
        - If a symbol is defined in terms of another → DEFINES
        """
        for symbol in symbols:
            file_path = symbol.get('file_path', '')
            line = symbol.get('line', 0)
            name = symbol.get('name', '')
            kind = symbol.get('kind', '')

            source_id = f"{file_path}:{line}:{name}"

            if source_id not in self.node_ids:
                continue

            # Process references if available
            references = symbol.get('references', [])

            # If references is a list of reference objects
            for ref in references:
                if isinstance(ref, dict):
                    ref_name = ref.get('name', '')
                    ref_type = ref.get('type', 'REFERENCES')

                    # Find target symbol by name
                    target_symbols = self.symbols_by_name.get(ref_name, [])

                    for target in target_symbols:
                        target_file = target.get('file_path', '')
                        target_line = target.get('line', 0)
                        target_name = target.get('name', '')
                        target_id = f"{target_file}:{target_line}:{target_name}"

                        # Don't create self-referencing edges
                        if target_id == source_id:
                            continue

                        if target_id in self.node_ids:
                            # Determine relationship type
                            relationship = self._determine_relationship(
                                symbol, target, ref_type
                            )

                            link = {
                                "source": source_id,
                                "target": target_id,
                                "relationship": relationship
                            }

                            self.links.append(link)

                            if HAS_NX and self.graph:
                                self.graph.add_edge(
                                    source_id, target_id,
                                    relationship=relationship
                                )

            # Fallback: Create cross-file REFERENCES for symbols with same name
            self._create_cross_file_references(symbol)

    def _determine_relationship(
        self,
        source: dict[str, Any],
        target: dict[str, Any],
        ref_type: str = None
    ) -> str:
        """
        Determine the relationship type between source and target symbols.

        Heuristics:
        - function → function = CALLS
        - variable/array → any = REFERENCES
        - If ref_type is provided, use it
        """
        if ref_type and ref_type in ['CALLS', 'REFERENCES', 'DEFINES']:
            return ref_type

        source_kind = source.get('kind', '')
        target_kind = target.get('kind', '')

        # Function calling function
        if source_kind == 'function' and target_kind == 'function':
            return 'CALLS'

        # Variable or array referencing something
        if source_kind in ['variable', 'array']:
            return 'REFERENCES'

        # Default
        return 'REFERENCES'

    def _create_cross_file_references(self, symbol: dict[str, Any]):
        """
        Create REFERENCES edges between symbols with the same name in different files.
        This helps show potential function calls or variable references across files.
        """
        name = symbol.get('name', '')
        file_path = symbol.get('file_path', '')
        line = symbol.get('line', 0)

        source_id = f"{file_path}:{line}:{name}"

        # Find all symbols with same name
        same_name_symbols = self.symbols_by_name.get(name, [])

        for target in same_name_symbols:
            target_file = target.get('file_path', '')
            target_line = target.get('line', 0)

            # Skip if same file or same symbol
            if target_file == file_path:
                if target_line == line:
                    continue

            target_id = f"{target_file}:{target_line}:{name}"

            if target_id not in self.node_ids:
                continue

            # Check if this edge already exists
            edge_exists = any(
                link['source'] == source_id and
                link['target'] == target_id
                for link in self.links
            )

            if not edge_exists:
                # Determine relationship based on symbol types
                relationship = self._determine_relationship(symbol, target)

                link = {
                    "source": source_id,
                    "target": target_id,
                    "relationship": relationship
                }

                self.links.append(link)

                if HAS_NX and self.graph:
                    self.graph.add_edge(
                        source_id, target_id,
                        relationship=relationship
                    )

    def get_networkx_graph(self) -> "Any | None":
        """
        Get the NetworkX graph object.

        Returns:
            NetworkX DiGraph or None if NetworkX is not available
        """
        return self.graph if HAS_NX else None

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the graph.

        Returns:
            Dictionary with node counts, edge counts, and other metrics
        """
        file_nodes = [n for n in self.nodes if n.get('type') == 'file']
        symbol_nodes = [n for n in self.nodes if n.get('type') != 'file']

        relationship_counts = defaultdict(int)
        for link in self.links:
            rel = link.get('relationship', 'UNKNOWN')
            relationship_counts[rel] += 1

        stats = {
            "total_nodes": len(self.nodes),
            "file_nodes": len(file_nodes),
            "symbol_nodes": len(symbol_nodes),
            "total_edges": len(self.links),
            "relationships": dict(relationship_counts)
        }

        # Add NetworkX metrics if available
        if HAS_NX and self.graph:
            try:
                stats["is_directed_acyclic"] = nx.is_directed_acyclic_graph(self.graph)
                stats["number_of_weakly_connected_components"] = nx.number_weakly_connected_components(self.graph)
            except:
                pass

        return stats


def build_d3_graph(symbols: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Convenience function to build D3.js graph from symbols.

    Args:
        symbols: List of symbol dictionaries

    Returns:
        Dictionary with "nodes" and "links" for D3.js visualization
    """
    builder = RepoGraphBuilder()
    return builder.build(symbols)
