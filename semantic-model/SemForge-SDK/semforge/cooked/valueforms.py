#
# Copyright (c) 2026 IndustryFusion Foundation
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

"""What an attribute's value may be: its forms, each with its own conditions.

An NGSI-LD attribute carries its value in one of several forms -- a Property's
`value`, a Relationship's `object`, a JsonProperty's `json`, a ListProperty's
`valueList`, … SHACL may allow any choice of them, and each its own
conditions: "a single boolean, or a list of numbers", "a Property or a
JsonProperty". The OPC UA tools write one such choice for every Variable
(a value, or a list of the same); cooked/payloads.py reads them.

Here a value is a list of Forms. Each Form names its payload (and so its
kind), its counts, whether a list may be empty, and an expression tree
(cooked/expression.py) for what the value -- or each item of a list -- must
be. Written back:

- no form: no value layer at all (any value);
- one form: one value layer, `sh:property [ sh:path ngsild:hasValue ; … ]`,
  as nearly every attribute is written by hand -- and edited where it stands
  when it was one already;
- several: the choice of value layers, `sh:or ( [ sh:property [ … ] ] … )`.

What the reader cannot say exactly -- an sh:or of something else, a comment
inside, a value layer with conditions it does not know -- is refused as a
whole, never half-edited. Every write is read back first: it must say what
was meant.
"""

from dataclasses import dataclass, replace

from rdflib import URIRef
from rdflib.namespace import SH

from ..errors import PackageError
from ..ngsild.kinds import LIST_PAYLOADS, NGSILD, PAYLOAD_NAME
from .expression import (Leaf, Op, _apply, _canonical, _conditions, _read_root, _split,
                         _uncommented, _value, describe, normalize_root, to_json)

# The kinds a form may be, in the order a reader thinks of them; each has its
# payload. GeoProperty shares hasValue with Property, and is not offered.
KINDS = ('Property', 'Relationship', 'JsonProperty', 'ListProperty', 'ListRelationship',
         'LanguageProperty', 'VocabProperty')
KIND_OF = {PAYLOAD_NAME[k]: k for k in KINDS}
WORDS = {'hasValue': 'one value', 'hasObject': 'one entity', 'hasJSON': 'JSON',
         'hasValueList': 'a list of values', 'hasObjectList': 'a list of entities',
         'hasLanguageMap': 'text by language', 'hasVocab': 'a vocabulary term'}


@dataclass(frozen=True)
class Form:
    payload: str                 # hasValue | hasObject | hasJSON | hasValueList | …
    root: Op                     # what the value, or each item of a list, must be
    least: str = '1'             # sh:minCount of the payload
    most: str = '1'              # sh:maxCount of the payload
    may_be_empty: bool = False   # a list that may be ()
    encoded: bool = True         # writes the one value's sh:nodeKind (literal / IRI)

    @property
    def kind(self):
        return KIND_OF.get(self.payload, self.payload)

    @property
    def is_list(self):
        return NGSILD + self.payload in LIST_PAYLOADS


@dataclass(frozen=True)
class Value:
    forms: tuple
    where: str                   # 'slot' (one value layer) | 'attribute' (sh:or) | ''
    slot: str = ''               # the value layer's sh:path as written, when 'slot'
    editable: bool = True
    reason: str = ''


def _form(alternative, prefixes, spell):
    """A Form from what payloads.py read; (Form, why not editable)."""
    from rdflib.namespace import SH as shacl

    member = [(k, v) for k, v in alternative.member if k != 'sh:nodeKind']
    body = '[ ' + ' ; '.join(f'<{shacl}{k[3:]}> {v}' for k, v in member) + ' ]'
    root, reason = _read_root(body, prefixes, spell)
    return Form(payload=alternative.payload, root=root, least=alternative.least or '',
                most=alternative.most or '', may_be_empty=alternative.may_be_empty,
                encoded='sh:nodeKind' in dict(alternative.member)), reason


def read_value(package, text, shape, chain):
    """The value of the attribute at `chain` of `shape`, as forms."""
    from .constrain import _group_in, _turtle_name, _value_slot
    from .payloads import alternatives, prefixes_of

    group = _group_in(text, shape, chain)
    prefixes = prefixes_of(package)

    def spell(iri):
        return _turtle_name(text, iri)

    choice = group.parameter(_turtle_name(text, SH['or']))
    slot = _value_slot(package, group)
    if choice is not None and slot is not None:
        return Value((), 'attribute', editable=False,
                     reason='its value is said both by an sh:or and by a value layer')
    if choice is not None:
        found = alternatives(choice[2], prefixes)
        if not found:
            return Value((), 'attribute', editable=False,
                         reason='its sh:or is not a choice of value forms')
        written = text[choice[0]:choice[1]]
    elif slot is not None:
        layer = _group_in(text, shape, chain + [slot])
        written = text[layer.start:layer.end]
        # One value layer is one form: read by the same reader, as a choice of one.
        found = alternatives(f'( [ <{SH.property}> {written} ] )', prefixes)
        if not found:
            return Value((), 'slot', slot, editable=False,
                         reason='its value layer says something SemForge does not edit here')
    else:
        return Value((), '')
    forms, reasons = [], []
    for alternative in found:
        form, reason = _form(alternative, prefixes, spell)
        forms.append(form)
        reasons.append(reason)
    reason = next((r for r in reasons if r), '')
    if not reason and not _uncommented(written):
        reason = 'a comment inside it would be lost'
    return Value(tuple(forms), 'attribute' if choice is not None else 'slot', slot or '',
                 editable=not reason, reason=reason)


