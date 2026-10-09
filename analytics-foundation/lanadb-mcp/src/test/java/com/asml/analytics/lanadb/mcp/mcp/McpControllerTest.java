package com.asml.analytics.lanadb.mcp.mcp;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.asml.analytics.lanadb.mcp.waferkpi.WaferLevelKpi;
import com.asml.analytics.lanadb.mcp.waferkpi.WaferLevelKpiRepository;
import com.asml.analytics.lanadb.mcp.waferkpi.WaferLevelKpiResult;
import com.asml.analytics.lanadb.mcp.waferkpi.WaferLevelKpiTool;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

@WebMvcTest(McpController.class)
@Import(WaferLevelKpiTool.class)
class McpControllerTest {

    private static final String WINDOW =
            "\"lotExposureStartFrom\":\"2024-12-01T00:00:00Z\",\"lotExposureStartTo\":\"2024-12-31T00:00:00Z\"";

    @Autowired
    private MockMvc mvc;

    @MockitoBean
    private WaferLevelKpiRepository repository;

    private ResultActions rpc(String body) throws Exception {
        return mvc.perform(post("/mcp").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.jsonrpc").value("2.0"));
    }

    private static String call(String arguments) {
        return "{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"tools/call\",\"params\":"
                + "{\"name\":\"getWaferLevelKpis\",\"arguments\":{" + arguments + "}}}";
    }

    @Test
    void listsWaferLevelKpiToolWithSchemas() throws Exception {
        rpc("{\"jsonrpc\":\"2.0\",\"id\":\"list\",\"method\":\"tools/list\",\"params\":{}}")
                .andExpect(jsonPath("$.id").value("list"))
                .andExpect(jsonPath("$.result.tools[0].name").value("getWaferLevelKpis"))
                .andExpect(jsonPath("$.result.tools[0].inputSchema.required[0]").value("lotExposureStartFrom"))
                .andExpect(jsonPath("$.result.tools[0].inputSchema.properties.chuckIds.type").value("array"))
                .andExpect(jsonPath("$.result.tools[0].outputSchema.properties.rows.type").value("array"))
                .andExpect(jsonPath("$.result.tools[0].annotations.readOnlyHint").value(true));
    }

    @Test
    void returnsStructuredRows() throws Exception {
        var row = new WaferLevelKpi("Y82A", "4984123.003", "DC", "GF6SF310SEA1", "Chuck1", new BigDecimal("80"),
                "CW41", "2782", OffsetDateTime.parse("2024-12-04T05:45:16Z"), 23.7, 20.33, false);
        when(repository.getWaferLevelKpis(any())).thenReturn(new WaferLevelKpiResult(List.of(row), 1, false));

        rpc(call(WINDOW + ",\"chuckIds\":[\"Chuck1\"]"))
                .andExpect(jsonPath("$.id").value(7))
                .andExpect(jsonPath("$.result.isError").value(false))
                .andExpect(jsonPath("$.result.structuredContent.rowCount").value(1))
                .andExpect(jsonPath("$.result.structuredContent.truncated").value(false))
                .andExpect(jsonPath("$.result.structuredContent.rows[0].chuckId").value("Chuck1"))
                .andExpect(jsonPath("$.result.structuredContent.rows[0].lotStart").value("2024-12-04T05:45:16Z"))
                .andExpect(jsonPath("$.result.structuredContent.rows[0].kpiValue1").value(23.7))
                .andExpect(jsonPath("$.result.content[0].type").value("text"))
                .andExpect(jsonPath("$.result.content[0].text").value(containsString("GF6SF310SEA1")));
    }

    @Test
    void invalidArgumentsAreInvalidParams() throws Exception {
        rpc(call("\"lotExposureStartFrom\":\"yesterday\",\"lotExposureStartTo\":\"2024-12-31T00:00:00Z\""))
                .andExpect(jsonPath("$.error.code").value(-32602))
                .andExpect(jsonPath("$.error.message").value(containsString("lotExposureStartFrom")));
        verify(repository, never()).getWaferLevelKpis(any());
    }

    @Test
    void databaseFailureDoesNotLeakDetails() throws Exception {
        when(repository.getWaferLevelKpis(any()))
                .thenThrow(new DataAccessResourceFailureException("password authentication failed for jdbc:secret"));

        rpc(call(WINDOW))
                .andExpect(jsonPath("$.error.code").value(-32000))
                .andExpect(jsonPath("$.error.message").value(not(containsString("secret"))));
    }

    @Test
    void rejectsUnknownToolMethodAndVersion() throws Exception {
        rpc("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"dropTables\"}}")
                .andExpect(jsonPath("$.error.code").value(-32602));
        rpc("{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"resources/list\"}")
                .andExpect(jsonPath("$.error.code").value(-32601));
        rpc("{\"jsonrpc\":\"1.0\",\"id\":3,\"method\":\"tools/list\"}")
                .andExpect(jsonPath("$.error.code").value(-32600));
    }
}
