#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Creates the java_demo sample repository with deliberate git history.
# Each commit introduces a specific change pattern that the impact analyzer
# should detect. Run once after cloning.
# ============================================================================

SAMPLE_DIR="sample_repos/java_demo"

# If it already has a .git, we're done
if [ -d "$SAMPLE_DIR/.git" ]; then
    echo "✅ Sample repo already initialized at $SAMPLE_DIR"
    exit 0
fi

echo "🔧 Initializing sample Java repo with commit history..."

cd "$SAMPLE_DIR"
git init
git checkout -b main

# ── Commit 1: Initial project structure ──────────────────────────────────────
git add pom.xml
git add src/main/java/com/impactlens/demo/util/PriceFormatter.java
git add src/main/java/com/impactlens/demo/pricing/DiscountCalculator.java
git add src/main/java/com/impactlens/demo/pricing/TaxCalculator.java
git add src/main/java/com/impactlens/demo/service/OrderService.java
git add src/main/java/com/impactlens/demo/api/CheckoutHandler.java
git add src/test/java/com/impactlens/demo/util/PriceFormatterTest.java
git add src/test/java/com/impactlens/demo/pricing/DiscountCalculatorTest.java
git add src/test/java/com/impactlens/demo/pricing/TaxCalculatorTest.java
git add src/test/java/com/impactlens/demo/service/OrderServiceTest.java
git add src/test/java/com/impactlens/demo/api/CheckoutHandlerTest.java
git commit -m "Initial commit — full project with layered dependencies"

# ── Commit 2: Modify PriceFormatter (leaf utility) ──────────────────────────
# This tests: change to a leaf node should impact CheckoutHandler (direct caller)
# Expected blast radius: PriceFormatter → CheckoutHandler
# Expected tests: PriceFormatterTest, CheckoutHandlerTest
cat > src/main/java/com/impactlens/demo/util/PriceFormatter.java << 'JAVA'
package com.impactlens.demo.util;

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
}
JAVA
git add -A
git commit -m "Add negative amount handling to PriceFormatter.format()"

# ── Commit 3: Modify DiscountCalculator (mid-level) ─────────────────────────
# This tests: change to a mid-level node ripples through OrderService → CheckoutHandler
# Expected blast radius: DiscountCalculator → OrderService → CheckoutHandler
# Expected tests: DiscountCalculatorTest, OrderServiceTest, CheckoutHandlerTest
cat > src/main/java/com/impactlens/demo/pricing/DiscountCalculator.java << 'JAVA'
package com.impactlens.demo.pricing;

public class DiscountCalculator {
    public double calculateDiscount(double subtotal, String tier) {
        if (subtotal <= 0) return 0.0;
        if ("premium".equals(tier)) return subtotal * 0.20;
        if ("standard".equals(tier)) return subtotal * 0.10;
        if ("vip".equals(tier)) return subtotal * 0.30;
        return 0.0;
    }
}
JAVA
git add -A
git commit -m "Add VIP tier and guard against negative subtotals in DiscountCalculator"

# ── Commit 4: Add a new utility class (no callers yet) ──────────────────────
# This tests: a brand new file with no dependents → minimal blast radius
# Expected blast radius: just the new file itself
# Expected tests: just the new test
mkdir -p src/main/java/com/impactlens/demo/util
cat > src/main/java/com/impactlens/demo/util/CurrencyConverter.java << 'JAVA'
package com.impactlens.demo.util;

import java.util.Map;

public class CurrencyConverter {
    private static final Map<String, Double> RATES = Map.of(
        "USD", 1.0,
        "EUR", 0.92,
        "GBP", 0.79,
        "INR", 83.12
    );

    public double convert(double amount, String from, String to) {
        double inUsd = amount / RATES.getOrDefault(from, 1.0);
        return inUsd * RATES.getOrDefault(to, 1.0);
    }
}
JAVA

mkdir -p src/test/java/com/impactlens/demo/util
cat > src/test/java/com/impactlens/demo/util/CurrencyConverterTest.java << 'JAVA'
package com.impactlens.demo.util;

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
JAVA
git add -A
git commit -m "Add CurrencyConverter utility with exchange rate support"

# ── Commit 5: Modify TaxCalculator + wire CurrencyConverter into CheckoutHandler
# This tests: two changes in one diff, one with deep ripple, one adding a new edge
# Expected blast radius: TaxCalculator → OrderService → CheckoutHandler (existing path)
#                        + CurrencyConverter → CheckoutHandler (new edge)
# Expected tests: TaxCalculatorTest, OrderServiceTest, CheckoutHandlerTest, CurrencyConverterTest
cat > src/main/java/com/impactlens/demo/pricing/TaxCalculator.java << 'JAVA'
package com.impactlens.demo.pricing;

public class TaxCalculator {
    private static final double DEFAULT_TAX_RATE = 0.08;

    public double calculateTax(double amount) {
        return calculateTax(amount, DEFAULT_TAX_RATE);
    }

    public double calculateTax(double amount, double rate) {
        if (amount < 0 || rate < 0) return 0.0;
        return amount * rate;
    }
}
JAVA

cat > src/main/java/com/impactlens/demo/api/CheckoutHandler.java << 'JAVA'
package com.impactlens.demo.api;

import com.impactlens.demo.service.OrderService;
import com.impactlens.demo.util.PriceFormatter;
import com.impactlens.demo.util.CurrencyConverter;

public class CheckoutHandler {
    private final OrderService orderService;
    private final PriceFormatter formatter;
    private final CurrencyConverter currencyConverter;

    public CheckoutHandler() {
        this.orderService = new OrderService();
        this.formatter = new PriceFormatter();
        this.currencyConverter = new CurrencyConverter();
    }

    public String checkout(double subtotal, String tier) {
        double total = orderService.getOrderTotal(subtotal, tier);
        return "Order total: " + formatter.format(total);
    }

    public String checkoutInCurrency(double subtotal, String tier, String currency) {
        double total = orderService.getOrderTotal(subtotal, tier);
        double converted = currencyConverter.convert(total, "USD", currency);
        return "Order total: " + formatter.formatWithCurrency(converted, currency);
    }
}
JAVA
git add -A
git commit -m "Add overloaded TaxCalculator, wire CurrencyConverter into CheckoutHandler"

echo ""
echo "✅ Sample repo initialized with 5 commits"
echo ""
echo "Commit history (oldest first):"
git log --oneline --reverse
echo ""
echo "Useful diff ranges for testing:"
echo "  HEAD~4..HEAD~3  →  PriceFormatter change (leaf node)"
echo "  HEAD~3..HEAD~2  →  DiscountCalculator change (mid-level ripple)"
echo "  HEAD~2..HEAD~1  →  New file added (CurrencyConverter)"
echo "  HEAD~1..HEAD    →  TaxCalculator + CheckoutHandler multi-change"