# --- writing -------------------------------------------------------------------------------

def _literals_and_iris(node):
    """(says a literal, says an IRI) anywhere in the tree."""
    literal = iri = False
    if isinstance(node, Op):
        for child in node.children:
            more = _literals_and_iris(child)
            literal, iri = literal or more[0], iri or more[1]
    elif isinstance(node, Leaf):
        keys = dict(node.conditions)
        literal = 'sh:datatype' in keys or any(k in keys for k in (
            'sh:minLength', 'sh:maxLength', 'sh:pattern', 'sh:minInclusive', 'sh:maxInclusive',
            'sh:minExclusive', 'sh:maxExclusive'))
        iri = 'sh:class' in keys
        value = keys.get('sh:hasValue')
        if value is not None:
            if value.startswith(('"', "'")) or value[:1].isdigit() or value[:1] in '+-' or \
                    value in ('true', 'false'):
                literal = True
            else:
                iri = True
    return literal, iri


def _encoding(form, name):
    """The one value's sh:nodeKind, said again from what it must be: an entity
    is an IRI; a value a literal when every branch says one, an IRI when every
    branch says a class or term; neither when it may be both."""
    if not form.encoded or form.is_list:
        return []
    if form.payload == 'hasObject':
        return [('sh:nodeKind', name(SH.IRI))]
    if form.payload != 'hasValue':
        return []
    literal, iri = _literals_and_iris(form.root)
    if literal and not iri:
        return [('sh:nodeKind', name(SH.Literal))]
    if iri and not literal:
        return [('sh:nodeKind', name(SH.IRI))]
    return []


def _alternative(form, name):
    from .payloads import Alternative

    own, params = _split(normalize_root(form.root))
    member = list(own.conditions) + [(f'sh:{op}', _value(node, name)) for op, node in params] + \
        _encoding(form, name)
    return Alternative(payload=form.payload, kind=form.kind, member=tuple(sorted(member)),
                       least=form.least, most=form.most, may_be_empty=form.may_be_empty)


def _same(one, other, prefixes, spell):
    """Do two Values say the same, once written and read back?"""
    if len(one.forms) != len(other.forms):
        return False
    for a, b in zip(one.forms, other.forms):
        if (a.payload, a.least, a.most, a.may_be_empty) != \
                (b.payload, b.least, b.most, b.may_be_empty):
            return False
        if normalize_root(a.root) != _canonical(b.root, prefixes, spell):
            return False
    return True


def write_value(package, shape, chain, forms):
    """Write `forms` as the value of the attribute at `chain`; {'file', 'line'}.
    Refuses -- and changes nothing -- unless it reads back as meant."""
    from .constrain import _add_line, _group_in, _remove_line, _set, _turtle_name
    from .expression import write_layer
    from .payloads import _layer, prefixes_of, render
    from .remove_attribute import _remove_span
    from .tree import _write_verified

    shape, chain = str(shape), list(chain)
    holder = package.index('shapes').file_for(URIRef(shape))
    if holder is None:
        raise PackageError(f'{shape} is not in any shapes file')
    with open(holder, encoding='utf-8') as handle:
        text = handle.read()
    before = read_value(package, text, shape, chain)
    if not before.editable:
        raise PackageError(f'the value of {chain[-1]} is edited in the .ttl: {before.reason}')
    payloads = [f.payload for f in forms]
    if len(set(payloads)) != len(payloads):
        raise PackageError('each form once: two of the same kind say nothing a single one '
                           'does not')
    forms = tuple(replace(f, root=normalize_root(f.root)) for f in forms)

    def name(iri):
        return _turtle_name(text, iri)

    old = before.forms
    if before.where == 'slot' and len(forms) == 1 and len(old) == 1 and \
            (forms[0].payload, forms[0].least, forms[0].most) == \
            (old[0].payload, old[0].least, old[0].most) and not forms[0].is_list:
        # One value layer, still one: changed where it stands, comments and all.
        form = forms[0]
        own, *rest = form.root.children
        root = Op('and', (Leaf(tuple(sorted(own.conditions + tuple(_encoding(form, name))))),)
                  + tuple(rest))
        made = write_layer(package, shape, chain, root)
    else:
        group = _group_in(text, shape, chain)
        if before.where == 'slot':
            layer = _group_in(text, shape, chain + [before.slot])
            text = _remove_span(text, layer, group.start, group.end)
        elif before.where == 'attribute':
            text = _remove_line(text, group, _turtle_name(text, SH['or']))
        alternatives = tuple(_alternative(f, name) for f in forms)
        group = _group_in(text, shape, chain)
        if len(alternatives) == 1:
            text = _add_line(text, group, _turtle_name(text, SH.property),
                             f'[ {_layer(alternatives[0], name)} ]')
        elif alternatives:
            from .constrain import _indent_of

            text = _set(text, group, _turtle_name(text, SH['or']),
                        render(alternatives, name, _indent_of(text, group.start)))
        made = None
    if made is None:
        after = read_value(package, text, shape, chain)
        if not _same(after, Value(forms, ''), prefixes_of(package), name):
            raise PackageError('the value would not read back as meant; nothing was changed')
        _write_verified(holder, text)
        group = _group_in(text, shape, chain)
        made = {'file': holder, 'line': text.count('\n', 0, group.start) + 1}
    return made


