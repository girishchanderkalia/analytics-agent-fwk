package com.asml.analytics.facade.controller;
import com.asml.analytics.facade.client.AnalyticsFoundationClient;
import com.asml.analytics.facade.dto.foundation.*;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/trends")
public class TrendController {
    private final AnalyticsFoundationClient client;
    public TrendController(AnalyticsFoundationClient client){this.client=client;}
    @PostMapping("/query") public TrendResponse query(@RequestBody TrendQuery request){return client.queryTrends(request);}
    @PostMapping("/overlay/query") public java.util.Map<String,Object> overlay(@RequestBody java.util.Map<String,Object> request){return client.queryOverlayTrends(request);}
    @PostMapping("/distribution") public DistributionResponse distribution(@RequestBody DistributionQuery request){return client.getDistribution(request);}
}
