"""
Setup script for Streamlit Cloud deployment.
Creates git history in sample repos that were deployed as flat files.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def ensure_sample_repo():
    """Create git history in java_demo if it doesn't have any."""
    project_root = Path(__file__).parent.parent
    sample_dir = project_root / "sample_repos" / "java_demo"

    if not sample_dir.exists():
        return False

    if (sample_dir / ".git").exists():
        # Check if it actually has commits
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(sample_dir),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass

    # Try running the setup script
    setup_script = project_root / "scripts" / "setup_sample_repo.sh"
    if setup_script.exists():
        try:
            subprocess.run(
                ["bash", str(setup_script)],
                cwd=str(project_root),
                capture_output=True,
                timeout=30,
            )
            return (sample_dir / ".git").exists()
        except Exception:
            pass

    # Manual fallback — create commits directly with Python
    try:
        _create_history_manually(sample_dir)
        return True
    except Exception as e:
        print(f"Manual git setup failed: {e}")
        return False


def _create_history_manually(sample_dir: Path):
    """Create git history using subprocess calls."""
    import os

    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Demo"
    env["GIT_AUTHOR_EMAIL"] = "demo@demo.com"
    env["GIT_COMMITTER_NAME"] = "Demo"
    env["GIT_COMMITTER_EMAIL"] = "demo@demo.com"

    def git(*args):
        subprocess.run(
            ["git"] + list(args),
            cwd=str(sample_dir),
            capture_output=True,
            env=env,
            timeout=10,
        )

    # Remove old .git if broken
    import shutil
    git_dir = sample_dir / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir)

    git("init")
    git("checkout", "-b", "main")

    # Commit 1: everything
    git("add", ".")
    git("commit", "-m", "Initial commit — full project with layered dependencies")

    # Read and modify PriceFormatter for commit 2
    pf = sample_dir / "src" / "main" / "java" / "com" / "impactlens" / "demo" / "util" / "PriceFormatter.java"
    if pf.exists():
        content = pf.read_text()
        modified = content.replace(
            'return String.format("$%.2f", amount);',
            'if (amount < 0) {\n'
            '            return "-" + String.format("$%.2f", Math.abs(amount));\n'
            '        }\n'
            '        return String.format("$%.2f", amount);'
        )
        pf.write_text(modified)
        git("add", "-A")
        git("commit", "-m", "Add negative amount handling to PriceFormatter.format()")

    # Modify DiscountCalculator for commit 3
    dc = sample_dir / "src" / "main" / "java" / "com" / "impactlens" / "demo" / "pricing" / "DiscountCalculator.java"
    if dc.exists():
        content = dc.read_text()
        modified = content.replace(
            'return 0.0;\n    }',
            'if ("vip".equals(tier)) return subtotal * 0.30;\n        return 0.0;\n    }'
        )
        dc.write_text(modified)
        git("add", "-A")
        git("commit", "-m", "Add VIP tier to DiscountCalculator")

    # Add CurrencyConverter for commit 4
    util_dir = sample_dir / "src" / "main" / "java" / "com" / "impactlens" / "demo" / "util"
    cc = util_dir / "CurrencyConverter.java"
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
''')

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
''')
    git("add", "-A")
    git("commit", "-m", "Add CurrencyConverter utility")

    # Commit 5: Modify TaxCalculator
    tc = sample_dir / "src" / "main" / "java" / "com" / "impactlens" / "demo" / "pricing" / "TaxCalculator.java"
    if tc.exists():
        content = tc.read_text()
        modified = content.replace(
            'return amount * TAX_RATE;',
            'if (amount < 0) return 0.0;\n        return amount * TAX_RATE;'
        )
        tc.write_text(modified)
        git("add", "-A")
        git("commit", "-m", "Add guard to TaxCalculator")