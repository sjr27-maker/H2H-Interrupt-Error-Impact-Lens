# ImpactLens Architecture

## Design Principles

1. **Language-agnostic core.** The pipeline operates on abstract types
   (`SourceSymbol`, `CallEdge`, `ChangedRegion`). No core module imports
   anything language-specific.
2. **Adapters isolate language concerns.** A `LanguageAdapter` subclass is
   responsible for turning source files into the abstract types. Java today,
   Python tomorrow, without changing the core.
3. **Extensibility has a fixed cost.** Adding a new language requires only:
   a new adapter module, one line in `register_all_adapters()`, and optional
   test-framework plumbing in the runner layer.

## Module Map

| Module | Purpose | Depends on |
|--------|---------|------------|
| `core/models.py` | Abstract data types (Pydantic) | — |
| `core/adapter.py` | `LanguageAdapter` ABC | `core/models` |
| `core/registry.py` | Adapter registry singleton | `core/adapter` |
| `core/diff.py` | Git diff → `ChangedRegion[]` | `core/models` |
| `core/pipeline.py` | Orchestrator | all of the above |
| `adapters/java/adapter.py` | Java implementation of `LanguageAdapter` | `core`, `tree_sitter_java` |
| `adapters/java/parser.py` | Tree-sitter wrapper | `tree_sitter_java` |
| `graph/call_graph.py` | NetworkX graph ops | `core/models` |
| `analysis/impact.py` | Reverse reachability | `graph/call_graph` |
| `mapping/test_mapper.py` | Impacted symbols → tests | `core/models` |
| `runner/base.py` | Test runner ABC | `core/models` |
| `ai/` | LLM augmentation (Day 4+) | `core/models` |
| `cli.py` | CLI entry point | all |

## Extending to Python (Future Work)

1. Create `src/impactlens/adapters/python/adapter.py` subclassing `LanguageAdapter`.
2. Use Python's built-in `ast` module inside the adapter; no tree-sitter needed.
3. Set `source_extensions = (".py",)` and test patterns (`**/test_*.py`, `**/*_test.py`).
4. Implement `parse_file`, `extract_calls`, `extract_tests` returning the
   same abstract types.
5. Add the import to `register_all_adapters()`.
6. Add a `PytestRunner(TestRunner)` in `runner/`.

The impact analyzer, call graph, and CLI do not change.

## Data Flow (Day 3+)

```
git refs
   │
   ▼  core/diff.py
ChangedRegion[]
   │
   ▼  adapter.symbols_in_range()
changed SymbolIds
   │
   ▼  graph/call_graph.CallGraph (built from adapter.parse_file + extract_calls)
CallGraph
   │
   ▼  analysis/impact.compute_impact()
ImpactResult { impacted_symbols, impacted_files }
   │
   ▼  mapping/test_mapper.map_tests()  + adapter.extract_tests()
selected TestCase[]
   │
   ▼  runner.run()
TestResult[]
```