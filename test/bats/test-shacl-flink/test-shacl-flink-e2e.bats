#!/usr/bin/env bats

# End-to-end tests for the SHACL -> Flink validation pipeline.
#
# These drive Kafka directly rather than going through Scorpio and the bridges,
# so a failure points at Flink and the generated SQL rather than at everything
# upstream of it. An entity written to the entities topic is all the pipeline
# needs to start validating: minCount constraints fire on an entity that has no
# attributes at all.

if [ -z "${SELF_HOSTED_RUNNER}" ]; then
    SUDO="sudo -E"
fi
DEBUG=${DEBUG:-false}          # set true to skip kubefwd (assumes forwarding is already up)
NAMESPACE=${NAMESPACE:-iff}
KAFKA_BOOTSTRAP=my-cluster-kafka-bootstrap:9092
ENTITY_TOPIC=iff.ngsild.entities
ATTRIBUTES_TOPIC=iff.ngsild.attributes
BASE=https://industryfusion.github.io/contexts/example/v0/base_entities
BULK_ALERTS_TOPIC=iff.alerts.bulk
STATEMENTSET=shacl-validation
CUTTER_TYPE=https://industryfusion.github.io/contexts/example/v0/base_entities/Cutter
ALERTS_OUT=/tmp/SHACL_FLINK_ALERTS
# A fresh id per run: alerts_bulk is an upsert topic keyed by (resource, event),
# so reusing an id from an earlier run would produce an identical value that
# Flink has no reason to re-emit, and the test would hang waiting for it.
RUN_ID=$(date +%s)
TEST_CUTTER="urn:e2e-flink-cutter:${RUN_ID}"
TEST_UNKNOWN="urn:e2e-flink-unknown:${RUN_ID}"
TEST_CLEAR="urn:e2e-flink-clear:${RUN_ID}"

setup() {
    # shellcheck disable=SC2086
    [ "$DEBUG" = "true" ] || (exec ${SUDO} kubefwd -n ${NAMESPACE} -l app.kubernetes.io/name=kafka svc >/dev/null 2>&1) &
    echo "# launched kubefwd for kafka" >&3
    sleep 3
}

teardown() {
    # shellcheck disable=SC2086
    [ "$DEBUG" = "true" ] || ${SUDO} killall kubefwd 2>/dev/null || true
    rm -f ${ALERTS_OUT}
}

publish_entity() {
    local id=$1 type=$2
    echo "{\"id\":\"${id}\",\"type\":\"${type}\"}" \
        | kafkacat -P -t ${ENTITY_TOPIC} -b ${KAFKA_BOOTSTRAP}
}

publish_attribute() {
    local entity=$1 attr_id=$2 name=$3
    printf '{"id":"%s\\\\%s","entityId":"%s","name":"%s","nodeType":"@id","type":"https://uri.etsi.org/ngsi-ld/Property","attributeValue":"x","datasetId":"@none","synced":true}\n' \
        "${entity}" "${attr_id}" "${entity}" "${name}" \
        | kafkacat -P -t ${ATTRIBUTES_TOPIC} -b ${KAFKA_BOOTSTRAP}
}

# Tail alerts into a file so the consumer is already attached before the entity
# is published -- otherwise the alert can be produced before we start listening.
start_alert_capture() {
    # Capture key AND value. An alert is retracted by a TOMBSTONE -- a record
    # whose value is empty and whose resource lives only in the key. Consuming
    # values alone makes every retraction invisible.
    (exec stdbuf -oL kafkacat -C -t ${BULK_ALERTS_TOPIC} -b ${KAFKA_BOOTSTRAP} -o end -f '%k;%s\n' >${ALERTS_OUT}) &
    sleep 3
}

stop_alert_capture() {
    killall kafkacat 2>/dev/null || true
}

# Poll rather than sleep a fixed amount: validation normally lands in a couple
# of seconds, but a busy cluster can be slower and a fixed sleep makes the test
# either flaky or needlessly slow.
wait_for_alert() {
    local pattern=$1 timeout=${2:-60} waited=0
    while [ "${waited}" -lt "${timeout}" ]; do
        if grep -q "${pattern}" ${ALERTS_OUT} 2>/dev/null; then
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    return 1
}

@test "shacl-validation statementset is deployed and running" {
    run kubectl -n "${NAMESPACE}" get beamsqlstatementsets "${STATEMENTSET}" -o jsonpath='{.status.state}'
    [ "$status" -eq 0 ]
    echo "# statementset state: ${output}" >&3
    [ "$output" = "RUNNING" ]
}

