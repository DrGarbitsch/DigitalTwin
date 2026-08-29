#!/bin/bash
# Run the minimal Flink 2.1+ deduplication regression reproducer against one
# Flink version. Everything -- DDL, query and data -- goes through sql-client,
# so nothing but Kafka and Docker is needed.
#
#   ./kafka_setup.sh                       # once, starts `repro-kafka` on `reprnet`
#   ./run-minimal.sh <flink-image> <label> <kafka-connector-jar-url>
#
# e.g.
#   ./run-minimal.sh flink:1.20.4 1.20 \
#     https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.3.0-1.20/flink-sql-connector-kafka-3.3.0-1.20.jar
#   ./run-minimal.sh flink:2.3.0 2.3 \
#     https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/5.0.0-2.2/flink-sql-connector-kafka-5.0.0-2.2.jar
set -u
IMG="$1"; LABEL="$2"; JAR="$3"
D="$(cd "$(dirname "$0")" && pwd)"
JARNAME=$(basename "$JAR"); B=repro-kafka:9092; CN=sqlrep-$LABEL
DDL=${DDL:-minimal-ddl.sql}; RULE=${RULE:-minimal-query.sql}
STEPS=${STEPS:-minimal-inserts.sql}
say() { echo "[$LABEL] $*"; }
[ -f "$D/$JARNAME" ] || curl -sSL -o "$D/$JARNAME" "$JAR"

for t in r_entities r_attributes r_verdict; do
  docker exec repro-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server $B \
    --delete --topic $t >/dev/null 2>&1
done
sleep 4
for t in r_entities r_attributes r_verdict; do
  docker exec repro-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server $B \
    --create --topic $t --partitions 1 --replication-factor 1 >/dev/null 2>&1
done

# every sql-client invocation is its own session, so each script repeats the DDL
cat "$D/$DDL" "$D/$RULE" > "$D/_query.sql"
python3 - "$D" "$STEPS" "$DDL" <<'EOF'
import sys
d = sys.argv[1]
ddl = open(d + '/' + sys.argv[3]).read()
steps = open(d + '/' + sys.argv[2]).read().split('-- ===== STEP')
for i, s in enumerate(steps[1:], start=1):
    open(f'{d}/_step{i}.sql', 'w').write(ddl + '\n-- ===== STEP' + s)
EOF

docker rm -f $CN >/dev/null 2>&1
docker run -d --name $CN --network reprnet -v "$D":/data -e JARNAME="$JARNAME" \
  --entrypoint /bin/bash "$IMG" /data/start-flink.sh >/dev/null
sleep 15

run() { docker exec $CN bash -c "cd /opt/flink && ./bin/sql-client.sh -f /data/$1 2>&1 | tail -2" \
        | sed "s/^/[$LABEL] /"; }

say "submit the query";                              run _query.sql; sleep 30
say "step 1: the entity appears (expect 'ok')";      run _step1.sql; sleep 35
say "step 2: violation appears (expect 'critical')"; run _step2.sql; sleep 60
say "step 3: violation clears (expect 'ok' again)";  run _step3.sql; sleep 60

say "verdict topic:"
docker exec repro-kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server $B \
  --topic r_verdict --from-beginning --timeout-ms 15000 2>/dev/null \
  | sed "s/^/[$LABEL]    /"
docker rm -f $CN >/dev/null 2>&1
