#!/bin/bash
# Run a SQL script against a Flink image, on the same docker network as the
# reproducer's Kafka, with the matching flink-sql-connector-kafka jar.
#   usage: run_kafka.sh <image> <label> <connector-jar-url> [sqlfile]
IMG="$1"; LABEL="$2"; JAR="$3"; SQL="${4:-kafka_repro.sql}"
D=/home/marcel/.claude/jobs/25e780a0/tmp/repro
JARNAME=$(basename "$JAR")
if [ ! -f "$D/$JARNAME" ]; then
  echo "[$LABEL] downloading $JARNAME"
  curl -sSL -o "$D/$JARNAME" "$JAR" || { echo "[$LABEL] download failed"; exit 1; }
fi
ls -la "$D/$JARNAME" | awk '{print "['"$LABEL"'] jar", $5, $9}'
docker run --rm --network reprnet -e SQLFILE="$SQL" -e JARNAME="$JARNAME" \
  -v "$D":/data --entrypoint /bin/bash "$IMG" -c '
  set -e
  FLINK=/opt/flink
  cp /data/$JARNAME $FLINK/lib/
  cd "$FLINK"
  export FLINK_CONF_DIR=$FLINK/conf
  ./bin/start-cluster.sh >/dev/null 2>&1
  sleep 12
  ./bin/sql-client.sh -f /data/$SQLFILE 2>&1 | tail -140
  ./bin/stop-cluster.sh >/dev/null 2>&1
' 2>&1 | sed "s/^/[$LABEL] /"