# --- the edits the panel asks for ------------------------------------------------------------

def edit_value(package, shape, chain, action):
    """One change to the value's forms, or to what one form must be.

    action: {'op': 'addform' (kind) | 'removeform' | 'formkind' (kind) |
    'empty' (value: bool) | any edit of cooked/expression.py, 'form': index}.
    """
    holder = package.index('shapes').file_for(URIRef(str(shape)))
    if holder is None:
        raise PackageError(f'{shape} is not in any shapes file')
    with open(holder, encoding='utf-8') as handle:
        text = handle.read()
    value = read_value(package, text, str(shape), list(chain))
    if not value.editable:
        raise PackageError(f'the value of {chain[-1]} is edited in the .ttl: {value.reason}')
    forms = list(value.forms)
    what = action.get('op')

    def at():
        index = int(action.get('form') if action.get('form') is not None else -1)
        if not 0 <= index < len(forms):
            raise PackageError('that form is not there any more')
        return index

    def payload_for(kind):
        if kind not in KINDS:
            raise PackageError(f'{kind} is not a kind a value may take here')
        return PAYLOAD_NAME[kind]

    if what == 'addform':
        payload = payload_for(action.get('kind'))
        forms.append(Form(payload=payload, root=Op('and', (Leaf(),)),
                          may_be_empty=NGSILD + payload in LIST_PAYLOADS))
    elif what == 'removeform':
        del forms[at()]
    elif what == 'formkind':
        index = at()
        payload = payload_for(action.get('kind'))
        forms[index] = replace(forms[index], payload=payload,
                               may_be_empty=NGSILD + payload in LIST_PAYLOADS and
                               forms[index].may_be_empty)
    elif what == 'empty':
        index = at()
        if not forms[index].is_list:
            raise PackageError('only a list may be empty')
        forms[index] = replace(forms[index], may_be_empty=bool(action.get('value')))
    else:
        index = at()
        forms[index] = replace(forms[index], root=_apply(
            forms[index].root, action, _conditions(package, text, action)))
    return write_value(package, shape, chain, tuple(forms))


# --- said ----------------------------------------------------------------------------------

def form_words(form):
    said = describe(_Layered(form.root), 'Relationship' if form.payload in (
        'hasObject', 'hasObjectList') else 'Property') or 'any value'
    head = WORDS.get(form.payload, form.payload)
    tail = ' (may be empty)' if form.may_be_empty else ''
    return f'{head}{tail}: {said}'


def member_words(params, kind, prefixes, spell):
    """What one form's member must be, in words -- for the type page, where
    each form of a choice says its own conditions, expressions included."""
    from rdflib.namespace import SH as shacl

    body = '[ ' + ' ; '.join(f'<{shacl}{k[3:]}> {v}' for k, v in params.items()
                             if k != 'sh:nodeKind') + ' ]'
    root, _ = _read_root(body, prefixes, spell)
    return describe(_Layered(root), kind) or 'any value'


class _Layered:
    """describe() reads a layer's root; a form has one too."""

    def __init__(self, root):
        self.root = normalize_root(root)


def value_words(value):
    if not value.forms:
        return 'any value'
    return ', or '.join(form_words(f) for f in value.forms)


def to_payload(value):
    """The value as the panel draws it."""
    return {'forms': [{'kind': f.kind, 'payload': f'ngsi-ld:{f.payload}', 'list': f.is_list,
                       'mayBeEmpty': f.may_be_empty, 'said': form_words(f),
                       'expression': to_json(normalize_root(f.root),
                                             'Relationship' if f.payload in (
                                                 'hasObject', 'hasObjectList') else 'Property')}
                      for f in value.forms],
            'said': value_words(value), 'editable': value.editable, 'reason': value.reason,
            'kinds': list(KINDS)}
