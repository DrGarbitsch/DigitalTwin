"""Completion and hover for a SPARQL query of this package.

Completion reads what is being typed and what comes before it:

  * after PREFIX -- the package's namespaces, written out (`iffBaseEntities:
    <https://…>`);
  * `prefix:` -- that namespace's terms: classes, attributes (with Property or
    Relationship), individuals; a prefix the query has not declared yet is
    declared by the completion itself (its PREFIX line is added);
  * an attribute where a predicate goes also comes as the whole NGSI-LD step,
    `iffBaseEntities:hasState [ ngsild:hasValue ?state ]` -- hasValue for a
    Property, hasObject for a Relationship;
  * `?` or `$` -- the query's variables, and $this;
  * anything else -- keywords, built-in functions, and the prefixes.
"""

from .lexer import (FUNCTIONS, KEYWORDS, at, code_tokens, declared_prefixes,
                    prologue_end)
from .terms import NGSILD

WORD = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-?$%')
LAYER = {'Property': 'hasValue', 'Relationship': 'hasObject',
         'ListProperty': 'hasValueList', 'ListRelationship': 'hasObjectList',
         'JsonProperty': 'hasJSON'}
KIND = {'class': 'class', 'attribute': 'property', 'individual': 'enum', 'ngsild': 'keyword',
        'property': 'property'}


def _item(label, insert, start, end, kind, detail='', doc='', sort='5', snippet=False,
          edits=(), retrigger=False, filter_text=None):
    return {'label': label, 'insert': insert, 'start': start, 'end': end, 'kind': kind,
            'detail': detail, 'documentation': doc, 'sort': f'{sort}{label.lower()}',
            'snippet': snippet, 'edits': list(edits), 'retrigger': retrigger,
            'filter': filter_text or label}


def _word(text, offset):
    start = offset
    while start > 0 and text[start - 1] in WORD:
        start -= 1
    return start, text[start:offset]


def _declare(text, prefix, namespace):
    """The edit that declares a prefix: a PREFIX line where the others are."""
    at_offset = prologue_end(text)
    return (at_offset, at_offset, f'PREFIX {prefix}: <{namespace}>\n')


def _predicate_position(code, start):
    """Is the word at `start` where a predicate goes (after a subject, `;`)?"""
    before = [t for t in code if t.end <= start]
    if not before:
        return False
    last = before[-1]
    if last.text == ';':
        return True
    if last.kind in ('var', 'pname', 'iri') or last.text == ']':
        earlier = before[-2] if len(before) > 1 else None
        return earlier is None or earlier.text in ('.', '{', ';', '}') or \
            (earlier.kind == 'comment')
    return False


def complete(text, offset, terms):
    """[item] for the cursor at `offset`; each item says what it replaces."""
    start, word = _word(text, offset)
    code = code_tokens(text)
    before = [t for t in code if t.end <= start]
    declared = declared_prefixes(text)
    items = []

    if before and before[-1].kind == 'name' and before[-1].upper == 'PREFIX':
        for prefix, namespace in sorted(terms.namespaces.items()):
            if prefix in declared:
                continue
            items.append(_item(f'{prefix}:', f'{prefix}: <{namespace}>', start, offset,
                               'module', namespace, sort='1'))
        return items

    if word.startswith(('?', '$')):
        names = {t.text[1:] for t in code if t.kind == 'var' and t.start != start}
        names.add('this')
        for name in sorted(names):
            items.append(_item(f'{word[0]}{name}', f'{word[0]}{name}', start, offset,
                               'variable', '$this: each node the shape selects'
                               if name == 'this' else 'variable', sort='1'))
        return items

    if ':' in word:
        prefix, _, local = word.partition(':')
        namespace = declared.get(prefix) or terms.namespaces.get(prefix)
        if not namespace:
            return []
        edits = [] if prefix in declared else [_declare(text, prefix, namespace)]
        predicate = _predicate_position(code, start)
        for term in sorted(terms.in_namespace(namespace), key=lambda t: t.local.lower()):
            name = f'{prefix}:{term.local}'
            doc = '\n\n'.join(p for p in (term.comment, f'<{term.iri}>') if p)
            rank = {'attribute': '1', 'class': '2', 'individual': '3'}.get(term.kind, '4')
            items.append(_item(name, name, start, offset, KIND.get(term.kind, 'text'),
                               term.detail, doc, sort=rank, edits=edits))
            if predicate and term.kind == 'attribute' and term.attribute_kind in LAYER:
                ngsild = next((p for p, n in declared.items() if n == NGSILD), None)
                step_edits = list(edits)
                if ngsild is None:
                    ngsild = 'ngsild'
                    step_edits.append(_declare(text, 'ngsild', NGSILD))
                variable = term.local[3:4].lower() + term.local[4:] \
                    if term.local.startswith('has') and len(term.local) > 3 else term.local
                layer = LAYER[term.attribute_kind]
                items.append(_item(
                    f'{name} [ {ngsild}:{layer} ?{variable} ]',
                    f'{name} [ {ngsild}:{layer} ${{1:?{variable}}} ]', start, offset,
                    'snippet', f'{term.attribute_kind}: its '
                    f'{"target" if "Relationship" in term.attribute_kind else "value"}',
                    doc, sort=rank, snippet=True, edits=step_edits, filter_text=name))
        return items

    upper = word.upper()
    for keyword in sorted(KEYWORDS):
        if keyword.startswith(upper):
            items.append(_item(keyword, keyword, start, offset, 'keyword', sort='2'))
    for function in sorted(FUNCTIONS):
        if function.startswith(upper):
            items.append(_item(f'{function}()', f'{function}($1)', start, offset, 'function',
                               'built-in function', sort='3', snippet=True,
                               filter_text=function))
    for prefix, namespace in sorted(terms.namespaces.items()):
        if prefix.lower().startswith(word.lower()):
            edits = [] if prefix in declared else [_declare(text, prefix, namespace)]
            items.append(_item(f'{prefix}:', f'{prefix}:', start, offset, 'module', namespace,
                               sort='1' if prefix in declared else '4', edits=edits,
                               retrigger=True))
    return items


def hover(text, offset, terms):
    """Markdown for what is under the cursor: a name's full IRI and what the
    knowledge says about it."""
    token = at(text, offset)
    if token is None:
        return None
    if token.kind == 'pname':
        prefix, _, local = token.text.partition(':')
        namespace = declared_prefixes(text).get(prefix) or terms.namespaces.get(prefix)
        if not namespace:
            return f'`{prefix}:` is not a prefix this query or the package declares'
        iri = namespace + local
    elif token.kind == 'iri':
        iri = token.text[1:-1]
    elif token.kind == 'var' and token.text[1:] == 'this':
        return ('**$this** — each node the shape selects, bound by the SHACL engine before '
                'the query runs (one run per node)')
    else:
        return None
    term = terms.terms.get(iri)
    if term is None:
        said = ('not declared in the knowledge' if terms.own(iri) else
                'a term from outside this package')
        return f'`<{iri}>`\n\n{said}'
    lines = [f'**{term.local}** · {term.detail}', f'`<{iri}>`']
    if term.comment:
        lines.append(term.comment)
    if term.kind == 'attribute' and term.attribute_kind in LAYER:
        lines.append(f'Read its {"target" if "Relationship" in term.attribute_kind else "value"}'
                     f' as `[ ngsild:{LAYER[term.attribute_kind]} ?x ]`')
    return '\n\n'.join(lines)
