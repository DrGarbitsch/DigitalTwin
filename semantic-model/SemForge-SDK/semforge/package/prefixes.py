"""One name per namespace, across every artifact in a package.

The kms did not have this, and the failure is worse than untidiness: the SAME
prefix denoted DIFFERENT namespaces in two files.

    :          base_shacl/      in shacl.ttl      base_entities/   in knowledge.ttl
    default1:  filter_shacl/    in shacl.ttl      base_knowledge/  in knowledge.ttl

So `:CartridgeShape` means one thing in one file and another in the other, and a
term copied between them changes meaning silently. The `default1..5` names come
from `make ontology2kms` merging modules with rdfpipe, which invents a prefix
whenever the source did not supply one.

The context is the source of truth, because it is the one artifact all three
already share: `context.jsonld` declares terms with `"@prefix": true`, and
`model-instance.jsonld` is written against them. This reads that map, reports
where the Turtle files disagree with it, and rewrites them to match.

What it will not do is invent a name for a namespace the context does not
declare. Those are reported so somebody adds them to the context, which is the
only place a name can be agreed.
"""

import json
import os
import re
from dataclasses import dataclass, field

from .registry import CACHE  # noqa: F401  (keeps the module's role obvious)

PREFIX_LINE = re.compile(
    r'^([ \t]*)@prefix[ \t]+([A-Za-z_][\w.-]*)?:[ \t]*<([^>]*)>[ \t]*\.[ \t]*$',
    re.MULTILINE)


@dataclass
class PrefixFinding:
    code: str
    severity: str
    message: str
    namespace: str = ''
    files: list = field(default_factory=list)


def context_prefixes(package_path, filename='context.jsonld'):
    """{prefix: namespace} declared by the package's JSON-LD context."""
    path = os.path.join(package_path, filename)
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as handle:
        document = json.load(handle)
    entries = document.get('@context', document)
    if not isinstance(entries, list):
        entries = [entries]

    found = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for name, value in entry.items():
            if isinstance(value, dict) and value.get('@prefix') and '@id' in value:
                found[name] = value['@id']
            elif isinstance(value, str) and value.endswith(('/', '#')):
                found[name] = value
    return found


def declared_prefixes(package_path):
    """`namespaces:` from semforge.yaml, which overrides the context."""
    config = os.path.join(package_path, 'semforge.yaml')
    if not os.path.exists(config):
        return {}
    from ruamel.yaml import YAML

    with open(config) as handle:
        data = YAML().load(handle) or {}
    return dict(data.get('namespaces') or {})


def canonical_map(package_path):
    """The agreed name for each namespace. semforge.yaml wins over the context."""
    found = context_prefixes(package_path)
    found.update(declared_prefixes(package_path))
    return found


def names_by_namespace(package_path):
    """{namespace: agreed name}, with the package's own declaration winning.

    Two names for one namespace is legal and happens -- the context calls
    base_knowledge `base` while this package calls it `iffBaseKnowledge`. The
    package's declaration is the deliberate one, so it is applied first and the
    context only fills namespaces the package says nothing about.
    """
    declared = declared_prefixes(package_path)
    by_namespace = {}
    for name, namespace in declared.items():
        by_namespace.setdefault(namespace, name)
    for name, namespace in context_prefixes(package_path).items():
        by_namespace.setdefault(namespace, name)
    return by_namespace


def file_prefixes(path):
    with open(path, encoding='utf-8') as handle:
        text = handle.read()
    return {(match.group(2) or ''): match.group(3)
            for match in PREFIX_LINE.finditer(text)}, text


def check(package):
    """Findings for every disagreement between the artifacts and the context."""
    by_namespace = names_by_namespace(package.path)

    artifacts = {role: package.sources[role] for role in ('shapes', 'knowledge')}
    seen = {}
    findings = []

    for role, path in artifacts.items():
        prefixes, _ = file_prefixes(path)
        for name, namespace in prefixes.items():
            seen.setdefault(name, {}).setdefault(namespace, []).append(role)

    # The dangerous one: one prefix, two meanings.
    for name, namespaces in sorted(seen.items()):
        if len(namespaces) > 1:
            findings.append(PrefixFinding(
                code='SF-PFX-001', severity='error',
                message=(f'"{name or "(default)"}:" denotes '
                         + ' and '.join(f'{ns} in {", ".join(roles)}'
                                        for ns, roles in sorted(namespaces.items()))
                         + '. A term copied between them changes meaning.'),
                files=[role for roles in namespaces.values() for role in roles]))

    for role, path in sorted(artifacts.items()):
        prefixes, _ = file_prefixes(path)
        for name, namespace in sorted(prefixes.items()):
            agreed = by_namespace.get(namespace)
            if agreed is None:
                findings.append(PrefixFinding(
                    code='SF-PFX-003', severity='warning', namespace=namespace,
                    message=(f'{role}: <{namespace}> is used as "{name or "(default)"}:" '
                             f'but the context declares no name for it. Add one '
                             f'to context.jsonld or semforge.yaml.'),
                    files=[role]))
            elif agreed != name:
                findings.append(PrefixFinding(
                    code='SF-PFX-002', severity='warning', namespace=namespace,
                    message=(f'{role}: <{namespace}> is "{name or "(default)"}:" here '
                             f'but "{agreed}:" in the context.'),
                    files=[role]))
    return findings


def _rewrite(text, renames):
    """Rename prefixes in a Turtle document, headers and usages alike.

    Strings, comments and IRIs are stepped over. That matters most for the
    SPARQL bodies in shacl.ttl: they carry their own PREFIX declarations inside
    a triple-quoted literal and are a separate namespace scope, so rewriting
    into them would break queries that are currently correct.
    """
    from ..rdfio.turtle_index import _skip_string

    out = []
    i = 0
    while i < len(text):
        char = text[i]
        if char == '#':
            end = text.find('\n', i)
            end = len(text) if end == -1 else end
            out.append(text[i:end])
            i = end
            continue
        if char in '"\'':
            end = _skip_string(text, i)
            out.append(text[i:end])
            i = end
            continue
        if char == '<':
            closing = text.find('>', i)
            newline = text.find('\n', i)
            if closing != -1 and (newline == -1 or closing < newline):
                out.append(text[i:closing + 1])
                i = closing + 1
                continue
        match = re.compile(r'([A-Za-z_][\w.-]*)?:').match(text, i)
        if match and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] in '_-.:')):
            name = match.group(1) or ''
            if name in renames:
                out.append(renames[name] + ':')
                i = match.end()
                continue
        out.append(char)
        i += 1
    return ''.join(out)


def align(package, dry_run=False):
    """Rewrite the Turtle artifacts to the agreed names. Returns {role: renames}."""
    by_namespace = names_by_namespace(package.path)

    applied = {}
    for role in ('shapes', 'knowledge'):
        path = package.sources[role]
        prefixes, text = file_prefixes(path)
        renames = {name: by_namespace[namespace]
                   for name, namespace in prefixes.items()
                   if namespace in by_namespace and by_namespace[namespace] != name}
        if not renames:
            continue
        applied[role] = renames
        if dry_run:
            continue

        updated = _rewrite(text, renames)
        from rdflib import Graph
        from rdflib.compare import isomorphic

        before, after = Graph(), Graph()
        before.parse(data=text, format='turtle')
        after.parse(data=updated, format='turtle')
        if not isomorphic(before, after):
            raise ValueError(
                f'{role}: renaming prefixes changed the graph; refusing to write')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(updated)
    return applied
