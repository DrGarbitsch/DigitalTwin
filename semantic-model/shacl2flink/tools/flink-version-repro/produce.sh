#!/bin/bash
# Create the two topics and produce the four KEYED records (upsert stream).
B=repro-kafka:9092
for t in topic_a topic_b; do
  docker exec repro-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server $B \
    --create --topic $t --partitions 1 --replication-factor 1 2>&1 | tail -1
done

docker exec -i repro-kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server $B --topic topic_a \
  --property "parse.key=true" --property "key.separator=|" <<'EOF'
{"k":"a","d":"0"}|{"k":"a","d":"0","v":"v1","ts":"2026-01-01 00:00:01"}
{"k":"a","d":"0"}|{"k":"a","d":"0","v":"v2","ts":"2026-01-01 00:00:02"}
{"k":"a","d":"0"}|{"k":"a","d":"0","v":"v3","ts":"2026-01-01 00:00:03"}
EOF

docker exec -i repro-kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server $B --topic topic_b \
  --property "parse.key=true" --property "key.separator=|" <<'EOF'
{"k":"a","d":"0"}|{"k":"a","d":"0","v":"w1","ts":"2026-01-01 00:00:01"}
EOF

echo "offsets:"
docker exec repro-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server $B --topic topic_a
docker exec repro-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server $B --topic topic_b
