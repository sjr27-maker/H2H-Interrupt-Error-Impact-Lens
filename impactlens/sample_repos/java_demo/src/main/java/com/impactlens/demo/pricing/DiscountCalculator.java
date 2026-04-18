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
