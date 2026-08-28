#!/bin/bash
# Cycle reproducer: submit the looping statement set, drive N updates of ONE
# key, then count what each topic received. Amplification = far more than N.
#   usage: run_cycle.sh <image> <label> <connector-jar-url> [updates]
IMG="$1"; LABEL="$2"; JAR="$3"; N="${4:-20}"; SQL="${5:-cycle_repro.sql}"
D=/home/marcel/.claude/jobs/25e780a0/tmp/repro
JARNAME=$(basename "$JAR")
B=repro-kafka:9092
CN=cycle-$LABEL

say() { echo "[$LABEL] $*"; }

[ -f "$D/$JARNAME" ] || curl -sSL -o "$D/$JARNAME" "$JAR"

# fresh topics for every run so counts are unambiguous
for t in topic_a topic_b topic_trigger topic_alerts; do
  docker exec repro-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server $B \
    --delete --topic $t >/dev/null 2>&1
done
sleep 5
for t in topic_a topic_b topic_trigger topic_alerts; do
  docker exec repro-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server $B \
    --create --topic $t --partitions 1 --replication-factor 1 >/dev/null 2>&1
done

# one row on b, before the job starts
KEYS="${KEYS:-1}"
for kk in $(seq 1 "$KEYS"); do
  echo "{\"k\":\"k$kk\",\"d\":\"0\"}|{\"k\":\"k$kk\",\"d\":\"0\",\"v\":\"w1\",\"ts\":\"2026-01-01 00:00:01\"}"
done | docker exec -i repro-kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server $B --topic topic_b \
  --property parse.key=true --property key.separator='|' >/dev/null 2>&1

docker rm -f $CN >/dev/null 2>&1
docker run -d --name $CN --network reprnet -v "$D":/data \
  --entrypoint /bin/bash "$IMG" -c "
     cp /data/$JARNAME /opt/flink/lib/
     cd /opt/flink && ./bin/start-cluster.sh && sleep 3600" >/dev/null
sleep 15
say "submitting the looping statement set"
docker exec -e SQL="$SQL" $CN bash -c 'cd /opt/flink && ./bin/sql-client.sh -f /data/$SQL 2>&1 | tail -6' \
  | sed "s/^/[$LABEL] /"
sleep 20

say "driving $N updates of ONE key"
KEYS="${KEYS:-1}"
for i in $(seq 1 "$N"); do
  for kk in $(seq 1 "$KEYS"); do
    echo "{\"k\":\"k$kk\",\"d\":\"0\"}|{\"k\":\"k$kk\",\"d\":\"0\",\"v\":\"v$i\",\"ts\":\"2026-01-01 00:00:0$((i % 9 + 1))\"}"
  done
done | docker exec -i repro-kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server $B --topic topic_a \
  --property parse.key=true --property key.separator='|' >/dev/null 2>&1

say "settling 60s"
sleep 60

say "records per topic (input was $N updates + 1 row on b):"
for t in topic_a topic_b topic_trigger topic_alerts; do
  off=$(docker exec repro-kafka /opt/kafka/bin/kafka-get-offsets.sh \
          --bootstrap-server $B --topic $t 2>/dev/null | cut -d: -f3)
  printf '[%s]   %-16s %s\n' "$LABEL" "$t" "${off:-0}"
done
docker rm -f $CN >/dev/null 2>&1
