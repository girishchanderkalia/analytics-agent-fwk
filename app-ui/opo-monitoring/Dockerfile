FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/opo-monitoring-bff-0.1.0.jar app.jar
USER 10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
