# Build context is app-ui/opo-monitoring so the front end ships with the BFF.
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY opo-monitoring-service/target/opo-monitoring-bff-0.1.0.jar app.jar
COPY opo-monitoring-fe/static /app/ui/static
ENV UI_STATIC_LOCATION=file:/app/ui/static/
USER 10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
