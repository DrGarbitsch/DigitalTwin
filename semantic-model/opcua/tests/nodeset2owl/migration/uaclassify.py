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
"""Independent static/dynamic classification from nodeset XML (does not use lib/nodesetparser).

NamespaceMetadata (StaticNodeIdTypes/StaticNumericNodeIdRange/StaticStringNodeIdPattern) where it decides,
otherwise: types and instance declarations static, other instances dynamic.
Keys are (raw namespace uri, canonical id) like 'i=31'.
"""
import re
import xml.etree.ElementTree as ET

NS = {'ua': 'http://opcfoundation.org/UA/2011/03/UANodeSet.xsd'}
CORE = 'http://opcfoundation.org/UA/'
INSTANCE = ('UAObject', 'UAVariable', 'UAMethod', 'UAView')
TYPES = ('UAObjectType', 'UAVariableType', 'UADataType', 'UAReferenceType')
IDT = {'i': 0, 's': 1, 'g': 2, 'b': 3}


def tag(e):
    return e.tag.split('}')[-1]


def canonical(idt, ident):
    if idt == 'i':
        ident = str(int(ident))
    elif idt == 'g':
        ident = ident.strip('{}').lower()
    return f'{idt}={ident}'


class NodesetFile:
    def __init__(self, path):
        self.root = ET.parse(path).getroot()
        self.aliases = {a.get('Alias'): a.text.strip() for a in self.root.findall('ua:Aliases/ua:Alias', NS)}
        self.ns = [CORE] + [u.text.strip() for u in self.root.findall('ua:NamespaceUris/ua:Uri', NS)]

    def key(self, nodeid):
        nodeid = self.aliases.get(nodeid.strip(), nodeid.strip())
        idx = 0
        if nodeid.startswith('ns='):
            nspart, nodeid = nodeid.split(';', 1)
            idx = int(nspart[3:])
        idt, ident = nodeid.split('=', 1)
        return (self.ns[idx], canonical(idt, ident))

    def refs(self, node):
        for r in node.findall('ua:References/ua:Reference', NS):
            yield self.key(r.get('ReferenceType')), r.get('IsForward') != 'false', self.key(r.text)


class Classifier:
    def __init__(self, paths):
        self.files = [NodesetFile(p) for p in paths]
        self.nodes = {}
        for f in self.files:
            for e in f.root:
                if tag(e) in INSTANCE + TYPES:
                    self.nodes.setdefault(f.key(e.get('NodeId')), (f, e))
        self.namespaces = {k[0] for k in self.nodes}
        self.rules = {}
        for key, (f, e) in self.nodes.items():
            if tag(e) != 'UAObject':
                continue
            if not any(rt == (CORE, 'i=40') and fw and t == (CORE, 'i=11616') for rt, fw, t in f.refs(e)):
                continue
            props = {}
            for k2, (f2, e2) in self.nodes.items():
                if f2 is f and tag(e2) == 'UAVariable' and e2.get('ParentNodeId') \
                        and f.key(e2.get('ParentNodeId')) == key:
                    vals = []
                    value = e2.find('ua:Value', NS)
                    for v in (list(value) if value is not None else []):
                        if 'ListOf' in v.tag:
                            vals += [i.text.strip() for i in v if i.text]
                        elif v.text:
                            vals.append(v.text.strip())
                    props[e2.get('BrowseName').split(':')[-1]] = vals
            if not props.get('NamespaceUri'):
                continue
            pat = props.get('StaticStringNodeIdPattern')
            self.rules[props['NamespaceUri'][0]] = {
                'types': {int(t) for t in props.get('StaticNodeIdTypes', [])},
                'ranges': [tuple(int(x) for x in (r.split(':') if ':' in r else (r, r)))
                           for r in props.get('StaticNumericNodeIdRange', [])],
                'pattern': re.compile(pat[0]) if pat and pat[0] else None}
        self.static = {k: self._is_static(k) for k in self.nodes}

    def _explicit(self, key):
        rule = self.rules.get(key[0]) or self.rules.get(key[0].rstrip('/')) or self.rules.get(key[0] + '/')
        if rule is None:
            return None
        idt, ident = key[1].split('=', 1)
        if idt == 'i' and rule['ranges']:
            return any(lo <= int(ident) <= hi for lo, hi in rule['ranges'])
        if idt == 's' and rule['pattern']:
            return rule['pattern'].fullmatch(ident) is not None
        if IDT[idt] in rule['types']:
            return True
        return None

    def parent(self, key):
        f, e = self.nodes[key]
        if e.get('ParentNodeId'):
            return f.key(e.get('ParentNodeId'))
        for rt, fw, t in f.refs(e):
            if not fw and rt[0] == CORE and rt[1] in ('i=47', 'i=46', 'i=49'):
                return t
        return None

    def _is_static(self, key):
        ex = self._explicit(key)
        if ex is not None:
            return ex
        if tag(self.nodes[key][1]) in TYPES:
            return True
        seen = set()
        while key not in seen:
            seen.add(key)
            if key not in self.nodes or tag(self.nodes[key][1]) not in INSTANCE:
                return False
            f, e = self.nodes[key]
            if any(rt == (CORE, 'i=37') and fw for rt, fw, _ in f.refs(e)):
                return True
            key = self.parent(key)
            if key is None:
                return False
            if key in self.nodes and tag(self.nodes[key][1]) in TYPES:
                return True
        return False
