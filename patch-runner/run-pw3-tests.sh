#!/bin/sh
set -eu
mkdir -p /tmp/pw3-source /tmp/gradle
cp -a /src/. /tmp/pw3-source/
cp -a /opt/gradle/. /tmp/gradle/
cd /tmp/pw3-source
export GRADLE_USER_HOME=/tmp/gradle
sh ./gradlew --offline --no-daemon test bootJar "$@"
if [ -d /out ]; then
  found=0
  for jar in build/libs/*.jar; do
    case "$jar" in *-plain.jar) continue;; esac
    cp "$jar" /out/app.jar
    found=1
    break
  done
  test "$found" -eq 1
fi
