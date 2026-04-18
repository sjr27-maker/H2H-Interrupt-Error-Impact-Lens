package com.impactlens.demo.api;

import com.impactlens.demo.service.OrderService;
import com.impactlens.demo.util.PriceFormatter;
import com.impactlens.demo.util.CurrencyConverter;

public class CheckoutHandler {
    private final OrderService orderService;
    private final PriceFormatter formatter;
    private final CurrencyConverter currencyConverter;

    public CheckoutHandler() {
        this.orderService = new OrderService();
        this.formatter = new PriceFormatter();
        this.currencyConverter = new CurrencyConverter();
    }

    public String checkout(double subtotal, String tier) {
        double total = orderService.getOrderTotal(subtotal, tier);
        return "Order total: " + formatter.format(total);
    }

    public String checkoutInCurrency(double subtotal, String tier, String currency) {
        double total = orderService.getOrderTotal(subtotal, tier);
        double converted = currencyConverter.convert(total, "USD", currency);
        return "Order total: " + formatter.formatWithCurrency(converted, currency);
    }
}
