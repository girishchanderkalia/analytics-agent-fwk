package com.asml.analytics.facade.controller;
import com.asml.analytics.facade.dto.foundation.*;
import com.asml.analytics.facade.service.OpoAgentService;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/trends")
public class TrendController {
    private final OpoAgentService agentService;
    public TrendController(OpoAgentService agentService){this.agentService=agentService;}
    @PostMapping("/query") public TrendResponse query(@RequestBody TrendQuery request){return agentService.queryTrends(request);}
    @PostMapping("/distribution") public DistributionResponse distribution(@RequestBody DistributionQuery request){return agentService.getDistribution(request);}
}
