// HTTP boundary for the OPO Monitoring UI.
//
// The BFF speaks camelCase over `/api/trends/**` and `/api/investigations/**`
// and returns the persisted runtime envelope (`conversationId`, `agentId`,
// `agentVersion`, `status`, `version`, `result`, `approvalRequest`). That
// envelope reaches the renderer unchanged; the only shaping here is building
// the request DTOs the API declares.

const AGENT_ID = window.OPO_AGENT_ID || "opo-monitoring-agent";
const APPLICATION_ID = window.OPO_APPLICATION_ID || "opo-monitoring";

async function requestJson(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json();
}

function postJson(path, body) {
  return requestJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// `values` are applied as workflow state updates and rejected when a key is not
// a declared state field, so the first-class decision keys are not repeated.
function toResumeRequest(decision, expectedVersion) {
  const value = decision ?? {};
  return {
    approved: value.approved !== false,
    selectedOutlierId: value.selectedOutlierId ?? null,
    comment: value.comment ?? null,
    expectedVersion: expectedVersion ?? null,
    values: value.values ?? {},
  };
}

window.OpoBff = {
  async loadTrends() {
    // No lookback: a relative window silently hides everything older than it.
    const response = await postJson("/api/trends/query", { filters: {}, groupBy: [] });
    return Array.isArray(response.series) ? response.series : response.series?.series || [];
  },

  async listAgents() {
    const response = await requestJson(
      `/api/applications/${encodeURIComponent(APPLICATION_ID)}/agents`,
    );
    return response.agents || [];
  },

  startChat(message, agent, availableTrendScopes = []) {
    return postJson("/api/investigations/chat", {
      applicationId: APPLICATION_ID,
      agentId: agent?.agentId || AGENT_ID,
      agentVersion: agent?.version ?? null,
      message,
      applicationContext: { source: "opo-monitoring-fe", available_trend_scopes: availableTrendScopes },
    });
  },

  resume(conversationId, decision, expectedVersion) {
    return postJson(
      `/api/investigations/${encodeURIComponent(conversationId)}/resume`,
      toResumeRequest(decision, expectedVersion),
    );
  },

  getConversation(conversationId) {
    return requestJson(`/api/investigations/${encodeURIComponent(conversationId)}`);
  },
};
