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
