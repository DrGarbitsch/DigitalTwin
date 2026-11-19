#!/usr/bin/env bats
#
# Copyright (c) 2026 IndustryFusion Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Which K8s e2e shards a pull request runs, from the paths it changes.

bats_require_minimum_version 1.5.0

SCRIPT="${BATS_TEST_DIRNAME}/../../.github/scripts/e2e-shards.sh"
SUITES_DIR="${BATS_TEST_DIRNAME}/../bats"

select_for() {
    printf '%s\n' "$@" | bash "${SCRIPT}" select
}

@test "every suite directory belongs to exactly one shard" {
    assigned=""
    for shard in $(bash "${SCRIPT}" list); do
        assigned="${assigned} $(bash "${SCRIPT}" suites "${shard}")"
    done
    for dir in "${SUITES_DIR}"/test-*/; do
        name=$(basename "${dir}")
        count=$(echo "${assigned}" | tr ' ' '\n' | grep -cx "${name}" || true)
        [ "${count}" -eq 1 ] || { echo "${name} is in ${count} shards"; false; }
    done
}

@test "every suite a shard names exists" {
    for shard in $(bash "${SCRIPT}" list); do
        for suite in $(bash "${SCRIPT}" suites "${shard}"); do
            [ -d "${SUITES_DIR}/${suite}" ] || { echo "${shard}: ${suite} missing"; false; }
        done
    done
}

@test "an agent change runs only the device shard" {
    run select_for NgsildAgent/lib/utils.js NgsildAgent/test/foo.js
    [ "${output}" = '["device"]' ]
}

@test "a shacl2flink change runs only the flink shard" {
    run select_for semantic-model/shacl2flink/create_sql_checks_from_shacl.py
    [ "${output}" = '["flink"]' ]
}

@test "a bridge change runs every shard the bridges are part of" {
    run select_for KafkaBridge/lib/mqttBridge.js
    [ "${output}" = '["device","broker","flink"]' ]
}

@test "a scorpio chart change runs broker and flink" {
    run select_for helm/charts/scorpio/values.yaml
    [ "${output}" = '["broker","flink"]' ]
}

@test "a change to a suite runs the shard of that suite" {
    run select_for test/bats/test-scorpio/test-scorpio-mergepatch.bats
    [ "${output}" = '["broker"]' ]
    run select_for test/bats/test-core-sql-services/test-alerta-bulk-filter.bats
    [ "${output}" = '["flink"]' ]
}

@test "shared platform files run every shard" {
    for path in .env docker-compose.yml helm/helmfile.yaml helm/values.yaml.gotmpl \
                helm/install_operators.sh helm/charts/keycloak/values.yaml \
                test/install-platform.sh test/bats/lib/utils.bash Keycloak/Dockerfile; do
        run select_for "${path}"
        [ "${output}" = '["device","broker","flink"]' ] || { echo "${path}: ${output}"; false; }
    done
}

@test "paths the cluster never runs select no shard" {
    run select_for semantic-model/SemForge-SDK/semforge/cli.py semantic-model/opcua/nodeset2owl.py \
        README.md openspec/specs/x/spec.md test/bats-unit/e2e-shards.bats DebeziumAdapter/pom.xml
    [ "${output}" = '[]' ]
}

@test "scripts of the other tests below test/ are not platform scripts" {
    run select_for test/opcua-chain/run.sh test/debezium-snapshot-memory/test.sh
    [ "${output}" = '[]' ]
}

@test "shards are merged across paths and listed once, in a fixed order" {
    run select_for semantic-model/shacl2flink/Makefile NgsildAgent/x.js FlinkSqlGateway/y NgsildAgent/z.js
    [ "${output}" = '["device","flink"]' ]
}

@test "--all selects every shard regardless of the paths" {
    run bash -c "printf 'README.md\n' | bash '${SCRIPT}' select --all"
    [ "${output}" = '["device","broker","flink"]' ]
}

@test "no changed paths select nothing" {
    run bash -c "printf '' | bash '${SCRIPT}' select"
    [ "${output}" = '[]' ]
}

@test "an unknown shard is an error" {
    run bash "${SCRIPT}" suites nope
    [ "${status}" -ne 0 ]
}
