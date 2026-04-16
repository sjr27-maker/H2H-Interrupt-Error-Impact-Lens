"""
Language adapter registry. Adapters register themselves here; the pipeline
looks them up by Language enum or by file extension.
"""
from __future__ import annotations

from pathlib import Path

from impactlens.core.adapter import LanguageAdapter
from impactlens.core.models import Language


class AdapterRegistry:
    def __init__(self) -> None:
        self._by_language: dict[Language, LanguageAdapter] = {}
        self._by_extension: dict[str, LanguageAdapter] = {}

    def register(self, adapter: LanguageAdapter) -> None:
        if adapter.language in self._by_language:
            raise ValueError(f"Adapter for {adapter.language} already registered")
        self._by_language[adapter.language] = adapter
        for ext in adapter.source_extensions:
            self._by_extension[ext] = adapter

    def get(self, language: Language) -> LanguageAdapter:
        if language not in self._by_language:
            raise KeyError(f"No adapter registered for {language}")
        return self._by_language[language]

    def for_file(self, path: Path) -> LanguageAdapter | None:
        return self._by_extension.get(path.suffix)

    def all(self) -> list[LanguageAdapter]:
        return list(self._by_language.values())


# Module-level singleton. Adapters import this and call .register() at import time.
registry = AdapterRegistry()


def register_all_adapters() -> None:
    """Import all adapter modules so they register themselves.

    This is called once at CLI startup. Adding a new language = adding a line
    here plus the adapter module."""
    # noqa: F401 — imports for side effects (registration)
    from impactlens.adapters.java import adapter as _java_adapter  # noqa: F401
    # Day N+: from impactlens.adapters.python import adapter as _python_adapter