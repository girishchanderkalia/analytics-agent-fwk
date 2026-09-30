package com.asml.analytics.facade.client;

import com.asml.analytics.facade.controller.TrendController;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.client.RestClient;

import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class OverlayTrendTest {
    @Test
    void forwardsMetricFiltersAndBothCoordinatesToFoundation() throws Exception {
        var builder = RestClient.builder().baseUrl("http://foundation");
        var server = MockRestServiceServer.bindTo(builder).build();
        var request = """
                {"metric":"MAX_997","product_ids":["P1"],"start_date":"2026-01-01"}
                """;
        server.expect(requestTo("http://foundation/overlay/trends/query"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().json(request))
                .andRespond(withSuccess("""
                        {"kpi":"MEASURED_OVERLAY","metric":"MAX_997","points":[
                          {"lot_step_id":1,"kpi_x":3.011,"kpi_y":null,"needs_ingestion":false}
                        ]}
                        """, MediaType.APPLICATION_JSON));
        var mvc = MockMvcBuilders.standaloneSetup(
                new TrendController(new HttpAnalyticsFoundationClient(builder.build()))).build();
        mvc.perform(post("/api/trends/overlay/query")
                        .contentType(MediaType.APPLICATION_JSON).content(request))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metric").value("MAX_997"))
                .andExpect(jsonPath("$.points[0].kpi_x").value(3.011))
                .andExpect(jsonPath("$.points[0].needs_ingestion").value(false));
        server.verify();
    }
}