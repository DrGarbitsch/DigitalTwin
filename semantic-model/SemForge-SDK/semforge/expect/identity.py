"""Who is who across the examples: one id, one entity.

An NGSI-LD id identifies an entity. In a suite of examples that rule gets bent
in three different ways, and only two of them are mistakes -- so they are
reported separately rather than as one "duplicate id" complaint. A fourth check
lives here for the same reason: an entity with no @context has no id at all, as
far as the graph is concerned.

  * **Twice in one file.** Always wrong. Nothing distinguishes the two, and
    whichever the reader means, the graph has one entity with both sets of
    attributes.

  * **Twice inside one composed case.** Also wrong, and the dangerous one. The
    case and its includes are parsed into ONE graph, so the definitions MERGE:
    an include saying `hasState ON` and a case saying `hasState OFF` produce an
    entity with both, not an entity that is off. Measured, not assumed -- and it
    is why `compose` cannot be used to override an included entity.

  * **The same id in files that are never composed together.** Not an error:
    each case is validated on its own, and reusing `urn:filter:1` for "the
    filter, switched off" is how a variant of the same thing is written. But the
    id has stopped identifying one entity -- it names four in the kms today --
    so a reader cannot tell which is meant and an edit touches only one of them.
    Reported as a warning, with where the others are.

  * **No `@context`.** `id` and `type` are ordinary keys until a context maps
    them, so the entity expands to a blank node, no shape targets it, and the
    case passes having validated nothing -- the same failure shape as a
    constraint that cannot fire.
"""

import json
import os
from dataclasses import dataclass, field

from .store import discover, load_expectations


@dataclass
class Finding:
    """Something about a document that makes it describe the wrong thing."""
    entity: str
    severity: str
    kind: str
    places: list = field(default_factory=list)
    message: str = ''


@dataclass
class Duplicate:
    entity: str
    severity: str                              # error | warning
    kind: str                                  # in-file | in-case | across-files
    places: list = field(default_factory=list)  # [(file, line)]
    message: str = ''
    case: str = ''                             # for in-case, which case


def _entity_lines(path):
    """[(id, line)] for a document, in order, including repeats."""
    from ..cooked.jsonloc import locate

    try:
        with open(path, encoding='utf-8') as handle:
            raw = handle.read()
        document = json.loads(raw)
    except Exception:                              # noqa: BLE001
        return []
    try:
        index = locate(raw)
    except Exception:                              # noqa: BLE001
        index = {}
    entities = document if isinstance(document, list) else [document]
    out = []
    for position, entity in enumerate(entities):
        if not isinstance(entity, dict):
            continue
        identifier = str(entity.get('id') or entity.get('@id') or '')
        if identifier:
            out.append((identifier, index.get((position,)) or 1))
    return out


def example_files(package):
    """Every JSON-LD document of the package: its model and its examples."""
    files = []
    model = package.sources.get('model')
    if model and os.path.exists(model):
        files.append(os.path.abspath(model))
    root = os.path.join(package.path, 'examples')
    if os.path.isdir(root):
        for relative in discover(package.path):
            files.append(os.path.abspath(os.path.join(root, relative)))
    return files


def _case_groups(package, expectations):
    """{case path: {absolute files composed into it}}."""
    groups = {}
    for example in expectations.examples:
        members = set()
        for relative in list(example.include) + [example.path]:
            for candidate in (os.path.join(package.path, 'examples', relative),
                              os.path.join(package.path, relative), relative):
                if os.path.exists(candidate):
                    members.add(os.path.abspath(candidate))
                    break
        groups[example.path] = members
    return groups


