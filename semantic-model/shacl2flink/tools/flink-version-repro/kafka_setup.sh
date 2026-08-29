#!/bin/bash
# Bring up a single-node Kafka (KRaft) on a docker network, create the two
# topics and produce the four records as an UPSERT stream (keyed records, so
# upsert-kafka puts a ChangelogNormalize in front of each source -- which is
# the one component the filesystem reproducer did not exercise).
set -e
NET=reprnet
KAFKA=k3d-iff.localhost:12345/strimzi/kafka:0.45.0-kafka-3.9.0
D=/home/marcel/.claude/jobs/25e780a0/tmp/repro

docker network create $NET 2>/dev/null || true
docker rm -f repro-kafka 2>/dev/null || true

docker run -d --name repro-kafka --network $NET --user root \
  -e LOG_DIR=/tmp/kafka-logs-out -e KAFKA_HEAP_OPTS="-Xmx512M -Xms256M" \
  -v $D/server.properties:/tmp/server.properties \
  --entrypoint /bin/bash $KAFKA -c '
    /opt/kafka/bin/kafka-storage.sh format -t 5L6g3nShT-eMCtK--X86sw \
      -c /tmp/server.properties --ignore-formatted
    exec /opt/kafka/bin/kafka-server-start.sh /tmp/server.properties'

echo "waiting for kafka ..."
for i in $(seq 1 40); do
  if docker exec repro-kafka /opt/kafka/bin/kafka-topics.sh \
       --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then
    echo "kafka up"; break
  fi
  sleep 3
done

for t in topic_a topic_b; do
  docker exec repro-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 \
    --create --topic $t --partitions 1 --replication-factor 1 2>/dev/null || true
done

# three successive values for the SAME key on topic_a, one row on topic_b
docker exec -i repro-kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 --topic topic_a \
  --property "parse.key=true" --property "key.separator=|" <<'EOF'
{"k":"a","d":"0"}|{"k":"a","d":"0","v":"v1","ts":"2026-01-01 00:00:01"}
{"k":"a","d":"0"}|{"k":"a","d":"0","v":"v2","ts":"2026-01-01 00:00:02"}
{"k":"a","d":"0"}|{"k":"a","d":"0","v":"v3","ts":"2026-01-01 00:00:03"}
EOF

docker exec -i repro-kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 --topic topic_b \
  --property "parse.key=true" --property "key.separator=|" <<'EOF'
{"k":"a","d":"0"}|{"k":"a","d":"0","v":"w1","ts":"2026-01-01 00:00:01"}
EOF

echo "records produced:"
docker exec repro-kafka /opt/kafka/bin/kafka-run-class.sh kafka.tools.GetOffsetShell \
  --bootstrap-server localhost:9092 --topic topic_a 2>/dev/null
