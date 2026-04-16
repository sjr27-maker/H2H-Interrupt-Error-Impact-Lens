package com.impactlens.demo.api;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class CheckoutHandlerTest {
    @Test
    public void testCheckoutPremium() {
        CheckoutHandler h = new CheckoutHandler();
        String result = h.checkout(100.0, "premium");
        assertTrue(result.contains("86.40"));
    }
}