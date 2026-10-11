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
"""Predict the new nodeset2owl output from an OLD expected file and compare it with the NEW output.

usage: predict.py old.ttl new.ttl target.xml [dep.xml ...] [--enforce]

The prediction applies only the agreed transformation rules (no lib/ code):
- node IRIs <ns>node<idt><id> -> <ns> + base64url(canonical ExpandedNodeId, nsu omitted for core)
- nodes classified dynamic (independent XML classifier) are not exported, nor triples touching them;
  nodes of a namespace exported by a dependency but missing there are dynamic; nodes of namespaces
  without any export are static
- renamings base:* -> uardf:*, opcua:*NodeClass -> uardf:*, instanceOf/rdf:type -> hasTypeDefinition,
  isAbstract class string -> node boolean, semantic bridge -> uardf:semanticBridgeReferenceType
- additions: uardf:nodeId/namespaceUri/browseName/name/symbolicName, uardf:parent from ParentNodeId
- displayName/description as @en, empty ones dropped
Language tags of other literals are ignored in the comparison.
"""
import base64
import os
import re
import sys
from collections import Counter
from urllib.parse import unquote, quote
from rdflib import Graph, URIRef, Literal, BNode, RDF, RDFS, OWL
from rdflib.compare import to_isomorphic, graph_diff
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uaclassify import Classifier, NodesetFile, CORE, canonical  # noqa: E402

BASE = 'https://industryfusion.github.io/contexts/ontology/v0/base/'
U = 'http://opcfoundation.org/rdf/uacore#'
B = lambda n: URIRef(BASE + n)  # noqa: E731
UA = lambda n: URIRef(U + n)  # noqa: E731
NODE_RE = re.compile(r'^(.*[/#:])node([isgb])([^/#:]+)$')
LOCALIZED = (UA('displayName'), UA('description'))

args = [a for a in sys.argv[1:] if not a.startswith('--')]
enforce = '--enforce' in sys.argv
old_path, new_path, target_path, dep_paths = args[0], args[1], args[2], args[3:]
target = NodesetFile(target_path)
clf = Classifier([target_path] + dep_paths)
dep_namespaces = {k[0] for k, (f, e) in clf.nodes.items() if f is not clf.files[0]}
target_nodes = {k for k, (f, e) in clf.nodes.items() if f is clf.files[0]}


def norm(uri):
    uri = str(uri)
    if uri.startswith('http') and not uri.endswith(('/', '#')):
        uri += '/'
    elif uri.startswith('urn') and not uri.endswith(':'):
        uri += ':'
    return uri


raw = {}  # normalized -> raw namespace uri
for f in clf.files:
    for uri in f.ns:
        raw.setdefault(norm(uri), uri)


def b64(s):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip('=')


def expanded(key):
    return key[1] if key[0] == CORE else f'nsu={key[0]};{key[1]}'


def is_dynamic(key):
    if key in clf.nodes:
        return not clf.static[key]
    return key[0] in dep_namespaces  # exported namespace without this node


def parse_old_iri(term):
    """old node IRI -> (prefix, key) or None"""
    if not isinstance(term, URIRef):
        return None
    m = NODE_RE.match(str(term))
    if not m or norm(m.group(1)) not in raw:
        return None
    prefix, idt, ident = m.group(1), m.group(2), unquote(m.group(3))
    if idt == 'i' and not ident.isdigit():
        return None
    return prefix, (raw[norm(prefix)], canonical(idt, ident))


DROP = object()


def new_iri(term):
    parsed = parse_old_iri(term)
    if parsed is None:
        return term
    prefix, key = parsed
    if is_dynamic(key):
        return DROP
    return URIRef(prefix + b64(expanded(key)))


old = Graph().parse(old_path)
pred = Graph()
defined = set(old.subjects(B('hasNodeId'), None))
ns_uri = {s: str(o) for s, o in old.subject_objects(B('hasUri'))}  # namespace class -> normalized uri

for node in defined:
    n = new_iri(node)
    if n is DROP:
        continue
    _, key = parse_old_iri(node)
    pred.add((n, UA('nodeId'), Literal(expanded(key))))
    pred.add((n, UA('namespaceUri'), Literal(key[0])))
    bn = str(old.value(node, B('hasBrowseName')))
    bn_class = old.value(node, B('hasBrowseNameNamespace'))
    bn_ns_uri = ns_uri.get(bn_class) or (str(bn_class).rsplit('/', 1)[0] + '/' if bn_class is not None else CORE)
    bn_ns = raw.get(norm(bn_ns_uri), bn_ns_uri)
    pred.add((n, UA('name'), Literal(bn)))
    pred.add((n, UA('browseName'), Literal(bn if bn_ns == CORE else f'nsu={bn_ns};{bn}')))
    sym = old.value(node, B('hasSymbolicName'))
    pred.add((n, UA('symbolicName'), Literal(str(sym) if sym is not None else bn)))
    if key in target_nodes:
        e = clf.nodes[key][1]
        if e.get('ParentNodeId'):
            p = clf.files[0].key(e.get('ParentNodeId'))
            if not is_dynamic(p):
                pred.add((n, UA('parent'), URIRef(norm(p[0]) + b64(expanded(p)))
                          if p[0] != CORE else URIRef(CORE + b64(expanded(p)))))

