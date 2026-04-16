package com.impactlens.demo.service;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class OrderServiceTest {
    @Test
    public void testPremiumOrderTotal() {
        OrderService s = new OrderService();
        // 100 - 20 (premium discount) + 6.40 (tax on 80) = 86.40
        assertEquals(86.40, s.getOrderTotal(100.0, "premium"), 0.001);
    }

    @Test
    public void testStandardOrderTotal() {
        OrderService s = new OrderService();
        assertEquals(97.20, s.getOrderTotal(100.0, "standard"), 0.001);
    }
}