"""Sanity: references that point at nothing, and declarations nothing uses.

Every artifact of a package names terms the others are supposed to define, and
each of those links can break without anything failing. A `sh:path` to an
attribute the knowledge no longer declares still parses, still validates, and
still selects whatever data happens to carry the key -- it has simply stopped
meaning anything the package can explain. A SPARQL body that reads a removed
attribute matches nothing, which reads exactly like a rule that is satisfied.
An expectation that asserts a constraint which no longer exists fails, but it
says "did not fire", which sends the reader looking for a data problem.

So this is the cross-artifact check, one finding per broken link, placed on the
line that holds it:

  undeclared-path    sh:path names an attribute the knowledge does not declare
  undeclared-class   sh:class / sh:targetClass names an undeclared class
  sparql-undeclared  a SPARQL body names an undeclared term of the package's
                     own namespaces (a warning: a query is checked by token,
                     not by meaning)
  stale-assert       an expectation names a constraint no shape declares
  severity-unknown   an sh:severity that is no severity level: not SHACL's
                     violation/warning/info, nor an individual of sh:Severity
                     or a class derived from it
  severity-unlinked  a class whose individuals are used as severities but which
                     is not declared a kind of sh:Severity (information)
  unused-attribute   a declared attribute nothing uses (information)

Undeclared keys in the DATA are expect.vocabulary's, which predates this and
already places them; `check` reports both.

Each finding carries a `fix` -- what a quick fix needs to act on it -- so the
editor can offer "Declare it", "Remove this use" or "Delete attribute" without
recomputing anything.
"""

import os
from dataclasses import dataclass, field

from rdflib import BNode, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

STANDARD = (str(RDF), str(RDFS), str(OWL), str(XSD), str(SH))
# The predicates whose object is (part of) a property path, so the term right
# after one of them is a path use -- `sh:path X`, `[ sh:inversePath X ]`.
PATH_PREDICATES = {str(SH.path), str(SH.inversePath), str(SH.alternativePath),
                   str(SH.zeroOrMorePath), str(SH.oneOrMorePath),
                   str(SH.zeroOrOnePath)}
NGSILD = 'https://uri.etsi.org/ngsi-ld/'


@dataclass
class SanityFinding:
    file: str
    line: int
    severity: str               # error | warning | information
    code: str                   # undeclared-path | ...
    message: str
    subject: str = ''           # the term the finding is about
    fix: dict = field(default_factory=dict)


# --- what the package declares --------------------------------------------------

def _declared(package):
    """Every IRI the knowledge or the NGSI-LD vocabulary declares."""
    found = {str(s) for s in package.knowledge.subjects(None, None)
             if isinstance(s, URIRef)}
    try:
        found |= {str(s) for s in package.vocabulary.subjects(None, None)
                  if isinstance(s, URIRef)}
    except Exception:                              # noqa: BLE001
        pass
    return found


def _is_standard(iri):
    return iri.startswith(STANDARD) or iri == NGSILD


def _own_namespaces(package):
    """Namespaces the knowledge declares terms in -- the package's own words.

    A SPARQL body is full of IRIs; only those in the package's own namespaces
    are claims about the package. `schema:` or `ex:` in a query is somebody
    else's business.
    """
    from .cooked.knowledge import _namespace_of

    return {_namespace_of(s) for s in package.knowledge.subjects(RDF.type, None)
            if isinstance(s, URIRef)} - {str(n) for n in (RDF, RDFS, OWL, XSD, SH)}


def _path_iris(graph, node, seen=None):
    """Every IRI in a property path: plain, inverse, sequence, alternative."""
    seen = seen if seen is not None else set()
    if isinstance(node, URIRef):
        return {str(node)}
    if not isinstance(node, BNode) or node in seen:
        return set()
    seen.add(node)
    found = set()
    if (node, RDF.first, None) in graph:
        for item in Collection(graph, node):
            found |= _path_iris(graph, item, seen)
        return found
    for predicate in (SH.inversePath, SH.alternativePath, SH.zeroOrMorePath,
                      SH.oneOrMorePath, SH.zeroOrOnePath):
        for inner in graph.objects(node, predicate):
            found |= _path_iris(graph, inner, seen)
    return found


