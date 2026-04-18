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
