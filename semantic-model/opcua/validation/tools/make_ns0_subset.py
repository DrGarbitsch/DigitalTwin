#!/usr/bin/env python3
#
# Copyright (c) 2025 Intel Corporation
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
"""Extract a small, faithful subset of OPC UA Namespace 0 from the official
``Opc.Ua.NodeSet2.xml`` so that validation test fixtures can depend on it
instead of on the full 3.6 MB core nodeset.

Why a subset at all
-------------------
Every rule fixture under ``validation/specs/*/testcases/`` has to be *hermetic*:
running it must not download anything and must not drag in the whole of NS0.
But a fixture also cannot be fully standalone -- almost every Part 3 rule is
phrased in terms of NS0 nodes (``HasComponent``, ``PropertyType``,
``BaseEventType``, the ModellingRule Objects, ...), and ``nodeset2owl.py``
hard-fails when a referenced DataType or ReferenceType is not in the graph.

So the fixtures share one dependency: the subset this tool produces. It is
extracted from the real core nodeset rather than hand-written, so the NodeIds,
``IsAbstract``/``Symmetric`` flags and subtype hierarchies are the spec's own
and cannot silently drift from it.

What gets kept
--------------
Starting from an explicit seed list of BrowseNames (``SEED_BROWSE_NAMES``), the
closure is taken over the references a node genuinely cannot be understood
without:

* its supertype (an inverse ``HasSubtype`` reference),
* its ``HasTypeDefinition`` target,
* its ``DataType`` attribute, and the ``DataType`` of every ``Definition``
  field.

Everything else -- in particular the forward hierarchical references that give
NS0 types their many children -- is pruned. The subset therefore describes the
*type skeleton* of NS0 and nothing else, which is exactly what the rules need
and keeps the generated Turtle small enough to re-validate per test case.

Adding a companion specification (or a rule that needs an NS0 node not yet in
the subset) means adding its BrowseName to ``SEED_BROWSE_NAMES`` and re-running
this tool; the checked-in output is regenerated, not edited by hand.
"""

import argparse
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

UA_NS = 'http://opcfoundation.org/UA/2011/03/UANodeSet.xsd'
NS = {'ua': UA_NS}

# NodeClass elements we know how to carry over, in the order the OPC UA
# nodeset schema requires them to appear in a UANodeSet document.
NODE_ELEMENTS = [
    'UAReferenceType',
    'UADataType',
    'UAObjectType',
    'UAVariableType',
    'UAObject',
    'UAVariable',
    'UAMethod',
]

# References that are structural: without them the retained node is not
# interpretable on its own. Everything else is pruned (see module docstring).
STRUCTURAL_REFERENCE_ALIASES = {'HasSubtype', 'HasTypeDefinition'}

# The NS0 nodes the Part 3 rule fixtures are written against. Grouped only for
# readability -- the tool treats this as one flat set and resolves each name to
# its NodeId from the source nodeset.
SEED_BROWSE_NAMES = [
    # --- ReferenceType hierarchy (Part 3 section 7) ---
    'References',
    'NonHierarchicalReferences',
    'HierarchicalReferences',
    'HasChild',
    'Aggregates',
    'HasComponent',
    'HasProperty',
    'HasSubtype',
    'Organizes',
    'HasTypeDefinition',
    'HasModellingRule',
    'HasEncoding',
    'HasDescription',
    'HasEventSource',
    'HasNotifier',
    'GeneratesEvent',
    'AlwaysGeneratesEvent',
    'HasInterface',
    'HasAddIn',
    'AssociatedWith',
    'IsDeprecated',
    'HasStructuredComponent',
    'HasOrderedComponent',
    # --- Base types every fixture needs ---
    'BaseObjectType',
    'BaseVariableType',
    'BaseDataVariableType',
    'PropertyType',
    'FolderType',
    'ModellingRuleType',
    'BaseEventType',
    'BaseInterfaceType',
    'DataTypeEncodingType',
    'DataTypeSystemType',
    'DataTypeDescriptionType',
    # --- DataTypes (built-ins plus the abstract roots the rules mention) ---
    'BaseDataType',
    'Number',
    'Integer',
    'UInteger',
    'Enumeration',
    'Structure',
    'Boolean',
    'SByte',
    'Byte',
    'Int16',
    'UInt16',
    'Int32',
    'UInt32',
    'Int64',
    'UInt64',
    'Float',
    'Double',
    'String',
    'DateTime',
    'Guid',
    'ByteString',
    'XmlElement',
    'NodeId',
    'ExpandedNodeId',
    'StatusCode',
    'QualifiedName',
    'LocalizedText',
    'Argument',
    'Duration',
    # --- The five standard ModellingRule Objects (Part 3 section 6.4.4.4) ---
    'Mandatory',
    'Optional',
    'ExposesItsArray',
    'OptionalPlaceholder',
    'MandatoryPlaceholder',
    # --- The two standard DataTypeEncoding Objects ---
    'Default Binary',
    'Default XML',
]


