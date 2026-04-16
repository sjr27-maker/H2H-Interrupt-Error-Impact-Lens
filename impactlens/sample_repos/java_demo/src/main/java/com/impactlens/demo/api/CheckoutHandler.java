package com.impactlens.demo.api;

import com.impactlens.demo.service.OrderService;
import com.impactlens.demo.util.PriceFormatter;

public class CheckoutHandler {
    private final OrderService orderService;
    private final PriceFormatter formatter;

    public CheckoutHandler() {
        this.orderService = new OrderService();
        this.formatter = new PriceFormatter();
    }

    public String checkout(double subtotal, String tier) {
        double total = orderService.getOrderTotal(subtotal, tier);
        return "Order total: " + formatter.format(total);
    }
}