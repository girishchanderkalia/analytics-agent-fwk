# OPO Monitoring BFF

The BFF has two explicit downstream boundaries:

- `RuntimeServiceClient` for chat, resume, and conversation retrieval.
- `AnalyticsFoundationClient` for deterministic Analytics Foundation operations.

Both HTTP implementations are plain Java classes. Spring creates them exclusively in `DownstreamClientConfiguration`, each with a separate `RestClient` base URL.

## Front end

`FrontEndConfiguration` serves the browser UI from `../opo-monitoring-fe/static` on the BFF origin, so the UI needs no CORS configuration and no second server. Override the location with `UI_STATIC_LOCATION` when the assets are deployed elsewhere, as the container image does.

The Application dropdown switches between existing OPO monitoring (`/`) and Overlay data analysis (`/overlay`). Overlay analysis queries `POST /api/trends/overlay/query`, forwarded by `AnalyticsFoundationClient` to Foundation's `POST /overlay/trends/query`. It does not invoke the agent runtime. The page supports all five lot-level measured-overlay metrics, product/layer/equipment/lot/date filters, X/Y chart traces, a lot-step horizontal-axis option, and CSV export. Foundation request/response field names are preserved on this dedicated route.

Overlay chat uses application ID `overlay-data-analysis` and agent
`overlay-analysis-agent`, independently of OPO's `opo-monitoring` identity.
Agent discovery uses the page's application ID. Each chat sends the last
successfully displayed metric, filters and X/Y measurement snapshot as
`applicationContext.overlay`; failed or pending queries do not supply stale data.
The read-only overlay agent answers questions about that snapshot without invoking
OPO capabilities or changing chart filters. Apply another metric or filter on the
page before asking about that data. Restart the runtime with the updated startup
configuration to register the new application. Both chats require a configured
model gateway; data charts do not.

## Build

```bash
export JAVA_HOME="/c/Program Files/Java/jdk-25.0.1"
export PATH="$JAVA_HOME/bin:$PATH"
mvn -s "$HOME/.m2/settings.xml" -U clean test
```