# --- the shapes -----------------------------------------------------------------

def _shape_checks(package, declared):
    """undeclared-path, undeclared-class and sparql-undeclared, placed on the
    exact term in the file that writes it."""
    from .rdfio import terms

    path_iris = set()
    for _, path in package.shapes.subject_objects(SH.path):
        path_iris |= _path_iris(package.shapes, path)
    class_iris = {str(o) for p in (SH['class'], SH.targetClass)
                  for o in package.shapes.objects(None, p) if isinstance(o, URIRef)}
    own = _own_namespaces(package)
    shapes = {str(s) for s in package.shapes.subjects(RDF.type, SH.NodeShape)}

    out = []
    for path in package.files('shapes'):
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
        found = terms(text)
        reported = set()
        for index, term in enumerate(found):
            iri = term.iri
            resolved = '://' in iri or iri.startswith('urn:')
            if not resolved or _is_standard(iri) or iri in declared:
                continue
            previous = found[index - 1].iri if index else ''
            key = (iri, term.line)
            if key in reported:
                continue
            if term.quoted:
                if any(iri.startswith(n) for n in own) and iri not in shapes:
                    reported.add(key)
                    out.append(SanityFinding(
                        file=os.path.abspath(path), line=term.line,
                        severity='warning', code='sparql-undeclared',
                        subject=iri,
                        message=f'{term.raw} is read by this query but the '
                                f'knowledge does not declare it. A query that '
                                f'names a term nothing defines matches nothing '
                                f'-- which reads exactly like a rule that is '
                                f'satisfied.',
                        fix={'declare': iri}))
                continue
            if iri in path_iris and previous in PATH_PREDICATES:
                reported.add(key)
                out.append(SanityFinding(
                    file=os.path.abspath(path), line=term.line,
                    severity='error', code='undeclared-path', subject=iri,
                    message=f'sh:path {term.raw} names an attribute the '
                            f'knowledge does not declare. The constraint still '
                            f'selects whatever data carries the key, but '
                            f'nothing says what it means -- declare it, or '
                            f'remove this property shape.',
                    fix={'declare': iri, 'remove': 'property',
                         'file': os.path.abspath(path), 'offset': term.start}))
            elif iri in class_iris and previous in (str(SH['class']),
                                                    str(SH.targetClass)):
                reported.add(key)
                which = 'sh:targetClass' if previous == str(SH.targetClass) \
                    else 'sh:class'
                out.append(SanityFinding(
                    file=os.path.abspath(path), line=term.line,
                    severity='error', code='undeclared-class', subject=iri,
                    message=f'{which} {term.raw} names a class the knowledge '
                            f'does not declare, so no entity can be typed as '
                            f'it from the model -- '
                            + ('the shape judges nothing.'
                               if which == 'sh:targetClass'
                               else 'the constraint can never be satisfied.')))
    return out


# --- the expectations -----------------------------------------------------------

def known_constraints(package):
    """Every constraint reference an expectation may name."""
    from .validate.applicable import constraints_of_shape
    from .validate.normalise import curie
    from .validate.shapes import targeted_shapes

    out = set()
    for shape in targeted_shapes(package.shapes):
        name = curie(package.shapes, shape)
        for attribute, component in constraints_of_shape(shape, package.shapes):
            out.add(f'{name}/{attribute}/{component}' if attribute
                    else f'{name}/{component}')
    return out


def _assert_lines(source):
    """[(entry path, assert index, line, constraint)] from one expectations
    file, with the line each `constraint:` sits on."""
    from .expect.store import _yaml

    with open(source, encoding='utf-8') as handle:
        raw = _yaml().load(handle) or {}
    out = []
    for entry in raw.get('examples') or []:
        for position, item in enumerate(entry.get('asserts') or []):
            try:
                line = item.lc.line + 1
            except Exception:                      # noqa: BLE001
                line = 1
            out.append((entry.get('path', ''), position, line,
                        str(item.get('constraint', ''))))
    return out


