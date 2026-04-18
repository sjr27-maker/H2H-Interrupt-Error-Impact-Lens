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
