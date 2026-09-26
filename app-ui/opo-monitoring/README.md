# OPO Monitoring BFF

The BFF has two explicit downstream boundaries:

- `RuntimeServiceClient` for chat, resume, and conversation retrieval.
- `AnalyticsFoundationClient` for deterministic Analytics Foundation operations.

Both HTTP implementations are plain Java classes. Spring creates them exclusively in `DownstreamClientConfiguration`, each with a separate `RestClient` base URL.

## Build

```bash
export JAVA_HOME="/c/Program Files/Java/jdk-25.0.1"
export PATH="$JAVA_HOME/bin:$PATH"
mvn -s "$HOME/.m2/settings.xml" -U clean test
```
