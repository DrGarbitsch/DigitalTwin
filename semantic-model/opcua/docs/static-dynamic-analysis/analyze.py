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
"""Semantic analysis of static and dynamic OPC UA nodes on the full nodeset2owl exports (build_exports.py).

Works on the uardf identification only: a node is dynamic iff it has uardf:serverUri. Writes a data report
(markdown) with
  1. dynamic subtrees per namespace, their roots and why they are dynamic (NamespaceMetadata or fallback rule),
  2. static nodes below dynamic nodes (grouped by the static node directly below the dynamic one) with type,
     data type, access level, value and the description of the specification,
  3. static instance variables whose value the specification does not fix (not below a dynamic node),
  4. type system nodes (encodings, type dictionaries, descriptions) and dictionary entries: static or dynamic.

usage: analyze.py <exports directory> <report.md>
"""
import glob
import os
import sys
from collections import defaultdict
from rdflib import Graph, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF

U = Namespace('http://opcfoundation.org/rdf/uacore#')
BASE = Namespace('https://industryfusion.github.io/contexts/ontology/v0/base/')
OPCUA = Namespace('http://opcfoundation.org/UA/')
CORE = 'http://opcfoundation.org/UA/'
AGGREGATES = [OPCUA[p] for p in ('HasComponent', 'HasProperty', 'HasOrderedComponent', 'HasAddIn')]
IDT = {'i': 0, 's': 1, 'g': 2, 'b': 3}
TYPE_SYSTEM = {'DataTypeEncodingType': 'encoding object', 'DataTypeDictionaryType': 'type dictionary',
               'DataTypeDescriptionType': 'data type description', 'DataTypeSystemType': 'type system'}


def load(directory):
    g = Graph()
    files = sorted(glob.glob(os.path.join(directory, '*.owl.ttl')))
    for path in files:
        g.parse(path)
    return g, [os.path.basename(f) for f in files]


class Model:
    def __init__(self, g):
        self.g = g
        self.nodes = set(g.subjects(U.nodeId, None))
        self.dynamic = {n for n in self.nodes if (n, U.serverUri, None) in g}
        self.ns = {n: str(g.value(n, U.namespaceUri)) for n in self.nodes}
        self.rules = self._metadata_rules()
        self._parent = {}

    def name(self, n):
        return str(self.g.value(n, U.name) or self.g.value(n, U.browseName) or n)

    def canonical(self, n):
        return str(self.g.value(n, U.nodeId)).rsplit(';', 1)[-1]

    def nodeclass(self, n):
        for t in self.g.objects(n, RDF.type):
            if str(t).startswith(str(U)):
                return str(t)[len(str(U)):]
        return '?'

    def typedef(self, n):
        t = self.g.value(n, U.hasTypeDefinition)
        return self.g.qname(t) if t is not None else ''

    def description(self, n):
        d = self.g.value(n, U.description)
        return ' '.join(str(d).split()) if d is not None else ''

    def parent(self, n):
        if n not in self._parent:
            p = self.g.value(n, U.parent)
            if p is None:
                p = next((s for a in AGGREGATES for s in self.g.subjects(a, n)), None)
            if p is None:
                p = next(self.g.subjects(OPCUA['Organizes'], n), None)
            if p is None:
                p = next(self.g.subjects(OPCUA['HasEncoding'], n), None)
            self._parent[n] = p
        return self._parent[n]

    def ancestors(self, n):
        seen = set()
        p = self.parent(n)
        while p is not None and p not in seen:
            seen.add(p)
            yield p
            p = self.parent(p)

    def value(self, n):
        v = self.g.value(n, BASE.hasValue)
        if v is not None:
            return self.g.qname(v) if isinstance(v, URIRef) else str(v)
        lst = self.g.value(n, BASE.hasValueList)
        if lst is not None:
            items = [self.g.qname(i) if isinstance(i, URIRef) else str(i) for i in Collection(self.g, lst)]
            return '[' + ', '.join(items) + ']'
        return None

    def access(self, n):
        levels = {str(a).rsplit('/', 1)[-1] for a in self.g.objects(n, BASE.hasAccessLevel)}
        if not levels:
            return 'read (default)'
        return ', '.join(sorted(levels))

    def datatype(self, n):
        d = self.g.value(n, BASE.hasDatatype)
        return self.g.qname(d) if d is not None else ''

    def is_template(self, n):
        """instance declaration or part of a type definition"""
        if (n, OPCUA['HasModellingRule'], None) in self.g:
            return True
        return any((a, U.definesType, None) in self.g or (a, OPCUA['HasModellingRule'], None) in self.g
                   for a in self.ancestors(n))

    def _metadata_rules(self):
        rules = {}
        for obj in self.g.subjects(U.hasTypeDefinition, OPCUA['NamespaceMetadataType']):
            props = {self.name(c): c for c in self.g.subjects(U.parent, obj)}
            if 'NamespaceUri' not in props or self.value(props['NamespaceUri']) is None:
                continue
            uri = self.value(props['NamespaceUri'])

            def values(name):
                v = props.get(name)
                lst = self.g.value(v, BASE.hasValueList) if v is not None else None
                return [str(i) for i in Collection(self.g, lst)] if lst is not None else []
            ranges = []
            for r in values('StaticNumericNodeIdRange'):
                lo, _, hi = r.partition(':')
                ranges.append((int(lo), int(hi or lo)))
            pattern = self.value(props['StaticStringNodeIdPattern']) if 'StaticStringNodeIdPattern' in props else None
            pattern = pattern.strip() if pattern is not None else None
            rules[uri.rstrip('/')] = {'types': {int(t) for t in values('StaticNodeIdTypes')}, 'ranges': ranges,
                                      'pattern': pattern or None, 'object': obj}
        return rules

    def reason(self, n):
        """why a node is static/dynamic: 'metadata' if the NamespaceMetadata decides, else 'fallback rule'"""
        rule = self.rules.get(self.ns[n].rstrip('/'))
        if rule is None:
            return 'fallback rule (no NamespaceMetadata)'
        idt, ident = self.canonical(n).split('=', 1)
        if idt == 'i' and rule['ranges']:
            return 'NamespaceMetadata (StaticNumericNodeIdRange)'
        if idt == 's' and rule['pattern']:
            return 'NamespaceMetadata (StaticStringNodeIdPattern)'
        if IDT[idt] in rule['types']:
            return 'NamespaceMetadata (StaticNodeIdTypes)'
        return 'fallback rule (NamespaceMetadata does not decide)'


