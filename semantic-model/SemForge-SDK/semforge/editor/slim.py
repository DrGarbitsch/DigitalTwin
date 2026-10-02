"""The trees in summary form: one row per meaningful thing, said once.

The full trees print the SHACL encoding a parameter per row, repeat every
value in the row's description, and prefix almost every label with a
namespace the reader already knows -- 192 rows for the kms's constraints,
nine levels in the model. The entity type page is now where a type is READ
and edited; the trees' job is to FIND things. So this pass, applied to the
payloads the server already builds, keeps the structure and drops the noise:

  Constraints  parameter and value-layer rows fold into the attribute row's
               description, in the type page's vocabulary
               ("required · one · → FilterCartridge"); a type row says how
               many attributes and rules it has.
  Model        the read-only `type` row folds into the entity row; a value
               is said once, without the attribute's kind after it.
  Knowledge    "ShapeA + ShapeB + ShapeC" becomes "3 shapes"; an entity id
               that appears in several files is one row, its files beneath.
  Everywhere   a prefix is dropped where the local name is unambiguous in
               that tree (the two CartridgeShapes keep theirs).

It works on the serialised dicts, so the builders and everything that tests
them are untouched, and `full` mode is exactly what it always was.
"""

import copy
import re

from ..cooked.typepage import presence, value_text

CURIE = re.compile(r'(?<![\w/#:.-])([A-Za-z][\w.-]*):([A-Za-z_][\w.-]*)')
KIND_WORDS = {'Property', 'Relationship', 'GeoProperty', 'JsonProperty',
              'ListProperty', 'LanguageProperty', 'VocabProperty'}


# --- prefixes -------------------------------------------------------------------

def _locals(nodes, found=None):
    """{local name: {prefix}} over every label and description in a tree."""
    found = {} if found is None else found
    for node in nodes:
        for text in (node.get('label', ''), node.get('detail', ''),
                     node.get('value', '')):
            for prefix, name in CURIE.findall(str(text or '')):
                if prefix not in ('urn', 'http', 'https'):
                    found.setdefault(name, set()).add(prefix)
        _locals(node.get('children', []), found)
    return found


def _shorten(text, unique):
    def replace(match):
        prefix, name = match.group(1), match.group(2)
        if prefix in ('urn', 'http', 'https') or name not in unique:
            return match.group(0)
        return name
    return CURIE.sub(replace, str(text))


def drop_prefixes(nodes):
    """Labels and descriptions without the prefix wherever the local name is
    unambiguous in this tree. The full term stays in `term` for tooltips."""
    names = _locals(nodes)
    unique = {name for name, prefixes in names.items() if len(prefixes) == 1}

    def walk(node):
        for key in ('label', 'detail'):
            if not node.get(key):
                continue
            shortened = _shorten(node[key], unique)
            if shortened == node[key]:
                continue
            if key == 'label':
                node.setdefault('term', node[key])
            node[key] = shortened
        for child in node.get('children', []):
            walk(child)
    for node in nodes:
        walk(node)
    return nodes


# --- constraints -------------------------------------------------------------------

def _summary(node):
    """'required · one · → FilterCartridge' from an attribute node's children."""
    own = {c['parameter']: c['value'] for c in node.get('children', [])
           if c.get('kind') == 'constraint' and c.get('parameter')}
    slot = next((c for c in node.get('children', []) if c.get('kind') == 'slot'), None)
    value = {}
    raw = []
    if slot is not None:
        for child in slot.get('children', []):
            if child.get('kind') == 'constraint' and child.get('parameter'):
                value[child['parameter']] = child['value']
            elif child.get('kind') == 'raw':
                raw.append((child['label'].replace(' (raw only)', ''),
                            child.get('value', '')))
    kind = 'Relationship' if slot is not None and \
        str(slot.get('detail', '')).endswith('hasObject') else 'Property'
    said = presence(own.get('sh:minCount'), own.get('sh:maxCount'))
    if slot is not None:
        said += ' · ' + value_text(kind, value, raw)
    return said


def _inverse_of(node):
    """The attribute an inverse path walks back over, or ''."""
    text = ' '.join(str(node.get(key, '')) for key in ('label', 'detail'))
    if 'inversePath' not in text and '] )' not in text:
        return ''
    names = [name.split(':')[-1] for name in
             re.findall(r'sh:inversePath\s+([\w.:-]+)', text)
             if not name.startswith('ngsild:')]
    if not names:
        names = [w.split(':')[-1] for w in re.findall(r'[\w.-]+:[\w.-]+', text)
                 if not w.startswith(('ngsild:', 'sh:'))]
    return names[-1] if names else ''


def _count(node, kind):
    return sum((1 if child.get('kind') == kind else 0) + _count(child, kind)
               for child in node.get('children', []))