def _expectation_checks(package):
    from .expect.stale import suggestion
    from .expect.store import expectation_files

    known = known_constraints(package)
    out = []
    for source in expectation_files(package.path):
        for path, position, line, constraint in _assert_lines(source):
            if constraint in known:
                continue
            shape = constraint.split('/')[0]
            near = sorted(k for k in known if k.startswith(shape + '/'))
            meant = suggestion(constraint, known)
            hint = (f' {shape} declares: {", ".join(near[:4])}'
                    + (' …' if len(near) > 4 else '')) if near else \
                f' No shape is called {shape}.'
            if meant:
                hint += f' Renamed? {meant} declares the same constraint.'
            out.append(SanityFinding(
                file=os.path.abspath(source), line=line, severity='error',
                code='stale-assert', subject=constraint,
                message=f'{path} asserts {constraint}, a constraint no shape '
                        f'declares -- it can never fire, so this case fails for '
                        f'a reason that has nothing to do with its data.' + hint,
                fix={'remove': 'assert', 'file': os.path.abspath(source),
                     'case': path, 'index': position, 'suggest': meant}))
    return out


# --- declared and unused --------------------------------------------------------

def _unused_attributes(package):
    """Declared NGSI-LD attributes that no shape, query or document names."""
    from .cooked.choices import attribute_terms
    from .editor.references import used_iris

    used = used_iris(package)
    out = []
    index = package.index('knowledge')
    for entry in attribute_terms(package):
        if not entry.ngsild or entry.iri in used:
            continue
        where, block = index.block_for(URIRef(entry.iri))
        if block is None:
            continue
        out.append(SanityFinding(
            file=os.path.abspath(where), line=block.start_line,
            severity='information', code='unused-attribute', subject=entry.iri,
            message=f'{entry.term} is declared but no shape, query or document '
                    f'uses it. Delete it, or constrain it on the type that '
                    f'carries it.',
            fix={'delete': entry.iri}))
    return out


def _severity_checks(package):
    """Severities that are not levels, and classes of levels not linked to
    sh:Severity -- the vocabulary SemForge reads them in."""
    from .cooked.severity import levels, severity_classes
    from .validate.normalise import curie

    def owner(node):
        # Up from a constraint's blank node -- through sh:property, sh:sparql,
        # a list -- to the named shape whose statement holds it.
        seen = set()
        while not isinstance(node, URIRef) and node not in seen:
            seen.add(node)
            node = next(iter(package.shapes.subjects(None, node)), None)
            if node is None:
                return None
        return node

    known = {level['iri'] for level in levels(package)}
    shapes_index = package.index('shapes')
    out = []
    for node, value in sorted(package.shapes.subject_objects(SH.severity), key=str):
        if str(value) in known:
            continue
        shape = owner(node)
        at = shapes_index.locator(str(shape)) if shape is not None else ''
        file, _, line = at.rpartition(':') if at else ('', '', '1')
        name = curie(package.shapes, URIRef(str(value)))
        out.append(SanityFinding(
            file=file or package.files('shapes')[0], line=int(line or 1),
            severity='warning', code='severity-unknown', subject=str(value),
            message=f'{curie(package.shapes, shape) if shape is not None else "a shape"} '
                    f'uses {name} as a severity, which is no severity level: not SHACL\'s '
                    f'violation, warning or info, nor an individual of sh:Severity or of '
                    f'a class derived from it. Declare it as one, or pick a level.'))
    knowledge_index = package.index('knowledge')
    for cls in severity_classes(package):
        if cls['linked']:
            continue
        at = knowledge_index.locator(cls['iri'])
        if not at:
            continue
        file, _, line = at.rpartition(':')
        out.append(SanityFinding(
            file=file, line=int(line), severity='information', code='severity-unlinked',
            subject=cls['iri'],
            message=f'{cls["term"]} holds the severity levels this package uses, but is not '
                    f'declared a kind of sh:Severity -- the class SHACL gives severities.',
            fix={'link': cls['iri']}))
    return out


def sanity(package):
    """Every finding, sorted by file and line. Reads only; writes nothing."""
    declared = _declared(package)
    found = []
    for check in (lambda: _shape_checks(package, declared),
                  lambda: _expectation_checks(package),
                  lambda: _severity_checks(package),
                  lambda: _unused_attributes(package)):
        try:
            found += check()
        except Exception:                          # noqa: BLE001
            continue        # one broken artifact must not hide the others' findings
    return sorted(found, key=lambda f: (f.file, f.line, f.code))
