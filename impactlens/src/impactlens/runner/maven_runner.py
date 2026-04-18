"""
Maven Surefire test runner.

Invokes `mvn test` with -Dtest=... to run only selected JUnit tests.
Parses Surefire XML reports for structured results.
Also supports running the full suite for baseline comparison.
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from impactlens.core.models import TestCase, TestResult, TestStatus
from impactlens.runner.base import TestRunner

log = logging.getLogger(__name__)


def _parse_surefire_reports(reports_dir: Path) -> list[TestResult]:
    """
    Parse Surefire XML reports (TEST-*.xml) into TestResult instances.

    Surefire writes one XML file per test class. Each <testcase> element
    contains name, classname, time, and optionally <failure> or <error>.
    """
    results: list[TestResult] = []

    if not reports_dir.exists():
        log.warning("Surefire reports directory not found: %s", reports_dir)
        return results

    for xml_file in sorted(reports_dir.glob("TEST-*.xml")):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            for testcase in root.findall("testcase"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                time_sec = float(testcase.get("time", "0"))

                test_id = f"{classname}#{name}"

                # Determine status
                failure = testcase.find("failure")
                error = testcase.find("error")
                skipped = testcase.find("skipped")

                if skipped is not None:
                    status = TestStatus.SKIPPED
                    message = skipped.get("message")
                elif failure is not None:
                    status = TestStatus.FAILED
                    message = failure.get("message", "")
                    detail = failure.text or ""
                    if detail:
                        message = f"{message}\n{detail[:500]}"
                elif error is not None:
                    status = TestStatus.ERROR
                    message = error.get("message", "")
                else:
                    status = TestStatus.PASSED
                    message = None

                results.append(TestResult(
                    test_id=test_id,
                    status=status,
                    duration_ms=time_sec * 1000,
                    message=message,
                ))

        except ET.ParseError as e:
            log.warning("Failed to parse Surefire report %s: %s", xml_file.name, e)

    return results


def _clean_surefire_reports(repo_path: Path) -> None:
    """Remove old Surefire reports to avoid mixing results."""
    reports_dir = repo_path / "target" / "surefire-reports"
    if reports_dir.exists():
        for f in reports_dir.glob("TEST-*.xml"):
            f.unlink()


class MavenSurefireRunner(TestRunner):
    """Runs JUnit tests via Maven Surefire plugin."""

    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout

    def _find_mvn(self) -> str:
        """Find the Maven executable. Supports mvnw wrapper."""
        return "mvn"

    def run(
        self,
        tests: list[TestCase],
        repo_path: Path,
    ) -> list[TestResult]:
        """
        Run selected tests via Maven Surefire.

        Uses -Dtest=ClassName#methodName,... to select specific tests.
        Parses Surefire XML reports for structured output.
        """
        if not tests:
            log.warning("No tests to run.")
            return []

        # Clean old reports
        _clean_surefire_reports(repo_path)

        # Build the -Dtest= parameter
        # Format: ClassName#method1+method2,OtherClass#method3
        # Group tests by class
        class_methods: dict[str, list[str]] = {}
        for t in tests:
            # t.id is like "com.example.FooTest#testMethod"
            if "#" in t.id:
                class_part, method_part = t.id.rsplit("#", 1)
                class_short = class_part.rsplit(".", 1)[-1]
                class_methods.setdefault(class_short, []).append(method_part)
            else:
                # No method specified — run entire class
                class_short = t.id.rsplit(".", 1)[-1]
                class_methods.setdefault(class_short, [])

        # Build test selector string
        test_selectors: list[str] = []
        for cls, methods in class_methods.items():
            if methods:
                test_selectors.append(f"{cls}#{'+'.join(methods)}")
            else:
                test_selectors.append(cls)

        test_param = ",".join(test_selectors)

        mvn = self._find_mvn()
        cmd = [
            mvn, "test",
            f"-Dtest={test_param}",
            "-Dsurefire.failIfNoSpecifiedTests=false",
            "-Dmaven.test.failure.ignore=true",  # Don't fail build on test failures
            "-q",  # Quiet mode — less Maven output noise
        ]

        log.info("Running: %s", " ".join(cmd))
        log.info("  in: %s", repo_path)
        log.info("  selecting: %s", test_param)

        start_time = time.time()

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            elapsed = time.time() - start_time

            if proc.returncode not in (0, 1):
                # 0 = all passed, 1 = some failed, other = build error
                log.error("Maven exited with code %d", proc.returncode)
                log.error("STDOUT: %s", proc.stdout[-2000:] if proc.stdout else "(empty)")
                log.error("STDERR: %s", proc.stderr[-2000:] if proc.stderr else "(empty)")

            log.info("Maven completed in %.1f seconds (exit code %d)", elapsed, proc.returncode)

        except subprocess.TimeoutExpired:
            log.error("Maven timed out after %d seconds", self.timeout)
            return [
                TestResult(test_id=t.id, status=TestStatus.ERROR,
                           duration_ms=self.timeout * 1000,
                           message=f"Timed out after {self.timeout}s")
                for t in tests
            ]
        except FileNotFoundError:
            log.error("Maven not found. Ensure 'mvn' is on PATH.")
            return [
                TestResult(test_id=t.id, status=TestStatus.ERROR,
                           duration_ms=0, message="Maven (mvn) not found on PATH")
                for t in tests
            ]

        # Parse results
        reports_dir = repo_path / "target" / "surefire-reports"
        results = _parse_surefire_reports(reports_dir)

        if not results and proc.returncode == 0:
            # Maven succeeded but no reports — tests may have been compiled but not run
            log.warning("No Surefire reports found. Tests may not have executed.")

        return results

    def run_full_suite(self, repo_path: Path) -> tuple[list[TestResult], float]:
        """
        Run the entire test suite for baseline comparison.

        Returns (results, elapsed_seconds).
        """
        _clean_surefire_reports(repo_path)

        mvn = self._find_mvn()
        cmd = [
            mvn, "test",
            "-Dmaven.test.failure.ignore=true",
            "-q",
        ]

        log.info("Running full test suite for baseline...")

        start_time = time.time()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=self.timeout * 2,  # Give full suite more time
            )
            elapsed = time.time() - start_time
        except subprocess.TimeoutExpired:
            elapsed = self.timeout * 2
            return [], elapsed
        except FileNotFoundError:
            return [], 0.0

        reports_dir = repo_path / "target" / "surefire-reports"
        results = _parse_surefire_reports(reports_dir)

        log.info("Full suite: %d tests in %.1fs", len(results), elapsed)
        return results, elapsed