def local_name(elem):
    """Return the namespace-stripped tag of `elem`."""
    tag = elem.tag
    return tag.split('}', 1)[1] if '}' in tag else tag


def browse_name(elem):
    """Return a node's BrowseName without its namespace-index prefix.

    NS0 BrowseNames are unprefixed, but being tolerant here means the tool also
    works if it is ever pointed at a companion-specification nodeset.
    """
    raw = elem.get('BrowseName', '')
    return raw.split(':', 1)[1] if ':' in raw else raw


def is_ns0(node_id):
    """True if `node_id` denotes a Namespace 0 node (no `ns=` prefix)."""
    return node_id is not None and not node_id.startswith('ns=')


class NodesetSubset:
    """Selects a closed subset of NS0 nodes and re-emits it as a UANodeSet."""

    def __init__(self, source):
        self.tree = ET.parse(source)
        self.root = self.tree.getroot()
        # Alias -> NodeId, so References written as ReferenceType="HasSubtype"
        # can be resolved the same way as ones written as ReferenceType="i=45".
        self.aliases = {
            alias.get('Alias'): (alias.text or '').strip()
            for alias in self.root.findall('ua:Aliases/ua:Alias', NS)
        }
        self.by_node_id = {}
        self.by_browse_name = {}
        for elem in self.root:
            if local_name(elem) not in NODE_ELEMENTS:
                continue
            node_id = elem.get('NodeId')
            self.by_node_id[node_id] = elem
            # First definition wins: NS0 BrowseNames are unique, and this keeps
            # the mapping deterministic if a nodeset ever repeats one.
            self.by_browse_name.setdefault(browse_name(elem), node_id)

    def resolve_reference_type(self, value):
        """Map a Reference's ReferenceType attribute (alias or NodeId) to a NodeId."""
        return self.aliases.get(value, value)

    def structural_targets(self, elem):
        """Yield the NodeIds `elem` cannot be interpreted without.

        See the module docstring: supertype, type definition, and the DataTypes
        named by the node's own attribute or by its Definition fields.
        """
        for ref in elem.findall('ua:References/ua:Reference', NS):
            ref_type = self.resolve_reference_type(ref.get('ReferenceType'))
            ref_name = browse_name_of_reference(self, ref_type)
            if ref_name in STRUCTURAL_REFERENCE_ALIASES:
                target = (ref.text or '').strip()
                if is_ns0(target):
                    yield target

        data_type = elem.get('DataType')
        if data_type is not None:
            resolved = self.aliases.get(data_type, data_type)
            if is_ns0(resolved):
                yield resolved

        for field in elem.findall('ua:Definition/ua:Field', NS):
            field_type = field.get('DataType')
            if field_type is None:
                continue
            resolved = self.aliases.get(field_type, field_type)
            if is_ns0(resolved):
                yield resolved

    def close_over(self, seed_node_ids):
        """Return the transitive closure of `seed_node_ids` under structural_targets."""
        selected = set()
        pending = list(seed_node_ids)
        while pending:
            node_id = pending.pop()
            if node_id in selected:
                continue
            elem = self.by_node_id.get(node_id)
            if elem is None:
                # A structural target outside the source nodeset would make the
                # subset unusable, so surface it instead of emitting a dangling
                # reference that only fails later inside nodeset2owl.py.
                raise KeyError(f'NodeId {node_id} referenced but not present in the source nodeset')
            selected.add(node_id)
            pending.extend(self.structural_targets(elem))
        return selected

    def seed_ids(self, browse_names):
        """Resolve seed BrowseNames to NodeIds, reporting every unknown name at once."""
        resolved, missing = [], []
        for name in browse_names:
            node_id = self.by_browse_name.get(name)
            (missing if node_id is None else resolved).append(name if node_id is None else node_id)
        if missing:
            raise KeyError('BrowseName(s) not found in source nodeset: ' + ', '.join(missing))
        return resolved

    def build(self, selected):
        """Build the output UANodeSet element tree for the `selected` NodeIds."""
        out = ET.Element('UANodeSet', {'xmlns': UA_NS})

        models = ET.SubElement(out, 'Models')
        ET.SubElement(models, 'Model', {
            'ModelUri': 'http://opcfoundation.org/UA/',
            'Version': '1.05.03',
            'PublicationDate': '2023-12-15T00:00:00Z',
        })

        # Only emit aliases that are actually used by a retained reference, so
        # the subset does not carry a wall of dead alias definitions.
        used_reference_types = set()
        for node_id in selected:
            for ref in self.by_node_id[node_id].findall('ua:References/ua:Reference', NS):
                ref_type = self.resolve_reference_type(ref.get('ReferenceType'))
                target = (ref.text or '').strip()
                if target in selected and browse_name_of_reference(self, ref_type) in STRUCTURAL_REFERENCE_ALIASES:
                    used_reference_types.add(ref_type)

        aliases_elem = ET.SubElement(out, 'Aliases')
        for alias, node_id in sorted(self.aliases.items()):
            if node_id in used_reference_types or node_id in selected:
                alias_elem = ET.SubElement(aliases_elem, 'Alias', {'Alias': alias})
                alias_elem.text = node_id

        for element_name in NODE_ELEMENTS:
            for elem in self.root:
                if local_name(elem) != element_name or elem.get('NodeId') not in selected:
                    continue
                out.append(self.prune(elem, selected))
        return out

    def prune(self, elem, selected):
        """Copy `elem`, keeping only structural references to nodes in `selected`."""
        copy = ET.Element(local_name(elem), dict(elem.attrib))

        display_name = elem.find('ua:DisplayName', NS)
        text = display_name.text if display_name is not None else browse_name(elem)
        ET.SubElement(copy, 'DisplayName').text = text

        # InverseName is mandatory for non-symmetric ReferenceTypes, and AS-018
        # is about exactly that attribute, so it must survive pruning.
        inverse_name = elem.find('ua:InverseName', NS)
        if inverse_name is not None:
            ET.SubElement(copy, 'InverseName').text = inverse_name.text

        definition = elem.find('ua:Definition', NS)
        if definition is not None:
            copy.append(strip_namespaces(definition))

        references = ET.SubElement(copy, 'References')
        for ref in elem.findall('ua:References/ua:Reference', NS):
            ref_type = self.resolve_reference_type(ref.get('ReferenceType'))
            target = (ref.text or '').strip()
            if target not in selected:
                continue
            if browse_name_of_reference(self, ref_type) not in STRUCTURAL_REFERENCE_ALIASES:
                continue
            attrib = {'ReferenceType': ref.get('ReferenceType')}
            if ref.get('IsForward') is not None:
                attrib['IsForward'] = ref.get('IsForward')
            ET.SubElement(references, 'Reference', attrib).text = target
        return copy


