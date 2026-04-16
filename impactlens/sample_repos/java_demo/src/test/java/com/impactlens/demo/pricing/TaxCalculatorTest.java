package com.impactlens.demo.pricing;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class TaxCalculatorTest {
    @Test
    public void testTaxCalculation() {
        TaxCalculator t = new TaxCalculator();
        assertEquals(8.0, t.calculateTax(100.0), 0.001);
    }
}