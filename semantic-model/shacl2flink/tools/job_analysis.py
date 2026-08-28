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
Analyse the RUNNING shacl-validation job. No entities are created, nothing is
written -- it only reads Flink's REST API and the alert topics, so it is safe
against a production cluster.

Why it exists: a validation failure looks the same from Alerta whatever caused
it -- a record lost inside the job, a record the sink never wrote, a record
CoreServices dropped, or a verdict that flips so fast the last one wins
arbitrarily. Those need completely different fixes, and telling them apart
after the fact meant reconstructing plan counters and Kafka offsets by hand.
This says which one it is.

    plan     what the job compiled to: operator mix, mini-batch mode,
             aggregate phase, state pins. The first question after any
             config change is "did I get the plan I asked for".

    watch    snapshot the per-vertex record counters twice and diff them.
             Vertices that take records and emit none are where a changelog
             dies; vertices emitting far more than they take are where one
             amplifies.

    churn    records per (resource, event) in iff.alerts.bulk over a window,
             and the same in iff.alerts. This is the discriminator:

               few records, no 'ok'      -> the retraction was never produced
               'ok' in bulk, not alerts  -> CoreServices dropped it
               thousands of records      -> the verdict is oscillating; the
                                            alert is not stuck, it is being
                                            rewritten faster than it settles

             Measured for reference: a healthy 1.20.4 run emits 9-50 records
             per key for a whole test; a broken 2.3.0 run emitted 9454 and
             66813 for single keys in the same window.

Examples:
    tools/job_analysis.py plan
    tools/job_analysis.py watch --seconds 60
    tools/job_analysis.py churn --minutes 30
    tools/job_analysis.py churn --minutes 30 --resource urn:filter:1
