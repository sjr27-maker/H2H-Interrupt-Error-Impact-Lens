package com.impactlens.demo.pricing;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class DiscountCalculatorTest {
    @Test
    public void testPremiumDiscount() {
        DiscountCalculator d = new DiscountCalculator();
        assertEquals(20.0, d.calculateDiscount(100.0, "premium"), 0.001);
    }

    @Test
    public void testStandardDiscount() {
        DiscountCalculator d = new DiscountCalculator();
        assertEquals(10.0, d.calculateDiscount(100.0, "standard"), 0.001);
    }

    @Test
    public void testNoDiscount() {
        DiscountCalculator d = new DiscountCalculator();
        assertEquals(0.0, d.calculateDiscount(100.0, "basic"), 0.001);
    }
}