SECURITY = ('DefaultRolePermissions', 'DefaultUserRolePermissions', 'DefaultAccessRestrictions')
CATEGORIES = ['constant: method signature', 'constant: namespace description', 'constant: diagnostics counter metadata',
              'structure: object/method without value', 'server state: security configuration',
              'server state: configuration, capability or runtime value']


def category(m, n):
    """Semantic category of a static node below a dynamic node (see the review in the documentation)."""
    name = m.name(n)
    if m.nodeclass(n) != 'Variable':
        return 'structure: object/method without value'
    if name in ('InputArguments', 'OutputArguments'):
        return 'constant: method signature'
    parent = m.parent(n)
    if parent is not None and (parent, U.hasTypeDefinition, OPCUA['NamespaceMetadataType']) in m.g:
        return 'server state: security configuration' if name in SECURITY else 'constant: namespace description'
    # Classification and DiagnosticsLevel of a PubSub diagnostics counter are fixed by the specification
    if name in ('Classification', 'DiagnosticsLevel') and parent is not None and \
            m.typedef(parent).endswith('PubSubDiagnosticsCounterType'):
        return 'constant: diagnostics counter metadata'
    return 'server state: configuration, capability or runtime value'


def short_ns(uri):
    return 'core' if uri == CORE else uri.replace(CORE, '').rstrip('/') or uri