def slim_constraints(roots):
    roots = copy.deepcopy(roots)

    def walk(node):
        if node.get('kind') == 'attribute':
            summary = _summary(node)
            origin = node.get('inheritedClass', '')
            inverse = _inverse_of(node)
            if inverse:
                # A path walked backwards -- the kms's "one cartridge per
                # filter" rule. Its label in the full tree is the raw path.
                node['term'] = node.get('label')
                node['label'] = f'← {inverse}'
                summary = f'inverse path · {summary}'
            node['detail'] = summary + (f' · from {origin.rsplit("/", 1)[-1]}'
                                        if node.get('inheritedFrom') and origin else '')
            node['children'] = [c for c in node.get('children', [])
                                if c.get('kind') == 'attribute']
        else:
            node['children'] = [c for c in node.get('children', [])
                                if c.get('kind') not in ('constraint', 'slot')]
            if node.get('kind') == 'shape' and node['children'] and all(
                    c.get('kind') == 'raw' for c in node['children']):
                # A shape that is only a query: one row saying so, rather than
                # "0 attribute(s)" over a row explaining it is not a form.
                node['detail'] = ' · '.join(
                    c['label'] for c in node['children']) + \
                    (f' · {node["detail"].split(" — ")[0]}'
                     if node.get('inheritedFrom') else '')
                node['children'] = []
        for child in node['children']:
            walk(child)

    for root in roots:
        # Counted before the fold: rule rows become their shape's description.
        rules = sum(1 for shape in root.get('children', [])
                    for child in shape.get('children', [])
                    if child.get('kind') == 'raw')
        walk(root)
        attributes = _count(root, 'attribute')
        root['detail'] = ' · '.join(part for part in (
            f'{attributes} attribute(s)' if attributes else '',
            f'{rules} rule(s)' if rules else '') if part) or 'nothing constrained'
    return drop_prefixes(roots)


# --- the model ------------------------------------------------------------------------

def _value_once(detail):
    """'base:state_ON · Property · 1 violation(s)' -> 'base:state_ON · 1 violation(s)'.

    A plain string value loses its JSON quotes: `"urn:cartridge:1"` reads as
    urn:cartridge:1 in a tree, and the quotes said nothing a reader needs."""
    parts = [part for part in str(detail or '').split(' · ')
             if part.strip() not in KIND_WORDS]
    if parts and re.fullmatch(r'"[^"\\]*"', parts[0].strip()):
        parts[0] = parts[0].strip()[1:-1]
    return ' · '.join(parts)


def slim_model(roots):
    roots = copy.deepcopy(roots)

    def walk(node):
        node['children'] = [c for c in node.get('children', [])
                            if c.get('kind') != 'type']
        if node.get('kind') in ('attribute', 'instance', 'dataset'):
            node['detail'] = _value_once(node.get('detail'))
        for child in node['children']:
            walk(child)

    for root in roots:
        walk(root)
    return drop_prefixes(roots)


# --- the knowledge -----------------------------------------------------------------------

def _shape_count(detail):
    """'ShapeA + ShapeB · 3 instance(s)' -> '2 shape(s) · 3 instance(s)'."""
    parts = str(detail or '').split(' · ')
    if parts and parts[0] and ('Shape' in parts[0] or ' + ' in parts[0]):
        count = len(parts[0].split(' + '))
        parts[0] = f'{count} shape(s)' if count > 1 else parts[0]
    return ' · '.join(parts)


def slim_knowledge(roots):
    roots = copy.deepcopy(roots)

    def walk(node):
        if node.get('kind') == 'class':
            node['detail'] = _shape_count(node.get('detail'))
        children = node.get('children', [])
        grouped, order = {}, []
        for child in children:
            if child.get('kind') == 'instance':
                if child['label'] not in grouped:
                    grouped[child['label']] = []
                    order.append(('instance', child['label']))
                grouped[child['label']].append(child)
            else:
                order.append(('node', child))
        rebuilt = []
        for what, item in order:
            if what == 'node':
                rebuilt.append(item)
                continue
            places = grouped[item]
            if len(places) == 1:
                rebuilt.append(places[0])
                continue
            # One id, several files: one row, the files beneath it. The row
            # keeps the first file's location so a click still lands somewhere.
            row = dict(places[0])
            row['detail'] = f'in {len(places)} files'
            row['children'] = [dict(place, label=place.get('detail') or place['label'],
                                    detail='') for place in places]
            rebuilt.append(row)
        node['children'] = rebuilt
        for child in node['children']:
            walk(child)

    for root in roots:
        walk(root)
    return drop_prefixes(roots)


SLIM = {'constraints': slim_constraints, 'model': slim_model,
        'knowledge': slim_knowledge}
