#!/bin/bash
# Copyright (c) 2026 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Deleting an entity clears its alert only while the state that produced the
# verdict is still there. Once table.exec.state.ttl has expired it, the
# operator no longer knows it ever emitted triggered=true, so the delete
# produces no retraction: constraint_trigger_table keeps the stale verdict --
# nothing recomputes a verdict for an entity that does not exist -- and alerta
# holds the alert for good.
#
# This is not a property any unit test can hold, and waiting out the deployed
# hour makes it painful to check by hand, so the script shrinks the ttl and
# runs the same cycle on both sides of it. The failure follows the setting:
#
#     ttl=300s, delete after  60s  -> alerts clear   (inside the window)
#     ttl=300s, delete after 420s  -> alerts stay    (outside it)
#
# which is what makes this the ttl rather than something that merely takes a
# long time. The original ttl is restored on the way out, including on failure.
#
#   usage: tools/ttl_retraction_repro.sh [namespace]
#
# Requires kubectl against a cluster with shacl-validation deployed, and jq.
set -u
NAMESPACE=${1:-iff}
STATEMENTSET=shacl-validation
PROBE_TTL="300 s"
INSIDE=60      # comfortably inside PROBE_TTL
OUTSIDE=420    # comfortably outside it
SETTLE=90

ENTITIES_TOPIC=iff.ngsild.entities
ATTRIBUTES_TOPIC=iff.ngsild.attributes
KAFKA_BOOTSTRAP=my-cluster-kafka-bootstrap:9092
BASE=https://industryfusion.github.io/contexts/example/v0/base_entities/
KNOW=https://industryfusion.github.io/contexts/example/v0/base_knowledge/

ORIGINAL_TTL=

# Runs from the EXIT trap, so shellcheck cannot see it being called.
# shellcheck disable=SC2317
cleanup() {
    if [ -n "${ORIGINAL_TTL}" ]; then
        echo "-- restoring table.exec.state.ttl to ${ORIGINAL_TTL} --"
        set_ttl "${ORIGINAL_TTL}"
        redeploy >/dev/null || echo "   WARNING: restore redeploy failed, check ${STATEMENTSET}"
    fi
}
trap cleanup EXIT

alerta_key() {
    kubectl -n "${NAMESPACE}" get secret alerta \
        -o jsonpath='{.data.alerta-admin-key}' | base64 -d
}

# Alerts open against any resource carrying the run's suffix.
alerts_for() {
    kubectl -n "${NAMESPACE}" exec deploy/alerta-bridge -- sh -c \
        "curl -s -H 'Authorization: Key $(alerta_key)' 'http://alerta:8080/api/alerts?status=open'" \
        2>/dev/null | jq --arg s "$1" '[.alerts[] | select(.resource | test($s))] | length'
}

get_ttl() {
    kubectl -n "${NAMESPACE}" get beamsqlstatementsets "${STATEMENTSET}" \
        -o jsonpath='{.spec.sqlsettings}' \
        | jq -r '[.[] | select(has("table.exec.state.ttl"))][0]["table.exec.state.ttl"] // "unset"'
}

# sqlsettings is a list of single-key objects, so the setting is replaced in
# place when present and appended when not. Patched from a file because the
# json is far too awkward to pass through a shell argument intact.
set_ttl() {
    local patch
    patch=$(mktemp)
    kubectl -n "${NAMESPACE}" get beamsqlstatementsets "${STATEMENTSET}" \
        -o jsonpath='{.spec.sqlsettings}' \
        | jq --arg t "$1" 'map(if has("table.exec.state.ttl")
                               then {"table.exec.state.ttl": $t} else . end)
                           | if any(.[]; has("table.exec.state.ttl")) then .
                             else . + [{"table.exec.state.ttl": $t}] end
                           | {"spec": {"sqlsettings": .}}' > "${patch}"
    kubectl -n "${NAMESPACE}" patch beamsqlstatementsets "${STATEMENTSET}" \
        --type=merge --patch-file "${patch}" >/dev/null
    rm -f "${patch}"
}

# Restart the job and wait for the operator to report a new one RUNNING.
redeploy() {
    local old new st
    old=$(kubectl -n "${NAMESPACE}" get beamsqlstatementsets "${STATEMENTSET}" \
            -o jsonpath='{.status.job_id}')
    kubectl -n "${NAMESPACE}" annotate beamsqlstatementset "${STATEMENTSET}" \
        ttl-repro="$(date +%s)" --overwrite >/dev/null
    for _ in $(seq 1 40); do
        st=$(kubectl -n "${NAMESPACE}" get beamsqlstatementsets "${STATEMENTSET}" \
                -o jsonpath='{.status.state}' 2>/dev/null)
        new=$(kubectl -n "${NAMESPACE}" get beamsqlstatementsets "${STATEMENTSET}" \
                -o jsonpath='{.status.job_id}' 2>/dev/null)
        if [ -n "${new}" ] && [ "${new}" != "${old}" ] && [ "${st}" = "RUNNING" ]; then
            echo "${new}"; return 0
        fi
        sleep 15
    done
    return 1
}

