# OPO Monitoring BFF

The BFF has two explicit downstream boundaries:

- `RuntimeServiceClient` for chat, resume, and conversation retrieval.
- `AnalyticsFoundationClient` for deterministic Analytics Foundation operations.

Both HTTP implementations are plain Java classes. Spring creates them exclusively in `DownstreamClientConfiguration`, each with a separate `RestClient` base URL.

## Front end

`FrontEndConfiguration` serves the browser UI from `../opo-monitoring-fe/static` on the BFF origin, so the UI needs no CORS configuration and no second server. Override the location with `UI_STATIC_LOCATION` when the assets are deployed elsewhere, as the container image does.

## Build

```bash
export JAVA_HOME="/c/Program Files/Java/jdk-25.0.1"
export PATH="$JAVA_HOME/bin:$PATH"
mvn -s "$HOME/.m2/settings.xml" -U clean test
```
