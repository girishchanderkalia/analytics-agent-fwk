// Adapts the current BFF contract to the legacy shape `app.js` renders.
//
// The BFF speaks camelCase over `/api/trends/**` and `/api/investigations/**`
// and returns a persisted runtime envelope. The UI was written against the
// older same-origin `/trends`, `/chat`, `/resume`, `/threads/{id}` routes with
// a `status` + `evidence` payload, so the translation lives here instead of
// being spread through the rendering code.

const AGENT_ID = window.OPO_AGENT_ID || "opo-monitoring-agent";
const TREND_LOOKBACK_DAYS = 14;

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

function toLegacyResponse(runtime) {
  const evidence = runtime.result || {};
  const base = { thread_id: runtime.conversationId, evidence, version: runtime.version };

  if (runtime.approvalRequest) {
    return { ...base, status: "awaiting_human", request: runtime.approvalRequest };
  }
  if (evidence.cancelled_at) {
    return { ...base, status: "cancelled", cancelled_at: evidence.cancelled_at };
  }
  if (!(evidence.outliers || []).length) {
    return { ...base, status: "no_outliers" };
  }
  return { ...base, status: "complete", findings: evidence.findings };
}

// The gate payloads `app.js` builds are free-form, so the known keys are lifted
// into first-class resume fields and the whole decision is preserved in values.
function toResumeRequest(decision, expectedVersion) {
  const value = decision && typeof decision === "object" ? decision : { approved: decision !== false };
  return {
    approved: value.approved !== false,
    selectedOutlierId: value.machine ?? value.selected_outlier_id ?? null,
    comment: value.message ?? null,
    expectedVersion: expectedVersion ?? null,
    values: value,
  };
}

window.OpoBff = {
  async loadTrends() {
    const body = { filters: { days: TREND_LOOKBACK_DAYS }, groupBy: [] };
    const response = await postJson("/api/trends/query", body);
    return response.series || [];
  },

  async startChat(message, useToolCalling) {
    const runtime = await postJson("/api/investigations/chat", {
      agentId: AGENT_ID,
      message,
      applicationContext: { useToolCalling: Boolean(useToolCalling), source: "opo-monitoring-fe" },
    });
    return toLegacyResponse(runtime);
  },

  async resume(conversationId, decision, expectedVersion) {
    const runtime = await postJson(
      `/api/investigations/${encodeURIComponent(conversationId)}/resume`,
      toResumeRequest(decision, expectedVersion),
    );
    return toLegacyResponse(runtime);
  },

  async getConversation(conversationId) {
    const runtime = await requestJson(
      `/api/investigations/${encodeURIComponent(conversationId)}`,
    );
    const legacy = toLegacyResponse(runtime);
    return { ...legacy, values: runtime.result || {} };
  },
};
