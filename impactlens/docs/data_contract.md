# ImpactLens Data Contract

All boundaries between modules use these types. They are defined in
`src/impactlens/core/models.py` as Pydantic models for runtime validation.

## SymbolId
Unique identifier for a symbol (function, method, class). Format:
`<language>:<fully_qualified_name>`. Example: `java:com.impactlens.demo.pricing.DiscountCalculator#calculateDiscount`.

## SourceSymbol
Represents a defined symbol in source code.
| Field | Type | Description |
|-------|------|-------------|
| id | SymbolId | Unique ID |
| name | str | Short name (e.g., `calculateDiscount`) |
| qualified_name | str | Fully qualified (e.g., `com.impactlens.demo.pricing.DiscountCalculator.calculateDiscount`) |
| kind | enum | `class` \| `method` \| `function` \| `field` |
| file_path | str | Repo-relative path |
| start_line | int | 1-indexed |
| end_line | int | 1-indexed, inclusive |
| language | str | `java`, `python`, etc. |

## CallEdge
Represents a call from one symbol to another.
| Field | Type | Description |
|-------|------|-------------|
| caller | SymbolId | Symbol containing the call |
| callee | SymbolId | Symbol being called |
| call_site_line | int | Line number of the call |
| confidence | float | 0.0–1.0; static = 1.0, LLM-inferred = <1.0 |

## ChangedRegion
A contiguous range of lines that changed in one file.
| Field | Type | Description |
|-------|------|-------------|
| file_path | str | Repo-relative |
| change_type | enum | `added` \| `modified` \| `deleted` \| `renamed` |
| old_range | (int,int) \| None | Line range in base commit |
| new_range | (int,int) \| None | Line range in head commit |

## ImpactResult
Output of the impact analyzer.
| Field | Type | Description |
|-------|------|-------------|
| changed_symbols | list[SymbolId] | Directly changed |
| impacted_symbols | list[SymbolId] | Transitively impacted (includes changed) |
| impacted_files | list[str] | Union of files containing impacted symbols |
| selected_tests | list[TestCase] | Tests to run |
| reasoning | dict[SymbolId, str] | Optional per-symbol justification |

## TestCase
Represents a single test method.
| Field | Type | Description |
|-------|------|-------------|
| id | str | e.g., `com.impactlens.demo.pricing.DiscountCalculatorTest#testPremiumDiscount` |
| file_path | str | |
| language | str | |
| framework | str | `junit5`, `pytest`, etc. |

## TestResult
Output of the test runner per test.
| Field | Type | Description |
|-------|------|-------------|
| test_id | str | |
| status | enum | `passed` \| `failed` \| `skipped` \| `error` |
| duration_ms | float | |
| message | str \| None | Failure message if any |