# Publish one entity plus one violating attribute, or their deletions. The
# records go straight to kafka so the reproduction does not depend on scorpio.
publish() {
    local suffix=$1 deleted=$2
    kubectl -n "${NAMESPACE}" exec -i deploy/debezium-bridge -- node -e '
const {Kafka} = require("/opt/node_modules/kafkajs");
const i = JSON.parse(require("fs").readFileSync("/dev/stdin", "utf8"));
const p = new Kafka({brokers: [i.broker], clientId: "ttl-repro"}).producer();
(async () => {
  await p.connect();
  await p.sendBatch({topicMessages: [
    {topic: i.entitiesTopic,   messages: i.entities.map(r => ({key: r.key, value: JSON.stringify(r.value)}))},
    {topic: i.attributesTopic, messages: i.attributes.map(r => ({key: r.key, value: JSON.stringify(r.value)}))}
  ]});
  await p.disconnect();
})().catch(e => { console.error(e.message); process.exit(1); });' <<EOF
{
  "broker": "${KAFKA_BOOTSTRAP}",
  "entitiesTopic": "${ENTITIES_TOPIC}",
  "attributesTopic": "${ATTRIBUTES_TOPIC}",
  "entities": [
    {"key": "urn:ttlrepro${suffix}:1",
     "value": {"id": "urn:ttlrepro${suffix}:1", "type": "${BASE}Machine", "deleted": ${deleted}}}
  ],
  "attributes": [
    {"key": "urn:ttlrepro${suffix}:1",
     "value": {"id": "urn:ttlrepro${suffix}:1\\\\${BASE}hasState",
               "parentId": null, "entityId": "urn:ttlrepro${suffix}:1",
               "name": "${BASE}hasState", "type": "https://uri.etsi.org/ngsi-ld/Property",
               "datasetId": "@none", "nodeType": "@id", "attributeValue": "${KNOW}state_ON",
               "valueType": null, "unitCode": null, "lang": null,
               "deleted": ${deleted}, "synced": true}}
  ]
}
EOF
}

# cycle <suffix> <soak-seconds> <expected pass|fail>
cycle() {
    local suffix=$1 soak=$2 expect=$3 created after
    echo "-- cycle ${suffix}: delete after ${soak}s (expect ${expect}) --"
    publish "${suffix}" false
    sleep "${SETTLE}"
    created=$(alerts_for "ttlrepro${suffix}")
    echo "   after create: ${created} alert(s)"
    if [ "${created}" -lt 1 ]; then
        echo "   INCONCLUSIVE: the entity raised no alert to begin with"
        return 2
    fi
    sleep "${soak}"
    publish "${suffix}" true
    sleep "${SETTLE}"
    after=$(alerts_for "ttlrepro${suffix}")
    echo "   after delete: ${after} alert(s)"
    [ "${after}" -eq 0 ] && echo "   -> cleared" || echo "   -> STAYED OPEN"
    [ "${after}" -eq 0 ] && return 0 || return 1
}

echo "=== state-ttl retraction reproduction  $(date -u +%H:%M:%SZ) ==="
ORIGINAL_TTL=$(get_ttl)
echo "deployed table.exec.state.ttl: ${ORIGINAL_TTL}"
echo "shrinking it to ${PROBE_TTL} so both sides fit in a coffee break"
set_ttl "${PROBE_TTL}"
if ! JOB=$(redeploy); then
    echo "FAILED to redeploy with the probe ttl"
    exit 1
fi
echo "job ${JOB} running"
sleep 60

cycle inside "${INSIDE}" pass;  inside_rc=$?
cycle outside "${OUTSIDE}" fail; outside_rc=$?

echo
if [ "${inside_rc}" -eq 0 ] && [ "${outside_rc}" -eq 1 ]; then
    echo "REPRODUCED: the same delete clears inside the ttl window and does not"
    echo "            clear outside it. The retraction is lost with the state."
    rc=0
elif [ "${inside_rc}" -eq 0 ] && [ "${outside_rc}" -eq 0 ]; then
    echo "NOT REPRODUCED: both cycles cleared -- retraction survives ttl expiry."
    rc=0
else
    echo "INCONCLUSIVE: inside=${inside_rc} outside=${outside_rc}"
    rc=1
fi
echo "=== done $(date -u +%H:%M:%SZ) ==="
exit "${rc}"