def section_dynamic(m, out):
    out.append('## 1. Dynamic subtrees\n')
    per_ns = defaultdict(lambda: [0, 0])
    for n in m.nodes:
        per_ns[m.ns[n]][1 if n in m.dynamic else 0] += 1
    out.append('| Namespace | static | dynamic | NamespaceMetadata |')
    out.append('|---|---|---|---|')
    for ns, (s, d) in sorted(per_ns.items(), key=lambda x: short_ns(x[0])):
        rule = m.rules.get(ns.rstrip('/'))
        meta = 'none' if rule is None else (
            f"StaticNodeIdTypes={sorted(rule['types'])}, {len(rule['ranges'])} StaticNumericNodeIdRange(s), "
            f"StaticStringNodeIdPattern={rule['pattern']!r}")
        out.append(f'| {short_ns(ns)} | {s} | {d} | {meta} |')
    out.append('')
    # roots: topmost dynamic node of a namespace (its parent is static, missing or of another namespace)
    roots = defaultdict(list)
    for n in m.dynamic:
        p = m.parent(n)
        if p is None or p not in m.dynamic or m.ns.get(p) != m.ns[n]:
            roots[m.ns[n]].append(n)
    size = defaultdict(int)
    for n in m.dynamic:
        root = n
        for a in m.ancestors(n):
            if a in m.dynamic and m.ns.get(a) == m.ns[n]:
                root = a
            else:
                break
        size[root] += 1
    out.append('### Roots of the dynamic subtrees\n')
    out.append('| Namespace | Root | NodeId | Class / TypeDefinition | Parent | Nodes | Reason |')
    out.append('|---|---|---|---|---|---|---|')
    for ns in sorted(roots, key=short_ns):
        for r in sorted(roots[ns], key=lambda x: (-size[x], m.name(x))):
            p = m.parent(r)
            pname = (f'{m.name(p)} ({short_ns(m.ns.get(p, "?"))}, {"dynamic" if p in m.dynamic else "static"})'
                     if p is not None and p in m.ns else '-')
            out.append(f'| {short_ns(ns)} | {m.name(r)} | `{m.canonical(r)}` | {m.nodeclass(r)} / '
                       f'{m.typedef(r)} | {pname} | {size[r]} | {m.reason(r)} |')
    out.append('')


def section_static_below_dynamic(m, out):
    out.append('## 2. Static nodes below dynamic nodes\n')
    summary = defaultdict(lambda: defaultdict(int))
    for n in m.nodes - m.dynamic:
        chain = [n] + list(m.ancestors(n))
        for i, a in enumerate(chain[1:], 1):
            if a in m.dynamic:
                boundary = chain[i - 1]
                summary[(short_ns(m.ns[boundary]), m.name(a), m.name(boundary))][category(m, n)] += 1
                break
    out.append('### Summary by category\n')
    out.append('| Namespace | Dynamic parent | Boundary | ' + ' | '.join(CATEGORIES) + ' |')
    out.append('|---|---|---|' + '---|' * len(CATEGORIES))
    totals = defaultdict(int)
    for key in sorted(summary):
        counts = summary[key]
        for c in CATEGORIES:
            totals[c] += counts[c]
        out.append(f'| {key[0]} | {key[1]} | {key[2]} | ' + ' | '.join(str(counts[c] or '') for c in CATEGORIES) + ' |')
    out.append('| **Total** | | | ' + ' | '.join(f'**{totals[c]}**' for c in CATEGORIES) + ' |')
    out.append('')
    out.append('Grouped by the static node directly below a dynamic node (boundary). Variables: data type, '
               'access level, value in the nodeset, description of the specification.\n')
    groups = defaultdict(list)
    for n in m.nodes - m.dynamic:
        chain = [n] + list(m.ancestors(n))
        for i, a in enumerate(chain[1:], 1):
            if a in m.dynamic:
                groups[chain[i - 1]].append(n)
                break
    for boundary in sorted(groups, key=lambda b: (short_ns(m.ns[b]), m.name(m.parent(b)), m.name(b))):
        members = groups[boundary]
        dyn = m.parent(boundary)
        out.append(f'### {short_ns(m.ns[boundary])}: {m.name(dyn)} / {m.name(boundary)} '
                   f'(`{m.canonical(boundary)}`, {m.nodeclass(boundary)}, {m.typedef(boundary)})\n')
        if m.description(boundary):
            out.append(f'> {m.description(boundary)}\n')
        variables = sorted((v for v in members if m.nodeclass(v) == 'Variable'),
                           key=lambda v: [m.name(x) for x in reversed([v] + list(m.ancestors(v)))])
        others = len(members) - len(variables)
        out.append(f'{len(members)} static nodes ({len(variables)} variables, {others} objects/methods)\n')
        if variables:
            out.append('| Path below boundary | Data type | Access | Value | Description |')
            out.append('|---|---|---|---|---|')
            for v in variables:
                path = [m.name(v)]
                for a in m.ancestors(v):
                    if a == dyn:
                        break
                    path.append(m.name(a))
                value = m.value(v)
                value = '-' if value is None else (value[:60] + '…' if len(value) > 60 else value)
                desc = m.description(v)
                desc = desc[:140] + '…' if len(desc) > 140 else desc
                out.append(f"| {' / '.join(reversed(path))} | {m.datatype(v)} | {m.access(v)} | "
                           f"{value.replace('|', '/')} | {desc.replace('|', '/')} |")
            out.append('')


