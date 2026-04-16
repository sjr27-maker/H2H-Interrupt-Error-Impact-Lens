import os

BASE_DIR = "impactlens"

structure = [
    "README.md",
    "pyproject.toml",
    ".gitignore",
    ".python-version",

    "src/impactlens/__init__.py",
    "src/impactlens/cli.py",

    "src/impactlens/core/__init__.py",
    "src/impactlens/core/models.py",
    "src/impactlens/core/adapter.py",
    "src/impactlens/core/registry.py",
    "src/impactlens/core/pipeline.py",
    "src/impactlens/core/diff.py",

    "src/impactlens/adapters/__init__.py",
    "src/impactlens/adapters/java/__init__.py",
    "src/impactlens/adapters/java/adapter.py",
    "src/impactlens/adapters/java/parser.py",

    "src/impactlens/graph/__init__.py",
    "src/impactlens/graph/call_graph.py",

    "src/impactlens/analysis/__init__.py",
    "src/impactlens/analysis/impact.py",

    "src/impactlens/mapping/__init__.py",
    "src/impactlens/mapping/test_mapper.py",

    "src/impactlens/runner/__init__.py",
    "src/impactlens/runner/base.py",

    "src/impactlens/ai/__init__.py",
    "src/impactlens/ai/.gitkeep",

    "tests/__init__.py",
    "tests/test_models.py",

    "sample_repos/java_demo/",

    "docs/architecture.md",
    "docs/data_contract.md",

    ".github/"
]


def create_structure():
    for path in structure:
        full_path = os.path.join(BASE_DIR, path)

        # If it's a directory
        if path.endswith("/"):
            os.makedirs(full_path, exist_ok=True)
        else:
            # Create parent directories if needed
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Create empty file if it doesn't exist
            if not os.path.exists(full_path):
                with open(full_path, "w") as f:
                    pass

    print(f"Project structure created under '{BASE_DIR}/'")


if __name__ == "__main__":
    create_structure()