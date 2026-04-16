package com.impactlens.demo.pricing;

public class DiscountCalculator {
    public double calculateDiscount(double subtotal, String tier) {
        if ("premium".equals(tier)) return subtotal * 0.20;
        if ("standard".equals(tier)) return subtotal * 0.10;
        return 0.0;
    }
}