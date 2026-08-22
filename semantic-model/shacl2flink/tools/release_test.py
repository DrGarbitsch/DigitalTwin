#!/usr/bin/env python3
#
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

"""
Release test for the SHACL/SPARQL validation pipeline.

Not part of CI. Run it against a live cluster before a release, like
tools/loadgen.py. It creates its own entity family under unique UUID-based
ids (no collision with anything already on the cluster), drives it through
Scorpio so the full path is exercised (Scorpio -> Debezium -> bridge ->
Kafka -> Flink -> Alerta), and checks:

  * SPARQL rules      -- StateOnCutterShape, StateOnFilterShape,
                         FilterStrengthShape, StateValueShape: each must raise
                         on its trigger and retract on recovery.
  * SHACL checks      -- ClassConstraint (relationship to a wrong-class
                         entity), CountConstraint.
  * Count churn       -- many delete/insert cycles of the same [1,1]
                         relationship; count 0 and count 1 must both be
                         reported correctly and "Found 2" must never appear
                         in the verdict history.
  * Event time        -- observedAt governs, not arrival time: a newer-2024
                         value beats an older-2024 one regardless of arrival
                         order; a stale re-send does not overwrite; a delete
                         carries the timestamp of the value it deletes (so a
                         same-timestamp re-creation wins by arrival order);
                         once a 2026 value is in, no 2024 write can win again.
  * TTL survival      -- the tool reads the deployed table.exec.state.ttl
                         from the shacl-validation BeamSqlStatementSet and,
                         after the family has been idle for 3x that TTL,
                         re-runs the triggers. The spec is that validation
                         still works; if state expiry has killed the joins,
                         the tool reports exactly which operators swallow the
                         records (see below) instead of a bare failure.
  * Plan statistics   -- before and after every trigger the tool snapshots
                         the running job's per-vertex read/write counters via
                         the Flink REST API into a JSONL file, together with
                         the compiled plan (DAG + operator descriptions).
                         For every failed check it prints the operators that
                         received input but emitted nothing, so an unpinned
                         join or aggregate is visible immediately.

Requirements: kubectl access to the cluster (namespace iff by default) and
the usual local ingress names (ngsild.local, keycloak.local, alerta.local).
The Flink REST API is reached on --flink-rest (default http://localhost:8081)
and falls back to kubectl exec into the jobmanager pod.

Usage:
    python3 tools/release_test.py                      # full run (~3xTTL + 30 min)
    python3 tools/release_test.py --phase fresh        # only the t=0 checks
    python3 tools/release_test.py --phase ttl          # create, idle 3xTTL, retest
    python3 tools/release_test.py --idle-factor 1      # shorten the idle wait
    python3 tools/release_test.py --keep               # leave the family behind
    python3 tools/release_test.py --teardown --run-id ab12cd34
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

CONTEXT = 'https://industryfusion.github.io/contexts/staging/example/v0.2/context.jsonld'
NGSILD = 'http://ngsild.local/ngsi-ld/v1'
KEYCLOAK = 'http://keycloak.local/auth/realms'
ALERTA = 'http://alerta.local/api'

ENT = 'https://industryfusion.github.io/contexts/example/v0/base_entities'
KNOW = 'https://industryfusion.github.io/contexts/example/v0/base_knowledge'
MATERIAL = 'https://industryfusion.github.io/contexts/ontology/v0/material/EN_1.4301'

RESULTS = []


def log(msg):
    print(f"[{datetime.datetime.now(datetime.timezone.utc):%H:%M:%S}] {msg}", flush=True)


def record(phase, name, ok, detail=''):
    RESULTS.append({'phase': phase, 'name': name, 'ok': ok, 'detail': detail})
    log(f"   {'PASS' if ok else 'FAIL'}  {phase}/{name}  {detail}")


# --------------------------------------------------------------------------- plumbing

def _req(url, method='GET', token=None, body=None, ctype='application/ld+json'):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    if data:
        req.add_header('Content-Type', ctype)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()
    except Exception as err:
        return 0, str(err).encode()


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


def get_token(namespace, user, client_id, password):
    if password is None:
        password = sh(f"kubectl -n {namespace} get secret/credential-iff-realm-user-iff"
                      " -o jsonpath='{.data.password}' | base64 -d")
    form = urllib.parse.urlencode({'client_id': client_id, 'username': user,
                                   'password': password,
                                   'grant_type': 'password'}).encode()
    req = urllib.request.Request(f'{KEYCLOAK}/{namespace}/protocol/openid-connect/token',
                                 data=form, method='POST')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())['access_token']


def discover_ttl(namespace):
    """Read table.exec.state.ttl from the deployed statementset (seconds)."""
    raw = sh(f"kubectl -n {namespace} get beamsqlstatementsets shacl-validation -o json")
    for setting in json.loads(raw)['spec']['sqlsettings']:
        for key, val in setting.items():
            if key == 'table.exec.state.ttl':
                m = re.match(r'(\d+)\s*(s|min|h)?', str(val))
                mult = {'s': 1, 'min': 60, 'h': 3600}.get(m.group(2) or 's', 1)
                return int(m.group(1)) * mult
    return None


def alerta_key(namespace):
    return sh(f"kubectl -n {namespace} get secret alerta"
              " -o jsonpath='{.data.alerta-admin-key}' | base64 -d")


# --------------------------------------------------------------------------- flink stats

class PlanStats:
    """Per-vertex read/write counters + compiled plan, snapshotted to JSONL."""

    def __init__(self, namespace, rest, statsfile):
        self.namespace = namespace
        self.rest = rest
        self.statsfile = statsfile
        self.jid = None
        self.snaps = []

    def _get(self, path):
        try:
            with urllib.request.urlopen(self.rest + path, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception:
            pod = sh(f"kubectl -n {self.namespace} get pods --no-headers"
                     " -o custom-columns=:metadata.name | grep -m1 -E 'flink-deployment-[0-9a-f]'")
            out = sh(f"kubectl -n {self.namespace} exec {pod} -c flink-main-container --"
                     f" curl -s http://localhost:8081{path}")
            return json.loads(out) if out else {}

    def _find_job(self):
        for job in self._get('/jobs/overview').get('jobs', []):
            if job['state'] == 'RUNNING' and 'shacl' in job['name']:
                return job['jid']
        return None

    def snap(self, label):
        jid = self._find_job()
        if not jid:
            log(f"   stats: no running shacl job for snapshot '{label}'")
            return
        if jid != self.jid:
            self.jid = jid
            plan = self._get(f'/jobs/{jid}/plan')
            with open(self.statsfile.replace('.jsonl', f'.plan-{jid[:8]}.json'), 'w') as f:
                json.dump(plan, f)
        job = self._get(f'/jobs/{jid}')
        counters = {v['name']: [v['metrics']['read-records'], v['metrics']['write-records']]
                    for v in job.get('vertices', [])}
        entry = {'label': label, 'time': time.time(), 'jid': jid, 'counters': counters}
        self.snaps.append(entry)
        with open(self.statsfile, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def swallowers(self, before_label, after_label):
        """Operators that received records between two snapshots but emitted none."""
        before = next((s for s in self.snaps if s['label'] == before_label), None)
        after = next((s for s in reversed(self.snaps) if s['label'] == after_label), None)
        if not before or not after or before['jid'] != after['jid']:
            return []
        out = []
        for name, (rin, rout) in after['counters'].items():
            bin_, bout = before['counters'].get(name, [0, 0])
            din, dout = rin - bin_, rout - bout
            if din > 0 and dout == 0 and 'Sink' not in name and 'Committer' not in name:
                out.append((din, name))
        return sorted(out, reverse=True)


# --------------------------------------------------------------------------- family

class Family:
    """A private entity family mirroring semantic-model/kms/model-instance.jsonld."""

    def __init__(self, run):
        self.run = run
        self.cutter = f'urn:rt:{run}:cutter'
        self.filter = f'urn:rt:{run}:filter'
        self.workpiece = f'urn:rt:{run}:workpiece'
        self.cartridge = f'urn:rt:{run}:cartridge'
        # a second cutter/filter pair reserved for the event-time check: its
        # hasStrength timeline must stay pristine 2024, and the other checks
        # restore with wall-clock (2026) observedAt -- which would correctly
        # lock every later 2024 write out and void the test.
        self.cutter2 = f'urn:rt:{run}:cutter2'
        self.filter2 = f'urn:rt:{run}:filter2'
        self.all = [self.cutter, self.filter, self.cutter2, self.filter2,
                    self.workpiece, self.cartridge]

    def entities(self):
        return [
            {'@context': CONTEXT, 'id': self.cutter, 'type': 'iffBaseEntities:Cutter',
             'iffBaseEntities:hasState': [{
                 'type': 'Property', 'value': {'@id': 'base:state_PROCESSING'},
                 'iffBaseEntities:hasXXXWorkpiece': {
                     'type': 'Relationship', 'object': self.workpiece}}],
             'iffBaseEntities:hasFilter': [{
                 'type': 'Relationship', 'object': self.filter,
                 'iffBaseEntities:hasTrust': [{
                     'type': 'Property', 'value': 2.1,
                     'iffBaseEntities:hasOutWorkpiecexx': {
                         'type': 'Property', 'value': 2.0, 'datasetId': 'urn:index:1'}}]}],
             'iffBaseEntities:hasInWorkpiece': [{
                 'type': 'Relationship', 'object': self.workpiece}],
             'iffBaseEntities:hasList': {'type': 'ListProperty', 'valueList': []},
             'iffBaseEntities:hasJSON': {'type': 'JsonProperty', 'json': {}}},
            {'@context': CONTEXT, 'id': self.filter, 'type': 'iffBaseEntities:Filter',
             'iffBaseEntities:hasState': [{'type': 'Property',
                                           'value': {'@id': 'base:state_ON'}}],
             'iffBaseEntities:hasCartridge': [{'type': 'Relationship',
                                               'object': self.cartridge}],
             'iffBaseEntities:hasStrength': [{'type': 'Property', 'value': 0.6,
                                              'observedAt': '2024-03-01T00:00:00.000Z'}]},
            {'@context': CONTEXT, 'id': self.cutter2, 'type': 'iffBaseEntities:Cutter',
             'iffBaseEntities:hasState': [{
                 'type': 'Property', 'value': {'@id': 'base:state_PROCESSING'},
                 'iffBaseEntities:hasXXXWorkpiece': {
                     'type': 'Relationship', 'object': self.workpiece}}],
             'iffBaseEntities:hasFilter': [{
                 'type': 'Relationship', 'object': self.filter2,
                 'iffBaseEntities:hasTrust': [{
                     'type': 'Property', 'value': 2.1,
                     'iffBaseEntities:hasOutWorkpiecexx': {
                         'type': 'Property', 'value': 2.0, 'datasetId': 'urn:index:1'}}]}],
             'iffBaseEntities:hasInWorkpiece': [{
                 'type': 'Relationship', 'object': self.workpiece}],
             'iffBaseEntities:hasList': {'type': 'ListProperty', 'valueList': []},
             'iffBaseEntities:hasJSON': {'type': 'JsonProperty', 'json': {}}},
            {'@context': CONTEXT, 'id': self.filter2, 'type': 'iffBaseEntities:Filter',
             'iffBaseEntities:hasState': [{'type': 'Property',
                                           'value': {'@id': 'base:state_ON'}}],
             'iffBaseEntities:hasCartridge': [{'type': 'Relationship',
                                               'object': self.cartridge}],
             'iffBaseEntities:hasStrength': [{'type': 'Property', 'value': 0.6,
                                              'observedAt': '2024-03-01T00:00:00.000Z'}]},
            {'@context': CONTEXT, 'id': self.workpiece, 'type': 'iffBaseEntities:Workpiece',
             'iffBaseEntities:hasMaterial': [{'type': 'Property',
                                              'value': {'@id': MATERIAL}}],
             'iffBaseEntities:hasHeight': [{'type': 'Property', 'value': 5}],
             'iffBaseEntities:hasLength': [{'type': 'Property', 'value': 100}],
             'iffBaseEntities:hasWidth': [{'type': 'Property', 'value': 100}]},
            {'@context': CONTEXT, 'id': self.cartridge,
             'type': 'iffBaseEntities:FilterCartridge',
             'iffBaseEntities:isUsedFrom': [{'type': 'Property',
                                             'value': '2024-02-27 13:54:55.4'}],
             'iffBaseEntities:isUsedUntil': [{'type': 'Property',
                                              'value': '2024-02-27 13:54:55.4'}]},
        ]


def upsert(token, entities):
    return _req(f'{NGSILD}/entityOperations/upsert', 'POST', token, entities)


def post_attr(token, eid, short, fragment):
    body = {'@context': CONTEXT, f'iffBaseEntities:{short}': fragment}
    code, _ = _req(f'{NGSILD}/entities/{eid}/attrs', 'POST', token, body)
    return code


def del_attr(token, eid, short):
    enc = urllib.parse.quote(f'{ENT}/{short}', safe='')
    code, _ = _req(f'{NGSILD}/entities/{eid}/attrs/{enc}', 'DELETE', token)
    return code


def del_entity(token, eid):
    code, _ = _req(f'{NGSILD}/entities/{eid}', 'DELETE', token)
    return code


def set_state(token, eid, state):
    return post_attr(token, eid, 'hasState',
                     {'type': 'Property', 'value': {'@id': f'{KNOW}/{state}'}})


def set_strength(token, eid, value, observed_at):
    return post_attr(token, eid, 'hasStrength',
                     {'type': 'Property', 'value': value, 'observedAt': observed_at})


def now_observed_at():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


# --------------------------------------------------------------------------- alerta

def alerta_alerts(key, resource):
    url = f'{ALERTA}/alerts?' + urllib.parse.urlencode({'resource': resource})
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Key {key}')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get('alerts', [])
    except Exception:
        return []


def wait_alert(key, resource, event_frag, want, timeout=150):
    """want: 'open' (any non-ok severity) or 'gone' (closed or absent).

    event_frag may be a string or a list of strings; every fragment must
    occur in the event name. A single component name is often ambiguous --
    e.g. a filter entity without the optional hasXXXWorkpiece sub-attribute
    carries a permanent CountConstraint warning, which must not shadow the
    hasCartridge count under test."""
    frags = [event_frag] if isinstance(event_frag, str) else list(event_frag)
    deadline = time.time() + timeout
    last = 'absent'
    while time.time() < deadline:
        hits = [a for a in alerta_alerts(key, resource)
                if all(f in a['event'] for f in frags)]
        if not hits:
            last = 'absent'
            if want == 'gone':
                return True, last
        else:
            a = sorted(hits, key=lambda x: x['lastReceiveTime'])[-1]
            last = f"{a['status']}/{a['severity']}"
            if want == 'open' and a['status'] == 'open' and a['severity'] != 'ok':
                return True, f"{last}: {a.get('text', '')[:200]}"
            if want == 'gone' and a['status'] != 'open':
                return True, last
        time.sleep(6)
    return False, last


# --------------------------------------------------------------------------- checks

def run_check(stats, key, name, phase, resource, event_frag, trigger, restore):
    """trigger() then expect the alert open; restore() then expect it gone."""
    stats.snap(f'{phase}:{name}:before')
    trigger()
    ok, detail = wait_alert(key, resource, event_frag, 'open')
    stats.snap(f'{phase}:{name}:after')
    record(phase, name, ok, detail)
    if not ok:
        for din, opname in stats.swallowers(f'{phase}:{name}:before',
                                            f'{phase}:{name}:after')[:6]:
            log(f"      swallowed {din:>4} records: {opname[:110]}")
    restore()
    ok2, detail2 = wait_alert(key, resource, event_frag, 'gone')
    record(phase, name + '.retract', ok2, detail2)
    return ok and ok2


def sparql_checks(stats, token, key, fam, phase):
    run_check(stats, key, 'StateOnCutterShape', phase, fam.cutter,
              'StateOnCutterShape',
              lambda: set_state(token, fam.filter, 'state_OFF'),
              lambda: set_state(token, fam.filter, 'state_ON'))
    run_check(stats, key, 'StateOnFilterShape', phase, fam.filter,
              'StateOnFilterShape',
              lambda: set_state(token, fam.cutter, 'state_ON'),
              lambda: set_state(token, fam.cutter, 'state_PROCESSING'))
    run_check(stats, key, 'FilterStrengthShape', phase, fam.filter,
              'FilterStrengthShape',
              lambda: set_strength(token, fam.filter, 0.3, now_observed_at()),
              lambda: set_strength(token, fam.filter, 0.6, now_observed_at()))
    run_check(stats, key, 'StateValueShape', phase, fam.cutter,
              'StateValueShape',
              lambda: set_state(token, fam.cutter, 'state_CLEANING'),
              lambda: set_state(token, fam.cutter, 'state_PROCESSING'))


def class_check(stats, token, key, fam, phase):
    run_check(stats, key, 'ClassConstraint', phase, fam.cutter,
              ['ClassConstraintComponent', 'hasFilter'],
              lambda: post_attr(token, fam.cutter, 'hasFilter',
                                [{'type': 'Relationship', 'object': fam.workpiece}]),
              lambda: post_attr(token, fam.cutter, 'hasFilter',
                                [{'type': 'Relationship', 'object': fam.filter,
                                  'iffBaseEntities:hasTrust': [{
                                      'type': 'Property', 'value': 2.1,
                                      'iffBaseEntities:hasOutWorkpiecexx': {
                                          'type': 'Property', 'value': 2.0,
                                          'datasetId': 'urn:index:1'}}]}]))


def count_churn(stats, token, key, fam, namespace, phase, cycles=5):
    """Delete/create the same [1,1] relationship repeatedly; count must only
    ever be 0 (violation) or 1 (ok), never 2."""
    stats.snap(f'{phase}:churn:before')
    for i in range(cycles):
        del_attr(token, fam.filter, 'hasCartridge')
        time.sleep(4)
        post_attr(token, fam.filter, 'hasCartridge',
                  [{'type': 'Relationship', 'object': fam.cartridge}])
        time.sleep(4)
    del_attr(token, fam.filter, 'hasCartridge')
    ok0, det0 = wait_alert(key, fam.filter,
                           ['CountConstraintComponent', 'hasCartridge'], 'open')
    found0 = 'Found 0' in det0
    record(phase, 'churn.count0', ok0 and found0, det0)
    post_attr(token, fam.filter, 'hasCartridge',
              [{'type': 'Relationship', 'object': fam.cartridge}])
    ok1, det1 = wait_alert(key, fam.filter,
                           ['CountConstraintComponent', 'hasCartridge'], 'gone')
    record(phase, 'churn.count1', ok1, det1)
    stats.snap(f'{phase}:churn:after')

    # audit the full verdict history in the trigger topic: "Found 2" must not exist
    hist = sh("kubectl -n %s exec my-cluster-nodes-0 -- sh -c \"KAFKA_HEAP_OPTS='-Xmx256M'"
              " bin/kafka-console-consumer.sh --bootstrap-server localhost:9092"
              " --topic iff.ngsild.flink.constraint_trigger_table --from-beginning"
              " --max-messages 3000 --timeout-ms 25000\" 2>/dev/null" % namespace)
    counts = set()
    for line in hist.splitlines():
        if fam.filter in line and 'hasCartridge' in line:
            counts.update(re.findall(r'Found (\d+)', line))
    bad = {c for c in counts if int(c) > 1}
    record(phase, 'churn.never2', not bad,
           f"counts seen in history: {sorted(counts) or 'none'}")


def event_time_check(stats, token, key, fam, phase):
    """observedAt governs the outcome, arrival order only breaks exact ties.

    Runs on the dedicated cutter2/filter2 pair: the other checks restore
    hasStrength with wall-clock observedAt, and a single 2026 record in this
    timeline legitimately locks out every later 2024 write."""
    ev = 'FilterStrengthShape'
    flt = fam.filter2
    stats.snap(f'{phase}:eventtime:before')

    set_strength(token, flt, 0.55, '2024-03-01T00:00:00.000Z')
    ok, det = wait_alert(key, flt, ev, 'gone')
    record(phase, 'et.baseline-2024-ok', ok, det)

    set_strength(token, flt, 0.3, '2024-03-01T00:00:01.000Z')
    ok, det = wait_alert(key, flt, ev, 'open')
    record(phase, 'et.newer-2024-wins', ok, det)

    # stale write: older event time must NOT overwrite the newer value
    set_strength(token, flt, 0.55, '2024-03-01T00:00:00.000Z')
    time.sleep(90)
    hits = sorted((a for a in alerta_alerts(key, flt) if ev in a['event']),
                  key=lambda a: a['lastReceiveTime'])
    still = bool(hits) and hits[-1]['status'] == 'open'
    record(phase, 'et.stale-ignored', still,
           hits[-1]['status'] + '/' + hits[-1]['severity'] if hits else 'absent')

    # delete carries the timestamp of the value it deletes (00:00:01)
    del_attr(token, flt, 'hasStrength')
    ok, det = wait_alert(key, flt, ev, 'gone')
    record(phase, 'et.delete-retracts', ok, det)

    # same event time as the delete -> tie, later arrival (the value) wins
    set_strength(token, flt, 0.3, '2024-03-01T00:00:01.000Z')
    ok, det = wait_alert(key, flt, ev, 'open')
    record(phase, 'et.tie-recreate-wins', ok, det)

    # 2026 beats 2024
    set_strength(token, flt, 0.9, now_observed_at())
    ok, det = wait_alert(key, flt, ev, 'gone')
    record(phase, 'et.2026-wins', ok, det)

    # after 2026, no 2024 write may change the result again
    set_strength(token, flt, 0.3, '2024-03-01T00:00:02.000Z')
    time.sleep(90)
    hits = sorted((a for a in alerta_alerts(key, flt) if ev in a['event']),
                  key=lambda a: a['lastReceiveTime'])
    gone = not hits or hits[-1]['status'] != 'open'
    record(phase, 'et.2024-cannot-return', gone,
           hits[-1]['status'] + '/' + hits[-1]['severity'] if hits else 'absent')
    set_strength(token, flt, 0.6, now_observed_at())
    stats.snap(f'{phase}:eventtime:after')


def reset_family(token, fam):
    """Force complete re-publication: delete + recreate one attribute per
    entity (the bridge only re-emits the entity record when an attribute is
    inserted or deleted), then re-upsert the full family."""
    del_attr(token, fam.cutter, 'hasInWorkpiece')
    del_attr(token, fam.cutter2, 'hasInWorkpiece')
    del_attr(token, fam.filter, 'hasCartridge')
    del_attr(token, fam.filter2, 'hasCartridge')
    del_attr(token, fam.workpiece, 'hasHeight')
    del_attr(token, fam.cartridge, 'isUsedFrom')
    time.sleep(3)
    upsert(token, fam.entities())


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--namespace', default='iff')
    ap.add_argument('--user', default='realm_user')
    ap.add_argument('--client-id', default='scorpio')
    ap.add_argument('--password', default=None)
    ap.add_argument('--flink-rest', default='http://localhost:8081')
    ap.add_argument('--phase', choices=['all', 'fresh', 'ttl'], default='all')
    ap.add_argument('--idle-factor', type=float, default=3.0,
                    help='idle for this multiple of the deployed TTL (default 3)')
    ap.add_argument('--settle', type=float, default=90.0,
                    help='seconds to wait after family creation')
    ap.add_argument('--run-id', default=None, help='reuse an existing family')
    ap.add_argument('--keep', action='store_true', help='do not delete the family')
    ap.add_argument('--teardown', action='store_true')
    ap.add_argument('--stats-file', default=None)
    args = ap.parse_args()

    run = args.run_id or uuid.uuid4().hex[:8]
    fam = Family(run)
    token = get_token(args.namespace, args.user, args.client_id, args.password)
    key = alerta_key(args.namespace)

    if args.teardown:
        for eid in fam.all:
            log(f"delete {eid} -> {del_entity(token, eid)}")
        return 0

    ttl = discover_ttl(args.namespace)
    statsfile = args.stats_file or f'/tmp/release_test.{run}.stats.jsonl'
    stats = PlanStats(args.namespace, args.flink_rest, statsfile)
    log(f"run id {run}, deployed table.exec.state.ttl = {ttl} s, stats -> {statsfile}")
    if ttl is None:
        log('could not discover the TTL; aborting')
        return 2

    log('creating family ' + ', '.join(fam.all))
    code, body = upsert(token, fam.entities())
    if code not in (200, 201, 204, 207):
        log(f'family creation failed: {code} {body[:200]}')
        return 2
    log(f'settling {args.settle:.0f}s')
    time.sleep(args.settle)
    stats.snap('baseline')
    last_write = time.time()

    if args.phase in ('all', 'fresh'):
        log('=== phase FRESH: full checks right after creation ===')
        sparql_checks(stats, token, key, fam, 'fresh')
        class_check(stats, token, key, fam, 'fresh')
        count_churn(stats, token, key, fam, args.namespace, 'fresh')
        event_time_check(stats, token, key, fam, 'fresh')
        last_write = time.time()

    if args.phase in ('all', 'ttl'):
        idle = ttl * args.idle_factor
        wake = last_write + idle
        log(f"=== phase TTL: idling {idle:.0f}s ({args.idle_factor:.1f} x {ttl}s TTL) ===")
        while time.time() < wake:
            time.sleep(min(60, max(1, wake - time.time())))
        log(f"idle over ({idle:.0f}s since last family write); re-running triggers")
        stats.snap('postttl:baseline')
        sparql_checks(stats, token, key, fam, 'postttl')
        class_check(stats, token, key, fam, 'postttl')

        failed = [r for r in RESULTS if r['phase'] == 'postttl' and not r['ok']]
        if failed:
            log(f"=== phase RESET: {len(failed)} post-TTL failures; full re-publication ===")
            reset_family(token, fam)
            time.sleep(45)
            sparql_checks(stats, token, key, fam, 'reset')

    if not args.keep:
        for eid in fam.all:
            del_entity(token, eid)
        log('family deleted (use --keep to retain it)')

    log('=== RESULTS ===')
    fails = 0
    for r in RESULTS:
        mark = 'PASS' if r['ok'] else 'FAIL'
        fails += 0 if r['ok'] else 1
        log(f"  {mark}  {r['phase']:>8}/{r['name']:<28} {r['detail'][:90]}")
    log(f"{len(RESULTS) - fails}/{len(RESULTS)} checks passed; stats in {statsfile}")
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
