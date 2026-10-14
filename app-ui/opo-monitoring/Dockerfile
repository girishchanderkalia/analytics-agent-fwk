# Build context is app-ui/opo-monitoring so the front end ships with the BFF.
FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /workspace
COPY opo-monitoring-service/pom.xml ./opo-monitoring-service/pom.xml
COPY opo-monitoring-service/src ./opo-monitoring-service/src
RUN mvn -B -ntp -f opo-monitoring-service/pom.xml package

FROM eclipse-temurin:21-jre
WORKDIR /app
RUN groupadd --system --gid 10001 app && \
    useradd --system --uid 10001 --gid app --no-create-home app
COPY --from=build --chown=10001:10001 /workspace/opo-monitoring-service/target/opo-monitoring-bff-0.1.0.jar /app/app.jar
COPY --chown=10001:10001 opo-monitoring-fe/static /app/ui/static
ENV UI_STATIC_LOCATION=file:/app/ui/static/
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "/app/app.jar"]
