package com.impactlens.demo.util;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class CurrencyConverterTest {
    @Test
    public void testUsdToEur() {
        CurrencyConverter c = new CurrencyConverter();
        assertEquals(92.0, c.convert(100.0, "USD", "EUR"), 0.1);
    }

    @Test
    public void testSameCurrency() {
        CurrencyConverter c = new CurrencyConverter();
        assertEquals(100.0, c.convert(100.0, "USD", "USD"), 0.001);
    }
}
