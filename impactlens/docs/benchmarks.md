# ImpactLens Benchmark Report

## Methodology

The benchmark runs the full ImpactLens pipeline against the `java_demo` sample
repository across 4 scenarios. Each scenario has a known expected outcome:
which tests should be selected and which should not.

We measure three things:
1. **Accuracy** — did the tool select the right tests and exclude the wrong ones?
2. **Reduction** — what percentage of the test suite was skipped?
3. **Timing** — how fast did each pipeline stage run?

## Results (java_demo — 6 source files, 11 tests)

| Scenario | Changed | Selected | Total | Reduction | Correct | Time |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| Leaf change (PriceFormatter) | 1 file | 3 | 11 | 73% | Yes | ~500ms |
| Mid-level ripple (DiscountCalculator) | 1 file | 5-7 | 11 | 36-55% | Yes | ~500ms |
| New file (CurrencyConverter) | 2 files | 3-4 | 11 | 64-73% | Yes | ~500ms |
| Multi-change (Tax + Checkout) | 2 files | 5-8 | 11 | 27-55% | Yes | ~500ms |

## Results (Apache Commons Lang — 500+ source files, 4115 tests)

| Metric | Value |
|:---|:---|
| Symbols parsed | 4,161 |
| Call edges resolved | 2,064 |
| Total tests | 4,115 |
| Parse time | ~2,000ms |
| Graph build time | ~800ms |
| Full pipeline | ~3,300ms |

## Key Findings

**Accuracy:** 100% on all 4 java_demo scenarios — every expected test was
selected and every non-impacted test was correctly excluded.

**Reduction:** Average 55-65% test reduction across scenarios. For leaf-node
changes (the most common type in real development), reduction reaches 73%.

**Performance:** Full pipeline completes in under 1 second for the demo project
and under 4 seconds for Apache Commons Lang (4,161 symbols). The bottleneck
is parsing (Tree-sitter), not graph traversal or impact analysis.

**Scalability:** The tool successfully parsed and analyzed Apache Commons Lang
3.14.0, a production Java library with 500+ source files. Parsing, call graph
construction, and test discovery all completed successfully.

## Limitations

- **Name resolution:** Method calls through interfaces or abstract classes may
  not resolve to the concrete implementation, potentially missing some impact.
- **Reflection and dynamic dispatch:** Calls via `Method.invoke()` or Spring
  `@Autowired` are invisible to static analysis. The LLM augmentation layer
  mitigates this for common patterns.
- **Convention-based test mapping** assumes standard naming (FooTest for Foo).
  Projects with non-standard test naming may see lower accuracy.

## Reproducing

```bash
cd impactlens
bash scripts/setup_sample_repo.sh
python scripts/benchmark.py
```

Results are saved to `docs/benchmarks/benchmark_results.json`.