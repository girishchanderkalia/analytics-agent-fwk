package com.asml.analytics.facade.dto.runtime;
import java.util.List;
public record RegisteredAgentList(String applicationId, List<RegisteredAgent> agents) {
    public RegisteredAgentList { agents = agents == null ? List.of() : List.copyOf(agents); }
}