def browse_name_of_reference(subset, node_id):
    """Return the BrowseName of the ReferenceType node `node_id`, or ''."""
    elem = subset.by_node_id.get(node_id)
    return browse_name(elem) if elem is not None else ''


def strip_namespaces(elem):
    """Deep-copy `elem` with all XML namespaces removed from tags."""
    copy = ET.Element(local_name(elem), dict(elem.attrib))
    copy.text = elem.text
    for child in elem:
        copy.append(strip_namespaces(child))
    return copy


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('source', help='Path to the official Opc.Ua.NodeSet2.xml')
    parser.add_argument('-o', '--output', required=True, help='Path of the subset nodeset to write')
    args = parser.parse_args()

    subset = NodesetSubset(args.source)
    try:
        selected = subset.close_over(subset.seed_ids(SEED_BROWSE_NAMES))
    except KeyError as err:
        print(f'Error: {err}', file=sys.stderr)
        return 1

    out = subset.build(selected)
    ET.indent(out, space='  ')
    header = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!--\n'
        '  GENERATED FILE - do not edit by hand.\n'
        '\n'
        '  A minimal, faithful subset of OPC UA Namespace 0, extracted from the official\n'
        '  Opc.Ua.NodeSet2.xml by validation/tools/make_ns0_subset.py. It exists so that\n'
        '  the per-rule fixtures under validation/specs/*/testcases/ stay hermetic and\n'
        '  small while still being written against the real NS0 NodeIds and hierarchies.\n'
        '\n'
        '  To add a node: extend SEED_BROWSE_NAMES in the tool and re-run it.\n'
        '-->\n'
    )
    Path(args.output).write_text(header + ET.tostring(out, encoding='unicode') + '\n')
    print(f'Wrote {len(selected)} nodes to {args.output}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
