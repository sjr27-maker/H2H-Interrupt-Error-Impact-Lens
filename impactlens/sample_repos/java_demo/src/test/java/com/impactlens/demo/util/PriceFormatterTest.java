package com.impactlens.demo.util;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class PriceFormatterTest {
    @Test
    public void testFormatBasic() {
        PriceFormatter f = new PriceFormatter();
        assertEquals("$10.50", f.format(10.5));
    }

    @Test
    public void testFormatWithCurrency() {
        PriceFormatter f = new PriceFormatter();
        assertEquals("EUR 10.50", f.formatWithCurrency(10.5, "EUR"));
    }
}