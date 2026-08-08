#!/usr/bin/env python3
"""Count the Flink physical operators the generated statements cost.

Runs the real Flink planner (the one pinned in requirements.txt) over the
statements in output/shacl-validation-maps.yaml and reports how many physical
nodes each one contributes to the job graph. Because the planner reuses common
sub-plans across a statement set, per-statement cost is reported as a marginal:
ops(full set) - ops(set without that statement).

Source tables are swapped for `datagen` and sinks for `blackhole`, since the
real `upsert-kafka` connector is not on the local classpath. Absolute counts
therefore differ from the deployed job, but differences between variants -
which is what this is for - do not.

Usage:
    python debug/count_flink_operators.py [--marginal]

Requires the `output/` folder to be populated (`make flink`) and setuptools to
be importable (pyflink's loopback server needs pkg_resources).
"""
import argparse
import os
import re
import sys

import ruamel.yaml
from pyflink.table import EnvironmentSettings, TableEnvironment

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUT = os.path.join(ROOT, 'output')
sys.path.insert(0, ROOT)

SINK_SUFFIX = '__sink'


def _docs(path):
    """Split a multi-document yaml file, tolerating helm templating."""
    y = ruamel.yaml.YAML(typ='safe')
    y.allow_duplicate_keys = True
    chunks, cur = [], []
    for line in open(path).read().splitlines():
        if line.rstrip() == '---':
            chunks.append('\n'.join(cur))
            cur = []
        else:
            cur.append(line)
    chunks.append('\n'.join(cur))
    for chunk in chunks:
        if not chunk.strip():
            continue
        try:
            doc = y.load(chunk)
        except Exception:
            continue          # unquoted {{ .Values }} - not a table we can use
        if isinstance(doc, dict):
            yield doc


def load_specs():
    tables, views = {}, {}
    for f in ['core.yaml', 'ngsild.yaml', 'rdf.yaml']:
        for doc in _docs(os.path.join(OUTPUT, f)):
            if doc.get('kind') == 'BeamSqlTable':
                tables[doc['spec']['name']] = doc['spec']
            elif doc.get('kind') == 'BeamSqlView':
                views[doc['spec']['name']] = doc['spec']['sqlstatement']
    if 'constraint_table' not in tables:
        from lib.utils import constraint_table as ct
        tables['constraint_table'] = {'name': 'constraint_table', 'fields': ct}
    return tables, views


def field_lines(spec):
    cols, extras = [], []
    for f in spec.get('fields', []):
        (name, typ), = f.items()
        if name == 'watermark':
            extras.append(f'WATERMARK {typ}')
            continue
        if 'VIRTUAL' in typ:
            # METADATA VIRTUAL is excluded from the INSERT schema; so is a
            # computed column, which datagen can actually produce.
            cols.append(f'`{name}` AS CAST(CURRENT_TIMESTAMP AS TIMESTAMP(3))')
            continue
        typ = re.sub(r"METADATA\s+FROM\s+'[^']*'", '', typ)
        typ = ' '.join(re.sub(r'\bMETADATA\b', '', typ).split())
        cols.append(f'`{name}` {typ}')
    return cols, extras


def all_ddl(sinks):
    tables, views = load_specs()
    out = []
    for name, spec in tables.items():
        cols, extras = field_lines(spec)
        body = ',\n  '.join(cols + extras)
        out.append(f"CREATE TABLE `{name}` (\n  {body}\n) "
                   f"WITH ('connector'='datagen', 'rows-per-second'='1')")
        if name in sinks:
            plain = ',\n  '.join(c for c in cols if ' AS ' not in c)
            out.append(f"CREATE TABLE `{name}{SINK_SUFFIX}` (\n  {plain}\n) "
                       f"WITH ('connector'='blackhole')")
    out += [f'CREATE VIEW `{n}` AS {sql}' for n, sql in views.items()]
    return out


def load_statements(path):
    stmts = []
    for doc in _docs(path):
        if doc.get('kind') != 'ConfigMap':
            continue
        data = doc.get('data', {})
        stmts += [data[k] for k in sorted(data, key=int)]
    return stmts


def clean(s):
    # STATE_TTL is a Flink 1.18+ hint and is rejected by the 1.17 planner. It
    # controls state retention only, never the shape of the operator graph.
    s = re.sub(r'/\*\+.*?\*/', '', s, flags=re.S)
    s = re.sub(r'(INSERT\s+(?:OR\s+REPLACE\s+)?INTO\s+)`?(\w+)`?',
               lambda m: m.group(1) + m.group(2) + SINK_SUFFIX, s, flags=re.I)
    return s.rstrip().rstrip(';').rstrip()


def sinks_of(stmts):
    return set(re.findall(r'INSERT\s+(?:OR\s+REPLACE\s+)?INTO\s+`?(\w+)',
                          ' '.join(stmts), re.I))


NODE = re.compile(r'^[\s:+\-|]*([A-Z][A-Za-z]*)\(')


def count_ops(plan_text):
    """Physical nodes in the execution plan. `Reused(...)` back-references are
    not new operators and are excluded, so sub-plan reuse is accounted for."""
    counts, total = {}, 0
    for line in plan_text.split('== Optimized Execution Plan ==')[-1].splitlines():
        m = NODE.match(line)
        if not m or m.group(1) == 'Reused':
            continue
        counts[m.group(1)] = counts.get(m.group(1), 0) + 1
        total += 1
    return total, counts


def ops(stmts, sinks, extra_ddl=()):
    env = TableEnvironment.create(EnvironmentSettings.in_streaming_mode())
    cfg = env.get_config()
    for k, v in [('table.exec.sink.upsert-materialize', 'auto'),
                 ('table.exec.mini-batch.enabled', 'true'),
                 ('table.exec.mini-batch.allow-latency', '100 ms'),
                 ('table.exec.mini-batch.size', '1000'),
                 ('pipeline.object-reuse', 'true')]:
        cfg.set(k, v)
    for d in list(all_ddl(sinks)) + list(extra_ddl):
        env.execute_sql(d)
    ss = env.create_statement_set()
    for s in stmts:
        ss.add_insert_sql(clean(s))
    return count_ops(ss.explain())


def label(stmt):
    m = re.search(r"'([A-Za-z]*ConstraintComponent[^']*)' AS event", stmt)
    if m:
        return m.group(1)
    m = re.search(r'INSERT\s+INTO\s+(\w+)', stmt, re.I)
    return m.group(1) if m else '?'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--marginal', action='store_true',
                    help='also report each statement\'s marginal cost '
                         '(one planner run per statement, slow)')
    ap.add_argument('--file', default=os.path.join(OUTPUT, 'shacl-validation-maps.yaml'))
    args = ap.parse_args()

    stmts = load_statements(args.file)
    sinks = sinks_of(stmts)
    total, counts = ops(stmts, sinks)
    print(f'{len(stmts)} statements -> {total} physical operators\n')
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f'   {k:24s} {v}')

    if args.marginal:
        print('\nmarginal cost per statement:')
        for i in range(len(stmts)):
            rest = [s for j, s in enumerate(stmts) if j != i]
            m = total - ops(rest, sinks)[0]
            print(f'   [{i:2d}] {label(stmts[i]):46s} {m:4d}')


if __name__ == '__main__':
    main()
