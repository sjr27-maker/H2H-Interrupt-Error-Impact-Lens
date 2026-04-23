"""
Setup for Streamlit Cloud — creates git history in sample repos using pure Python.
No bash required. Runs automatically on app startup.
"""
from __future__ import annotations

import subprocess
import os
from pathlib import Path


def _git(sample_dir: Path, *args):
    """Run a git command in the sample directory."""
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "ImpactLens Demo"
    env["GIT_AUTHOR_EMAIL"] = "demo@impactlens.dev"
    env["GIT_COMMITTER_NAME"] = "ImpactLens Demo"
    env["GIT_COMMITTER_EMAIL"] = "demo@impactlens.dev"
    
    result = subprocess.run(
        ["git"] + list(args),
        cwd=str(sample_dir),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    return result.returncode == 0


def ensure_sample_repo() -> bool:
    """Create git history in java_demo. Returns True if successful."""
    project_root = Path(__file__).parent.parent
    sample_dir = project_root / "sample_repos" / "java_demo"

    if not sample_dir.exists():
        return False

    # Already has valid git history
    if (sample_dir / ".git").exists():
        check = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(sample_dir),
            capture_output=True, text=True,
        )
        if check.returncode == 0:
            return True
        # Broken .git — remove it
        import shutil
        shutil.rmtree(sample_dir / ".git", ignore_errors=True)

    # Create git history
    _git(sample_dir, "init")
    _git(sample_dir, "checkout", "-b", "main")

    # Commit 1: Initial
    _git(sample_dir, "add", ".")
    _git(sample_dir, "commit", "-m", "Initial commit - full project with layered dependencies")

    # Commit 2: Modify PriceFormatter
    pf = sample_dir / "src" / "main" / "java" / "com" / "impactlens" / "demo" / "util" / "PriceFormatter.java"
    if pf.exists():
        content = pf.read_text(encoding="utf-8")
        new_content = content.replace(
            'return String.format("$%.2f", amount);',
            'if (amount < 0) {\n            return "-" + String.format("$%.2f", Math.abs(amount));\n        }\n        return String.format("$%.2f", amount);'
        )
        if new_content != content:
            pf.write_text(new_content, encoding="utf-8")
            _git(sample_dir, "add", "-A")
            _git(sample_dir, "commit", "-m", "Add negative amount handling to PriceFormatter.format()")

    # Commit 3: Modify DiscountCalculator
    dc = sample_dir / "src" / "main" / "java" / "com" / "impactlens" / "demo" / "pricing" / "DiscountCalculator.java"
    if dc.exists():
        content = dc.read_text(encoding="utf-8")
        new_content = content.replace(
            'return 0.0;\n    }',
            'if ("vip".equals(tier)) return subtotal * 0.30;\n        return 0.0;\n    }'
        )
        if new_content != content:
            dc.write_text(new_content, encoding="utf-8")
            _git(sample_dir, "add", "-A")
            _git(sample_dir, "commit", "-m", "Add VIP tier and guard against negative subtotals")

    # Commit 4: Add CurrencyConverter
    util_dir = sample_dir / "src" / "main" / "java" / "com" / "impactlens" / "demo" / "util"
    cc = util_dir / "CurrencyConverter.java"
    if not cc.exists():
        cc.write_text('''package com.impactlens.demo.util;

import java.util.Map;

public class CurrencyConverter {
    private static final Map<String, Double> RATES = Map.of(
        "USD", 1.0, "EUR", 0.92, "GBP", 0.79, "INR", 83.12
    );

    public double convert(double amount, String from, String to) {
        double inUsd = amount / RATES.getOrDefault(from, 1.0);
        return inUsd * RATES.getOrDefault(to, 1.0);
    }
}
''', encoding="utf-8")
        test_dir = sample_dir / "src" / "test" / "java" / "com" / "impactlens" / "demo" / "util"
        test_dir.mkdir(parents=True, exist_ok=True)
        cct = test_dir / "CurrencyConverterTest.java"
        cct.write_text('''package com.impactlens.demo.util;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class CurrencyConverterTest {
    @Test
    public void testUsdToEur() {
        CurrencyConverter c = new CurrencyConverter();
        assertEquals(92.0, c.convert(100.0, "USD", "EUR"), 0.1);
    }

    @Test
    public void testSameCurrency() {
        CurrencyConverter c = new CurrencyConverter();
        assertEquals(100.0, c.convert(100.0, "USD", "USD"), 0.001);
    }
}
''', encoding="utf-8")
        _git(sample_dir, "add", "-A")
        _git(sample_dir, "commit", "-m", "Add CurrencyConverter utility with exchange rate support")

    # Commit 5: Modify TaxCalculator
    tc = sample_dir / "src" / "main" / "java" / "com" / "impactlens" / "demo" / "pricing" / "TaxCalculator.java"
    if tc.exists():
        content = tc.read_text(encoding="utf-8")
        if "amount < 0" not in content:
            new_content = content.replace(
                'return amount * TAX_RATE;',
                'if (amount < 0 || rate < 0) return 0.0;\n        return amount * TAX_RATE;'
            ).replace(
                'return amount * 0.08;',
                'if (amount < 0) return 0.0;\n        return amount * 0.08;'
            )
            if new_content != content:
                tc.write_text(new_content, encoding="utf-8")
                _git(sample_dir, "add", "-A")
                _git(sample_dir, "commit", "-m", "Add guard to TaxCalculator and wire CurrencyConverter")

    # Verify
    check = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=str(sample_dir),
        capture_output=True, text=True,
    )
    if check.returncode == 0:
        count = len(check.stdout.strip().split("\n"))
        print(f"Sample repo ready: {count} commits")
        return True

    return False