for s, p, o in old:
    if p in (B('hasNodeId'), B('hasIdentifierType'), B('hasNamespace'), B('hasBrowseName'),
             B('hasBrowseNameNamespace'), B('hasSymbolicName')):
        continue
    if p == B('isAbstract'):
        definer = next(old.subjects(B('definesType'), s), None)
        if definer is not None and new_iri(definer) is not DROP:
            pred.add((new_iri(definer), UA('isAbstract'), Literal(str(o).strip().lower() == 'true')))
        continue
    ns_, no_ = new_iri(s), new_iri(o)
    if ns_ is DROP or no_ is DROP:
        continue
    if p == RDF.type and s in defined:
        if str(o).startswith('http://opcfoundation.org/UA/') and str(o).endswith('NodeClass'):
            pred.add((ns_, RDF.type, UA(str(o).rsplit('/', 1)[1][:-len('NodeClass')])))
        elif enforce:
            pred.add((ns_, RDF.type, no_))
        else:
            pred.add((ns_, UA('hasTypeDefinition'), no_))
        continue
    if p == B('instanceOf'):
        pred.add((ns_, UA('hasTypeDefinition'), no_))
        continue
    if p == B('definesType'):
        pred.add((ns_, UA('definesType'), no_))
        continue
    if p in (B('hasDisplayName'), B('hasDescription')):
        if str(o).strip() == '':
            continue
        pred.add((ns_, UA('displayName' if p == B('hasDisplayName') else 'description'),
                  Literal(str(o), lang=o.language or 'en')))
        continue
    if p == RDFS.subPropertyOf and o == B('SemanticBridgeReferenceType'):
        pred.add((ns_, RDF.type, OWL.ObjectProperty))
        pred.add((ns_, RDFS.subPropertyOf, UA('semanticBridgeReferenceType')))
        continue
    pred.add((ns_, p, no_))


# B: remove blank node structures (RDF lists) which are no longer referenced
while True:
    referenced = {o for _, _, o in pred if isinstance(o, BNode)}
    orphans = [t for t in pred if isinstance(t[0], BNode) and t[0] not in referenced]
    if not orphans:
        break
    for t in orphans:
        pred.remove(t)

# D: semantic bridge by rule: every Aggregates edge s p o gets s <ns of BrowseName of o>has<name> o
AGGREGATES = URIRef('http://opcfoundation.org/UA/Aggregates')
aggregates = {AGGREGATES}
changed = True
while changed:
    changed = False
    for sub, sup in old.subject_objects(RDFS.subPropertyOf):
        if sup in aggregates and sub not in aggregates:
            aggregates.add(sub)
            changed = True
for s, p, o in list(pred):
    if p in aggregates and (o, UA('browseName'), None) in pred:
        qn = str(pred.value(o, UA('browseName')))
        ns, name = (qn[4:].split(';', 1) if qn.startswith('nsu=') else (CORE, qn))
        bridge = URIRef(norm(ns) + quote(f'has{name}'))
        pred.add((s, bridge, o))
        pred.add((bridge, RDF.type, OWL.ObjectProperty))
        pred.add((bridge, RDFS.subPropertyOf, UA('semanticBridgeReferenceType')))
# A: declarations of bridge properties which are not used any more
for prop in list(pred.subjects(RDFS.subPropertyOf, UA('semanticBridgeReferenceType'))):
    if not any(True for _ in pred.triples((None, prop, None))):
        pred.remove((prop, RDFS.subPropertyOf, UA('semanticBridgeReferenceType')))
        pred.remove((prop, RDF.type, OWL.ObjectProperty))


def comparable(g):
    out = Graph()
    for s, p, o in g:
        if isinstance(o, Literal) and o.language and p not in LOCALIZED:
            o = Literal(str(o))
        out.add((s, p, o))
    return out


new = Graph().parse(new_path)
name = new_path.rsplit('/', 1)[-1]
dropped_nodes = sum(1 for n in defined if new_iri(n) is DROP)
print(f'{name}: old {len(old)} triples / {len(defined)} nodes ({dropped_nodes} dynamic), '
      f'predicted {len(pred)}, new {len(new)}')
a, b = to_isomorphic(comparable(pred)), to_isomorphic(comparable(new))
if a == b:
    print('  PROVEN: new output == prediction from old expected file')
else:
    _, only_pred, only_new = graph_diff(a, b)
    print(f'  DIFFERENT: {len(only_pred)} only predicted, {len(only_new)} only new')
    print('   only predicted, by predicate:', Counter(str(t[1]).rsplit("/", 1)[-1] for t in only_pred).most_common(8))
    print('   only new, by predicate:', Counter(str(t[1]).rsplit("/", 1)[-1] for t in only_new).most_common(8))
    for t in list(only_pred)[:5]:
        print('    pred:', t)
    for t in list(only_new)[:5]:
        print('    new :', t)