"""

import argparse
import json
import re
import subprocess
import sys
import time


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True,
                          text=True).stdout.strip()


def jobmanager(ns):
    pod = sh(f"kubectl -n {ns} get pods -o name | grep flink-deployment | head -1")
    return pod.split('/')[-1] if pod else None


def rest(ns, pod, path):
    out = sh(f"kubectl -n {ns} exec {pod} -c flink-main-container -- "
             f"curl -s localhost:8081{path}")
    try:
        return json.loads(out)
    except Exception:
        return None


def shacl_job(ns, pod):
    jobs = rest(ns, pod, '/jobs') or {'jobs': []}
    for j in jobs['jobs']:
        if j.get('status') != 'RUNNING':
            continue
        d = rest(ns, pod, f"/jobs/{j['id']}")
        if d and 'shacl' in str(d.get('name', '')):
            return j['id'], d
    return None, None


def counters(detail):
    """{vertex name: (recordsIn, recordsOut)} for every vertex."""
    out = {}
    for v in detail.get('vertices', []):
        m = v.get('metrics', {})
        out[v['name']] = (m.get('read-records') or 0, m.get('write-records') or 0)
    return out


def cmd_plan(args):
    pod = jobmanager(args.namespace)
    jid, detail = shacl_job(args.namespace, pod)
    if not detail:
        print('no RUNNING shacl-validation job found')
        return 1
    names = [v['name'] for v in detail['vertices']]
    blob = ' '.join(names)
    plan = rest(args.namespace, pod, f'/jobs/{jid}/plan') or {}
    pblob = json.dumps(plan)
    print(f"job {detail['name']} ({jid})  vertices={len(names)}")
    print('\noperator mix')
    for pat in ('LocalGroupAggregate', 'GlobalGroupAggregate', 'GroupAggregate',
                'MiniBatchAssigner', 'Join', 'Rank', 'ChangelogNormalize',
                'SinkMaterializer', 'Deduplicate'):
        n = blob.count(pat)
        if pat == 'GroupAggregate':
            n -= blob.count('LocalGroupAggregate') + blob.count('GlobalGroupAggregate')
        print(f'  {pat:22} {n}')
    modes = set(re.findall(r'MiniBatchAssigner\(interval=\[[^\]]*\], mode=\[(\w+)\]', pblob))
    print('\nmini-batch mode :', ', '.join(sorted(modes)) or 'off (no assigner)')
    phase = 'ONE_PHASE' if blob.count('LocalGroupAggregate') == 0 else 'TWO_PHASE'
    print('aggregate phase :', phase if 'GroupAggregate' in blob else 'n/a')
    print('rowtime in plan :', 'ROWTIME' in pblob)
    return 0


def cmd_watch(args):
    pod = jobmanager(args.namespace)
    jid, detail = shacl_job(args.namespace, pod)
    if not detail:
        print('no RUNNING shacl-validation job found')
        return 1
    before = counters(detail)
    print(f'sampling {args.seconds}s ...')
    time.sleep(args.seconds)
    _, detail2 = shacl_job(args.namespace, pod)
    after = counters(detail2)

    rows = []
    for name, (bi, bo) in before.items():
        ai, ao = after.get(name, (bi, bo))
        rows.append((name, ai - bi, ao - bo))

    swallow = sorted([r for r in rows if r[1] > 0 and r[2] == 0],
                     key=lambda r: -r[1])
    amplify = sorted([r for r in rows if r[1] > 0 and r[2] > 2 * r[1]],
                     key=lambda r: -(r[2] - r[1]))
    busiest = sorted(rows, key=lambda r: -(r[1] + r[2]))

    def show(title, items, note):
        print(f'\n{title}  ({note})')
        if not items:
            print('   none')
        for name, i, o in items[:args.top]:
            print(f'   in={i:9} out={o:9}  {name[:88]}')

    show('SWALLOWING', swallow,
         'took records, emitted none -- a changelog dies here')
    show('AMPLIFYING', amplify,
         'emitted far more than taken -- feedback or fan-out')
    show('BUSIEST', busiest, 'highest total traffic')
    return 0


def kafka(ns, cmd):
    return sh(f"kubectl -n {ns} exec my-cluster-nodes-0 -- sh -c "
              f"\"KAFKA_HEAP_OPTS='-Xmx512M' {cmd}\"")


def offset_at(ns, topic, when_ms):
    out = kafka(ns, f'bin/kafka-get-offsets.sh --bootstrap-server '
                    f'localhost:9092 --topic {topic} --time {when_ms}')
    try:
        return int(out.rsplit(':', 1)[1])
    except Exception:
        return None


def cmd_churn(args):
    ns = args.namespace
    t1 = int(time.time() * 1000)
    t0 = t1 - args.minutes * 60 * 1000
    for topic in ('iff.alerts.bulk', 'iff.alerts'):
        start, end = offset_at(ns, topic, t0), offset_at(ns, topic, -1)
        if start is None or end is None or end <= start:
            print(f'\n=== {topic}: no records in the window')
            continue
        n = min(end - start, args.max_records)
        raw = kafka(ns, f'bin/kafka-console-consumer.sh --bootstrap-server '
                        f'localhost:9092 --topic {topic} --partition 0 '
                        f'--offset {start} --max-messages {n} '
                        f'--timeout-ms 60000 --property print.timestamp=true')
        seen = {}
        for line in raw.splitlines():
            if not line.startswith('CreateTime:'):
                continue
            ts, _, payload = line.partition('\t')
            try:
                d = json.loads(payload)
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            res = str(d.get('resource', ''))
            if args.resource and args.resource not in res:
                continue
            key = (res, str(d.get('event', '')))
            seen.setdefault(key, []).append((int(ts.split(':')[1]),
                                             d.get('severity')))
        print(f'\n=== {topic}: {n} records scanned, {len(seen)} keys')
        ranked = sorted(seen.items(), key=lambda kv: -len(kv[1]))
        span = max(args.minutes, 1)
        for (res, event), seq in ranked[:args.top]:
            sev = [s for _, s in seq]
            rate = len(seq) / (span * 60.0)
            flips = sum(1 for a, b in zip(sev, sev[1:]) if a != b)
            flag = ''
            if len(seq) > 500:
                flag = '  <-- OSCILLATING'
            elif 'ok' not in sev and len(seq) > 1:
                flag = '  <-- never cleared'
            print(f'  {res[-28:]:30} {event[:44]:46} n={len(seq):6} '
                  f'{rate:7.2f}/s flips={flips:5} last={sev[-1]}{flag}')
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--namespace', default='iff')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('plan', help='what the job compiled to')
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser('watch', help='diff per-vertex counters over time')
    p.add_argument('--seconds', type=int, default=60)
    p.add_argument('--top', type=int, default=8)
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser('churn', help='verdict records per key in the topics')
    p.add_argument('--minutes', type=int, default=15)
    p.add_argument('--top', type=int, default=15)
    p.add_argument('--resource', default=None,
                   help='only keys whose resource contains this string')
    p.add_argument('--max-records', type=int, default=200000)
    p.set_defaults(func=cmd_churn)

    args = ap.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