@test "flink job for shacl-validation has every task running" {
    pod=$(kubectl -n "${NAMESPACE}" get pods -l component=jobmanager -o jsonpath='{.items[0].metadata.name}')
    [ -n "${pod}" ]
    run kubectl -n "${NAMESPACE}" exec "${pod}" -c flink-main-container -- \
        curl -s http://localhost:8081/jobs/overview
    [ "$status" -eq 0 ]
    # every task of the shacl job must be running, not merely most of them:
    # a partially deployed job silently validates only part of the model
    result=$(echo "${output}" | python3 -c "
import json, sys
jobs = [j for j in json.load(sys.stdin)['jobs']
        if 'shacl-validation' in j['name'] and j['state'] == 'RUNNING']
if not jobs:
    print('NO_RUNNING_JOB')
else:
    j = jobs[0]
    print('OK' if j['tasks']['running'] == j['tasks']['total'] else
          f\"PARTIAL {j['tasks']['running']}/{j['tasks']['total']}\")")
    echo "# flink job task state: ${result}" >&3
    [ "${result}" = "OK" ]
}

@test "a Cutter entity with no attributes raises minCount alerts" {
    start_alert_capture
    publish_entity "${TEST_CUTTER}" "${CUTTER_TYPE}"
    echo "# published ${TEST_CUTTER}" >&3

    # The Cutter shape requires hasState and hasFilter, so an entity carrying
    # neither must be reported. This exercises the whole compiled pipeline:
    # entity source -> constraint join -> trigger table -> alerts.
    run wait_for_alert "${TEST_CUTTER}.*CountConstraintComponent" 90
    stop_alert_capture
    if [ "$status" -ne 0 ]; then
        echo "# no alert seen for ${TEST_CUTTER}; captured alerts were:" >&3
        grep "e2e-flink" ${ALERTS_OUT} >&3 || echo "# (none)" >&3
    fi
    [ "$status" -eq 0 ]

    run grep "${TEST_CUTTER}" ${ALERTS_OUT}
    echo "# ${output}" >&3
    [[ "${output}" == *"hasState"* ]] || [[ "${output}" == *"hasFilter"* ]]
    [[ "${output}" == *"warning"* ]]
}

wait_for_retraction() {
    # A retraction is a tombstone: key;<empty value>. Match the key with literal
    # substrings via awk rather than a regex -- the event name contains "(", ")"
    # and "}", which are ERE metacharacters and silently break a grep pattern.
    local resource=$1 fragment=$2 timeout=${3:-90} waited=0
    while [ "${waited}" -lt "${timeout}" ]; do
        if awk -F';' -v r="${resource}" -v f="${fragment}" \
            'index($1,r) && index($1,f) && $2=="" {found=1} END {exit !found}' \
            "${ALERTS_OUT}" 2>/dev/null; then
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    return 1
}

@test "supplying the missing attribute retracts the minCount alert" {
    start_alert_capture
    publish_entity "${TEST_CLEAR}" "${CUTTER_TYPE}"
    run wait_for_alert "${TEST_CLEAR}.*hasState" 90
    [ "$status" -eq 0 ]
    echo "# minCount alert raised for ${TEST_CLEAR}" >&3

    # Now satisfy hasState. The alert must be RETRACTED, which on an upsert
    # topic means a tombstone rather than a new value -- a test that only reads
    # values would never see the clear and would wrongly report a stuck alert.
    publish_attribute "${TEST_CLEAR}" a1 "${BASE}/hasState"
    run wait_for_retraction "${TEST_CLEAR}" "hasState)" 90
    stop_alert_capture
    if [ "$status" -ne 0 ]; then
        echo "# no retraction seen; captured:" >&3
        grep -c "${TEST_CLEAR}" "${ALERTS_OUT}" >&3 || echo "# (no lines captured)" >&3
    fi
    [ "$status" -eq 0 ]
}

@test "an entity of an unconstrained type raises no shacl alerts" {
    start_alert_capture
    publish_entity "${TEST_UNKNOWN}" "https://example.com/no/such/Type"
    echo "# published ${TEST_UNKNOWN}" >&3

    # No shape targets this class. Give the pipeline the same budget the
    # positive test needs to produce an alert, then assert nothing appeared --
    # validating an untargeted entity would mean targetClass is not being
    # honoured.
    sleep 30
    stop_alert_capture
    run grep -c "${TEST_UNKNOWN}" ${ALERTS_OUT}
    echo "# alerts for unconstrained entity: ${output}" >&3
    [ "${output}" = "0" ]
}