def section_static_unfixed(m, out):
    out.append('## 3. Static instance variables without value, not below a dynamic node\n')
    out.append('| Namespace | Path | Data type | Access | Description |')
    out.append('|---|---|---|---|---|')
    for v in sorted(m.nodes - m.dynamic, key=lambda x: (short_ns(m.ns[x]), m.name(x))):
        if m.nodeclass(v) != 'Variable' or m.value(v) is not None or m.is_template(v):
            continue
        if any(a in m.dynamic for a in m.ancestors(v)):
            continue
        path = [m.name(a) for a in m.ancestors(v)][::-1] + [m.name(v)]
        desc = m.description(v)
        out.append(f"| {short_ns(m.ns[v])} | {' / '.join(path)} | {m.datatype(v)} | {m.access(v)} | "
                   f"{(desc[:140] + '…' if len(desc) > 140 else desc).replace('|', '/')} |")
    out.append('')


def section_type_system(m, out):
    out.append('## 4. Type system nodes and dictionary entries\n')
    counts = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    reasons = defaultdict(set)
    for n in m.nodes:
        t = m.typedef(n).split(':')[-1]
        kind = TYPE_SYSTEM.get(t)
        if kind is None and (n, OPCUA['HasEncoding'], None) in m.g:
            continue
        if kind is None and t in ('DictionaryEntryType', 'IrdiDictionaryEntryType', 'UriDictionaryEntryType'):
            kind = 'dictionary entry'
        if kind is None:
            continue
        counts[m.ns[n]][kind][1 if n in m.dynamic else 0] += 1
        if n in m.dynamic:
            reasons[(m.ns[n], kind)].add(m.reason(n))
    out.append('| Namespace | Kind | static | dynamic | Reason for dynamic |')
    out.append('|---|---|---|---|---|')
    for ns in sorted(counts, key=short_ns):
        for kind, (s, d) in sorted(counts[ns].items()):
            out.append(f"| {short_ns(ns)} | {kind} | {s} | {d} | {', '.join(sorted(reasons[(ns, kind)]))} |")
    out.append('')
    # static nodes referencing dynamic type system nodes / dictionary entries (lost without server URI)
    links = defaultdict(int)
    for p in (OPCUA['HasEncoding'], OPCUA['HasDescription'], OPCUA['HasDictionaryEntry']):
        for s, o in m.g.subject_objects(p):
            if s in m.nodes and o in m.dynamic and s not in m.dynamic:
                links[(short_ns(m.ns[s]), m.g.qname(p))] += 1
    out.append('References from static nodes to dynamic type system nodes / dictionary entries (lost in the '
               'export without server URI):\n')
    out.append('| Namespace | Reference | Count |')
    out.append('|---|---|---|')
    for (ns, p), c in sorted(links.items()):
        out.append(f'| {ns} | {p} | {c} |')
    out.append('')


def main():
    g, files = load(sys.argv[1])
    m = Model(g)
    out = ['# Static/dynamic analysis data report\n',
           f'Generated by analyze.py from the {len(files)} nodeset2owl exports of translate_default_nodesets.make '
           '(UA-Nodeset UA-1.05.03-2023-12-15), built with --serverUri by build_exports.py. '
           f'{len(m.nodes)} nodes, {len(m.dynamic)} dynamic.\n']
    section_dynamic(m, out)
    section_static_below_dynamic(m, out)
    section_static_unfixed(m, out)
    section_type_system(m, out)
    open(sys.argv[2], 'w').write('\n'.join(out) + '\n')
    print(f'{sys.argv[2]}: {len(out)} lines')


if __name__ == '__main__':
    main()
