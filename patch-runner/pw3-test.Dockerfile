FROM mcr.microsoft.com/playwright/java:v1.63.0-noble
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"
RUN groupadd --gid 65532 runner && useradd --uid 65532 --gid 65532 --home-dir /home/runner --create-home runner
COPY --from=gradlecache /caches /opt/gradle/caches
COPY --from=gradlecache /wrapper/dists /opt/gradle/wrapper/dists
COPY --chmod=755 run-pw3-tests.sh /opt/run-pw3-tests.sh
RUN chown -R 65532:65532 /opt/gradle /home/runner
USER 65532:65532
ENV HOME=/home/runner
ENTRYPOINT ["/opt/run-pw3-tests.sh"]