def duplicate_ids(package, expectations=None):
    """Every id that names more than one entity, worst first."""
    expectations = expectations if expectations is not None \
        else load_expectations(package.path)

    by_file = {path: _entity_lines(path) for path in example_files(package)}
    found = []

    # 1. Twice in the same document.
    for path, entries in by_file.items():
        seen = {}
        for identifier, line in entries:
            seen.setdefault(identifier, []).append(line)
        for identifier, lines in seen.items():
            if len(lines) > 1:
                found.append(Duplicate(
                    entity=identifier, severity='error', kind='in-file',
                    places=[(path, line) for line in lines],
                    message=(
                        f'{identifier} is defined {len(lines)} times in '
                        f'{os.path.basename(path)} (lines '
                        + ', '.join(str(line) for line in lines) + '). '
                        'They are one entity carrying every attribute of both; '
                        'give them different ids.')))

    # 2. Twice inside one composed case -- a merge, not an override.
    for case, members in _case_groups(package, expectations).items():
        where = {}
        for path in sorted(members):
            for identifier, line in by_file.get(path, []):
                where.setdefault(identifier, []).append((path, line))
        for identifier, places in where.items():
            files = {path for path, _ in places}
            if len(files) > 1:
                found.append(Duplicate(
                    entity=identifier, severity='error', kind='in-case',
                    places=places, case=case,
                    message=(
                        f'{identifier} is defined by '
                        + ' and '.join(sorted(os.path.basename(p)
                                              for p in files))
                        + f', both composed into {case}. The files are parsed '
                        'into one graph, so the definitions MERGE rather than '
                        'override: the entity ends up with the attributes of '
                        'both. To vary an entity between cases, include a '
                        'different subobject instead.')))

    # 3. The same id in files that never meet. Legitimate, but it stops being
    #    an identifier.
    groups = _case_groups(package, expectations)
    composed = [members for members in groups.values()]
    everywhere = {}
    for path, entries in by_file.items():
        for identifier, line in entries:
            everywhere.setdefault(identifier, {}).setdefault(path, line)
    for identifier, places in everywhere.items():
        if len(places) < 2:
            continue
        # Anything already reported as a merge inside one case is not repeated.
        together = any(len({p for p in places if p in members}) > 1
                       for members in composed)
        if together:
            continue
        listed = sorted(os.path.basename(p) for p in places)
        found.append(Duplicate(
            entity=identifier, severity='warning', kind='across-files',
            places=sorted(places.items()),
            message=(
                f'{identifier} names a different entity in each of '
                + ', '.join(listed) +
                '. Nothing is invalid -- the cases are validated separately '
                'and this is how a variant of the same thing is written -- but '
                'the id no longer identifies one entity: a tree shows it once '
                'per file and an edit reaches only one of them. Renaming means '
                'updating whatever points at it.')))

    order = {'error': 0, 'warning': 1}
    return sorted(found, key=lambda d: (order[d.severity], d.entity, d.kind))


def missing_context(package):
    """Entities that will not expand, because nothing gives them a context.

    In JSON-LD `id` and `type` are ordinary keys until a context maps them. An
    entity without one becomes a blank node with a literal-ish predicate, every
    shape's `sh:targetClass` misses it, and the case passes having validated
    nothing -- the exact failure this project exists to prevent. A list has no
    shared context, so each entity in one needs its own.
    """
    found = []
    for path in example_files(package):
        try:
            with open(path, encoding='utf-8') as handle:
                document = json.load(handle)
        except Exception:                          # noqa: BLE001
            continue
        shared = isinstance(document, dict) and '@context' in document
        entities = document if isinstance(document, list) else [document]
        for position, entity in enumerate(entities):
            if not isinstance(entity, dict) or shared:
                continue
            if '@context' in entity:
                continue
            identifier = str(entity.get('id') or entity.get('@id')
                             or f'entity {position}')
            line = dict(_entity_lines(path)).get(identifier, 1)
            found.append(Finding(
                entity=identifier, severity='error', kind='no-context',
                places=[(path, line)],
                message=(
                    f'{identifier} in {os.path.basename(path)} has no '
                    '@context, so `id` and `type` are ordinary keys: it expands '
                    'to a blank node, no sh:targetClass matches it, and the '
                    'case validates nothing while passing. Add the package\'s '
                    'published context URL, as the other examples do.')))
    return found
