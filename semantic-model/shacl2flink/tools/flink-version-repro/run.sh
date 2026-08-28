#!/bin/bash
# Run the reproducer inside a Flink container: start a standalone cluster,
# execute the SQL script, print the results.
#   usage: run.sh <image> <label>
IMG="$1"
LABEL="$2"
SQL="${3:-repro.sql}"
D=/home/marcel/.claude/jobs/25e780a0/tmp/repro
docker run --rm -e SQLFILE="$SQL" -v "$D":/data --entrypoint /bin/bash "$IMG" -c '
  set -e
  FLINK=$(ls -d /opt/flink 2>/dev/null || ls -d /opt/flink-* | head -1)
  cd "$FLINK"
  echo "flink dist: $FLINK"
  ./bin/flink --version 2>/dev/null | head -2 || cat RELEASE 2>/dev/null | head -2
  export FLINK_CONF_DIR=$FLINK/conf
  # a single TaskManager slot is enough; keep memory small
  ./bin/start-cluster.sh >/dev/null 2>&1
  sleep 12
  ./bin/sql-client.sh -f /data/$SQLFILE 2>&1 | tail -120
  ./bin/stop-cluster.sh >/dev/null 2>&1
' 2>&1 | sed "s/^/[$LABEL] /"
