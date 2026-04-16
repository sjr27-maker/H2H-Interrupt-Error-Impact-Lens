package com.impactlens.demo.pricing;

public class TaxCalculator {
    private static final double TAX_RATE = 0.08;

    public double calculateTax(double amount) {
        return amount * TAX_RATE;
    }
}