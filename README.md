# ImpactLens

> Impact analysis and selective test execution for Java codebases — with Gen-AI augmentation for dynamic code paths.

## Problem Statement

Engineers working on large Java codebases face a painful tradeoff: run the full test suite after every change and waste hours, or skip tests and risk regressions. Modern test suites in production Java projects routinely take 30+ minutes to run in full. Most of those tests have nothing to do with the specific change an engineer just made. Big tech companies (Google's TAP, Meta's Predictive Test Selection) solve this with impact analysis — mapping code changes to the minimum set of relevant tests. Small teams have no such tooling.

ImpactLens brings impact analysis to everyday projects. Given a Java repository and a code change, it identifies the ripple effect of that change through the codebase and runs only the tests that actually exercise the affected code.

## Proposed Solution

ImpactLens parses Java source files into an abstract symbol table and constructs a call graph of the entire codebase. When given a git diff, it walks the graph in reverse from the changed symbols to identify the full blast radius — every function transitively affected by the change. It then maps that blast radius to relevant JUnit tests using a combination of naming conventions, import analysis, and LLM-assisted semantic matching for edge cases. Finally, it invokes Maven/Surefire to run only those tests and reports results alongside a time-saved comparison against the full suite.

Architecture is deliberately language-agnostic at the core: a `LanguageAdapter` interface separates Java-specific parsing from the generic pipeline, so adding Python, Go, or C++ support later requires only a new adapter — not a pipeline rewrite.

## Tech Stack

- **Language:** Python 3.11 (tooling), Java 17 (target codebase)
- **Parsing:** Tree-sitter with `tree-sitter-java` grammar
- **Graph:** NetworkX for call-graph construction and traversal
- **Git:** GitPython for diff extraction
- **CLI:** Click with Rich for styled output
- **Validation:** Pydantic for data contracts
- **Test execution:** Maven Surefire (invoked via subprocess)
- **LLM augmentation:** Anthropic Claude API (planned, Day 4)
- **Web dashboard:** Streamlit (planned, Day 5)
- **Deployment:** Streamlit Community Cloud (planned, Day 6)

## Features

- Parse Java source files into a structured symbol table (classes, methods, imports, invocations)
- Build a transitive call graph of the entire codebase
- Extract changed symbols from a git diff between two commits
- Compute the blast radius of a change via reverse graph traversal
- Map impacted source symbols to JUnit test methods
- Run only selected tests via Maven Surefire
- Report time saved versus full-suite execution
- Extensible adapter architecture for adding new languages

## Architecture

The system follows a ports-and-adapters pattern. The core pipeline is language-agnostic and operates on abstract data types defined in `src/impactlens/core/models.py`. Each supported language provides an adapter conforming to the `LanguageAdapter` interface.

```
┌──────────────────────────────────────────────────────────────┐
│                         CLI / Dashboard                        │
└────────────────────────┬──────────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────────────┐
│                    Pipeline Orchestrator                       │
└──┬───────────┬─────────────┬──────────────┬──────────────┬───┘
   │           │             │              │              │
┌──▼───┐  ┌────▼────┐  ┌─────▼──────┐  ┌────▼─────┐  ┌─────▼────┐
│ Diff │  │ Lang    │  │ Call Graph │  │ Impact   │  │ Test     │
│ Ext. │  │ Adapter │  │ Builder    │  │ Analyzer │  │ Runner   │
└──────┘  └────┬────┘  └────────────┘  └──────────┘  └──────────┘
               │
     ┌─────────┼──────────┐
     │         │          │
  ┌──▼──┐  ┌──▼──┐    ┌───▼────┐
  │Java │  │Python│    │(future)│
  │Adpt │  │Adpt  │    │        │
  └─────┘  └─────┘    └────────┘
```

See [docs/architecture.md](docs/architecture.md) for the full design document.

## Setup Instructions
 Run the scripts/setup_sample-repo.sh - bash scripts/setup_sample_repo.sh

### Prerequisites

- Python 3.10 or higher
- Git 2.30+
- Java 17 JDK (for running the sample project and its tests)
- Maven 3.8+ (for running JUnit tests — can be invoked via wrapper)

### Installation

```bash
git clone https://github.com/sjr27-maker/H2H-Interrupt-Error-Impact-Lens.git
cd IMPACT LENS/impactlens

python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

### Verify installation

```bash
impactlens --version
impactlens --help
```
### Build progress
### ✅ Day 1 — Foundation _(Wed, April 16)_

- [x] 📦 Repository initialized + submitted via Google Form
- [x] 📐 Pydantic data models defined (`SourceSymbol`, `CallEdge`, `ChangedRegion`, `TestCase`, `ImpactResult`)
- [x] 🔌 `LanguageAdapter` abstract base class with 3 abstract methods
- [x] 📇 Adapter registry with self-registration pattern
- [x] ☕ Java adapter scaffolded — Tree-sitter parser wrapper in place
- [x] 💻 Click + Rich CLI scaffolded (`analyze`, `languages` commands)
- [x] ☕ Sample Maven project — 5 source classes, 5 JUnit test classes, layered dependencies
- [x] 🧪 Pytest smoke suite covering the data models
- [x] 📚 Architecture & data-contract documentation

### ✅ Day 2 — Java Parsing & Git Diff _(Thu, April 17)_

- [x] 🔀 Git diff extractor with hunk-level line-range precision via GitPython
- [x] 🌳 Full Tree-sitter Java parser — classes, methods, constructors, imports, invocations
- [x] ☕ JavaAdapter complete — symbol extraction, call resolution with import-aware name lookup, `@Test` detection
- [x] 🕸️ Call graph builder with `ancestors`, `descendants`, and file-level queries via NetworkX
- [x] 💻 CLI `analyze` command now runs real diff extraction + symbol parsing with Rich table output
- [x] 📦 Sample repo enhanced — 5-commit history with scripted setup (`scripts/setup_sample_repo.sh`)
- [x] 🧪 15+ tests covering parser, adapter, diff extractor, and full integration pipeline
```bash
# Full usage available Day 3+; Day 1 supports --help only
impactlens analyze sample_repos/java_demo --base HEAD~1 --head HEAD
```

## Demo / Screenshots

Screenshots and a 3–5 minute demo video will be added by April 23. Watch this section for updates.

## Team Members

Adithya S — Analysis Engineer — AST parsing, call graph, impact logic — [@A-github-handle](https://github.com/A-github-handle)
Sooraj R Nair — Platform Engineer — CLI, web dashboard, test runner, deployment — [@B-github-handle](https://github.com/B-github-handle)

## Deployed Link

*Deployment planned for April 21 (Day 6). Live URL will be added here.*

---

 — T John Institute of Technology — CSE Department — April 2026*