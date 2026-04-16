package com.impactlens.demo.service;

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
}