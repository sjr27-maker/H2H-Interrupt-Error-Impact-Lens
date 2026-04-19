# Analysis Targets

This directory contains codebases that ImpactLens analyzes. These are
**input data**, not part of the ImpactLens source code.

## java_demo/
Synthetic Maven project created by our team during the build phase.
5-commit history with deliberate change patterns for testing.
Run `scripts/setup_sample_repo.sh` to initialize.

## commons_lang/ (git submodule)
Apache Commons Lang 3.14.0 — a production Java utility library used by
millions of projects. ~500 source files, ~2800 JUnit tests.
Included as a scale-validation target to demonstrate ImpactLens on
real-world code. We do not modify this code; we only analyze it.
Licensed under Apache License 2.0.