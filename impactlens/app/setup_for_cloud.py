"""
Cloud setup — creates sample repos with git history using pure Python.
No bash, no external scripts. Works on Streamlit Cloud.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def _git(cwd: Path, *args) -> bool:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "ImpactLens"
    env["GIT_AUTHOR_EMAIL"] = "demo@impactlens.dev"
    env["GIT_COMMITTER_NAME"] = "ImpactLens"
    env["GIT_COMMITTER_EMAIL"] = "demo@impactlens.dev"
    try:
        r = subprocess.run(["git"] + list(args), cwd=str(cwd),
                           capture_output=True, text=True, env=env, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def ensure_sample_repo() -> bool:
    """Create java_demo with 5-commit history if it doesn't exist."""
    base = PROJECT_ROOT / "sample_repos" / "java_demo"
    src = base / "src" / "main" / "java" / "com" / "impactlens" / "demo"
    tst = base / "src" / "test" / "java" / "com" / "impactlens" / "demo"

    # Already good
    if (base / ".git").exists():
        r = subprocess.run(["git", "log", "--oneline"], cwd=str(base),
                           capture_output=True, text=True)
        if r.returncode == 0 and len(r.stdout.strip().split("\n")) >= 3:
            return True
        shutil.rmtree(base / ".git", ignore_errors=True)

    # Create all source files
    _write(base / "pom.xml", """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.impactlens.demo</groupId>
    <artifactId>java-demo</artifactId>
    <version>1.0.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>5.10.1</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>""")

    _write(src / "util" / "PriceFormatter.java", """package com.impactlens.demo.util;

public class PriceFormatter {
    public String format(double amount) {
        return String.format("$%.2f", amount);
    }

    public String formatWithCurrency(double amount, String currency) {
        return String.format("%s %.2f", currency, amount);
    }
}""")

    _write(src / "pricing" / "DiscountCalculator.java", """package com.impactlens.demo.pricing;

public class DiscountCalculator {
    public double calculateDiscount(double subtotal, String tier) {
        if ("premium".equals(tier)) return subtotal * 0.20;
        if ("standard".equals(tier)) return subtotal * 0.10;
        return 0.0;
    }
}""")

    _write(src / "pricing" / "TaxCalculator.java", """package com.impactlens.demo.pricing;

public class TaxCalculator {
    private static final double TAX_RATE = 0.08;

    public double calculateTax(double amount) {
        return amount * TAX_RATE;
    }
}""")

    _write(src / "service" / "OrderService.java", """package com.impactlens.demo.service;

import com.impactlens.demo.pricing.DiscountCalculator;
import com.impactlens.demo.pricing.TaxCalculator;

public class OrderService {
    private final DiscountCalculator discountCalculator;
    private final TaxCalculator taxCalculator;

    public OrderService() {
        this.discountCalculator = new DiscountCalculator();
        this.taxCalculator = new TaxCalculator();
    }

    public double getOrderTotal(double subtotal, String tier) {
        double discount = discountCalculator.calculateDiscount(subtotal, tier);
        double afterDiscount = subtotal - discount;
        double tax = taxCalculator.calculateTax(afterDiscount);
        return afterDiscount + tax;
    }
}""")

    _write(src / "api" / "CheckoutHandler.java", """package com.impactlens.demo.api;

import com.impactlens.demo.service.OrderService;
import com.impactlens.demo.util.PriceFormatter;

public class CheckoutHandler {
    private final OrderService orderService;
    private final PriceFormatter formatter;

    public CheckoutHandler() {
        this.orderService = new OrderService();
        this.formatter = new PriceFormatter();
    }

    public String checkout(double subtotal, String tier) {
        double total = orderService.getOrderTotal(subtotal, tier);
        return "Order total: " + formatter.format(total);
    }
}""")

    # Tests
    _write(tst / "util" / "PriceFormatterTest.java", """package com.impactlens.demo.util;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class PriceFormatterTest {
    @Test public void testFormatBasic() {
        assertEquals("$10.50", new PriceFormatter().format(10.5));
    }
    @Test public void testFormatWithCurrency() {
        assertEquals("EUR 10.50", new PriceFormatter().formatWithCurrency(10.5, "EUR"));
    }
}""")

    _write(tst / "pricing" / "DiscountCalculatorTest.java", """package com.impactlens.demo.pricing;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class DiscountCalculatorTest {
    @Test public void testPremiumDiscount() {
        assertEquals(20.0, new DiscountCalculator().calculateDiscount(100.0, "premium"), 0.001);
    }
    @Test public void testStandardDiscount() {
        assertEquals(10.0, new DiscountCalculator().calculateDiscount(100.0, "standard"), 0.001);
    }
    @Test public void testNoDiscount() {
        assertEquals(0.0, new DiscountCalculator().calculateDiscount(100.0, "basic"), 0.001);
    }
}""")

    _write(tst / "pricing" / "TaxCalculatorTest.java", """package com.impactlens.demo.pricing;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class TaxCalculatorTest {
    @Test public void testTaxCalculation() {
        assertEquals(8.0, new TaxCalculator().calculateTax(100.0), 0.001);
    }
}""")

    _write(tst / "service" / "OrderServiceTest.java", """package com.impactlens.demo.service;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class OrderServiceTest {
    @Test public void testPremiumOrderTotal() {
        assertEquals(86.40, new OrderService().getOrderTotal(100.0, "premium"), 0.001);
    }
    @Test public void testStandardOrderTotal() {
        assertEquals(97.20, new OrderService().getOrderTotal(100.0, "standard"), 0.001);
    }
}""")

    _write(tst / "api" / "CheckoutHandlerTest.java", """package com.impactlens.demo.api;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class CheckoutHandlerTest {
    @Test public void testCheckoutPremium() {
        assertTrue(new CheckoutHandler().checkout(100.0, "premium").contains("86.40"));
    }
}""")

    # Git history
    _git(base, "init")
    _git(base, "checkout", "-b", "main")
    _git(base, "add", ".")
    _git(base, "commit", "-m", "Initial commit - full project")

    # Commit 2: PriceFormatter
    pf = src / "util" / "PriceFormatter.java"
    pf.write_text("""package com.impactlens.demo.util;

public class PriceFormatter {
    public String format(double amount) {
        if (amount < 0) {
            return "-" + String.format("$%.2f", Math.abs(amount));
        }
        return String.format("$%.2f", amount);
    }

    public String formatWithCurrency(double amount, String currency) {
        return String.format("%s %.2f", currency, amount);
    }
}""", encoding="utf-8")
    _git(base, "add", "-A")
    _git(base, "commit", "-m", "Add negative amount handling to PriceFormatter")

    # Commit 3: DiscountCalculator
    dc = src / "pricing" / "DiscountCalculator.java"
    dc.write_text("""package com.impactlens.demo.pricing;

public class DiscountCalculator {
    public double calculateDiscount(double subtotal, String tier) {
        if (subtotal <= 0) return 0.0;
        if ("premium".equals(tier)) return subtotal * 0.20;
        if ("standard".equals(tier)) return subtotal * 0.10;
        if ("vip".equals(tier)) return subtotal * 0.30;
        return 0.0;
    }
}""", encoding="utf-8")
    _git(base, "add", "-A")
    _git(base, "commit", "-m", "Add VIP tier to DiscountCalculator")

    # Commit 4: CurrencyConverter
    _write(src / "util" / "CurrencyConverter.java", """package com.impactlens.demo.util;

import java.util.Map;

public class CurrencyConverter {
    private static final Map<String, Double> RATES = Map.of(
        "USD", 1.0, "EUR", 0.92, "GBP", 0.79, "INR", 83.12
    );

    public double convert(double amount, String from, String to) {
        double inUsd = amount / RATES.getOrDefault(from, 1.0);
        return inUsd * RATES.getOrDefault(to, 1.0);
    }
}""")
    _write(tst / "util" / "CurrencyConverterTest.java", """package com.impactlens.demo.util;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class CurrencyConverterTest {
    @Test public void testUsdToEur() {
        assertEquals(92.0, new CurrencyConverter().convert(100.0, "USD", "EUR"), 0.1);
    }
    @Test public void testSameCurrency() {
        assertEquals(100.0, new CurrencyConverter().convert(100.0, "USD", "USD"), 0.001);
    }
}""")
    _git(base, "add", "-A")
    _git(base, "commit", "-m", "Add CurrencyConverter utility")

    # Commit 5: TaxCalculator guard
    tc = src / "pricing" / "TaxCalculator.java"
    tc.write_text("""package com.impactlens.demo.pricing;

public class TaxCalculator {
    private static final double TAX_RATE = 0.08;

    public double calculateTax(double amount) {
        if (amount < 0) return 0.0;
        return amount * TAX_RATE;
    }
}""", encoding="utf-8")
    _git(base, "add", "-A")
    _git(base, "commit", "-m", "Add negative guard to TaxCalculator")

    # Verify
    r = subprocess.run(["git", "log", "--oneline"], cwd=str(base),
                       capture_output=True, text=True)
    if r.returncode == 0:
        print(f"java_demo ready: {len(r.stdout.strip().split(chr(10)))} commits")
        return True
    return False