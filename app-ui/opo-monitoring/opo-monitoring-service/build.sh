#!/usr/bin/env bash

export JAVA_HOME='C:\Program Files\Java\jdk-25.0.1'
export PATH="/c/Program Files/Java/jdk-25.0.1/bin:$PATH"
export MAVEN_OPTS='-Djavax.net.ssl.trustStoreType=Windows-ROOT -Djavax.net.ssl.trustStore=NONE'


mvn \
  -U \
  -s "$HOME/.m2/settings.xml" \
  clean test
