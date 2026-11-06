#!/bin/bash
set -euxo pipefail
N=lt-net; P=lt-pg; C=lt-scorpio; K=lt-kafka
s=$SECONDS
docker pull -q postgis/postgis:14-3.4
docker pull -q apache/kafka-native:3.9.0
docker pull -q ibn40/scorpio-all-in-one-runner:v0.10
echo "image pulls: $((SECONDS-s))s"
s=$SECONDS
openssl genrsa -out "$OUT/key.pem" 2048
openssl rsa -in "$OUT/key.pem" -pubout -outform DER | base64 -w0 > "$OUT/pub.b64"
docker network create $N
docker run -d --name $K --network $N \
  -e KAFKA_NODE_ID=1 -e KAFKA_PROCESS_ROLES=broker,controller \
  -e KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093 -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://$K:9092 \
  -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT \
  -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@$K:9093 -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  -e KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1 -e KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1 \
  apache/kafka-native:3.9.0
docker run -d --name $P --network $N -e POSTGRES_USER=ngb -e POSTGRES_PASSWORD=ngb -e POSTGRES_DB=ngb postgis/postgis:14-3.4 \
  -c ssl=on -c ssl_cert_file=/etc/ssl/certs/ssl-cert-snakeoil.pem -c ssl_key_file=/etc/ssl/private/ssl-cert-snakeoil.key
for i in $(seq 1 60); do docker exec $P pg_isready -U ngb -d ngb -q && break; sleep 1; done
sleep 4
docker run -d --name $C --network $N -p 127.0.0.1:19090:9090 \
  -e POSTGRES_SERVICE=$P -e POSTGRES_PORT=5432 -e POSTGRES_DBNAME=ngb -e POSTGRES_USERNAME=ngb -e POSTGRES_USER=ngb -e POSTGRES_PASSWORD=ngb \
  -e KAFKA_BOOTSTRAP=$K -e KAFKA_BROKERS=$K -e KAFKA_PORT=9092 \
  -e REALM=iff -e CLIENT_ID=scorpio -e SSL_REQUIRED=none \
  -e QUARKUS_OIDC_PUBLIC_KEY="$(cat "$OUT/pub.b64")" -e QUARKUS_OIDC_TOKEN_ISSUER=any \
  ibn40/scorpio-all-in-one-runner:v0.10
code=000
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -m 3 -w '%{http_code}' http://127.0.0.1:19090/ngsi-ld/v1/types || true)
  [ "$code" != 000 ] && break
  sleep 2
done
test "$code" = 401
echo "stack up: $((SECONDS-s))s"
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' $P $K $C
