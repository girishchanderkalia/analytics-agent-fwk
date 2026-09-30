package com.asml.analytics.facade.config;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(properties = "ui.static-location=file:../opo-monitoring-fe/static/")
@AutoConfigureMockMvc
class FrontEndConfigurationTest {
    @Autowired
    MockMvc mvc;

    @Test
    void revalidatesPagesAndAssetsRatherThanServingStaleLayouts() throws Exception {
        for (String asset : new String[]{"overlay.html", "index.html", "overlay.css", "bff-client.js"}) {
            mvc.perform(get("/static/" + asset))
                    .andExpect(status().isOk())
                    .andExpect(header().string("Cache-Control", "no-cache"));
        }
    }
}