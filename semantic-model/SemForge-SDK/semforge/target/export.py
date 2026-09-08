"""Export a package to the KMS triple shacl2flink consumes (section 6.3).

Two properties matter more than convenience here.

**Determinism (H5).** Export twice, get identical bytes -- otherwise every
export produces a spurious git diff and the semantic diff drowns in noise. The
`default1:`/`default2:` auto-prefixes in today's knowledge.ttl are exactly that
failure. Determinism is achieved by NOT reserialising: Turtle artifacts are
emitted from their source text, which is byte-stable by construction and also
preserves the comments rdflib would drop (C2 -- an alert should refer to a shape
that appears in the file you wrote).

**Emission mode.** model-instance.jsonld and model-instance.scorpio.jsonld are
the same model serialised for different consumers, and today they are two files
a human keeps in sync:

    compile   keep the observation stream. Four hasStrength values sharing a
              datasetId exercise the dedup and the aggregations built on it.
    broker    collapse each (id, attribute, datasetId) to its latest
              observedAt. NGSI-LD 4.5.5.1 permits only one default instance per
              attribute IN ANY REQUEST, and 4.5.5.3 requires a receiver to keep
              the most recent -- so the four-instance form is not a conformant
              request, however well it compiles offline.
"""

import json
import os
import shutil
from enum import Enum


class EmissionMode(Enum):
    COMPILE = 'compile'
    BROKER = 'broker'


def _observed_at(instance):
    return instance.get('observedAt', '') if isinstance(instance, dict) else ''


def collapse_for_broker(entities):
    """Keep one instance per (attribute, datasetId): the latest observedAt."""
    collapsed = 0
    for entity in entities:
        for key, value in list(entity.items()):
            if key in ('id', 'type', '@context') or not isinstance(value, list):
                continue
            groups = {}
            for instance in value:
                dataset = instance.get('datasetId', '@none') \
                    if isinstance(instance, dict) else '@none'
                groups.setdefault(dataset, []).append(instance)
            kept = []
            for _, instances in groups.items():
                if len(instances) > 1 and any(_observed_at(i) for i in instances):
                    collapsed += len(instances) - 1
                    instances = [max(instances, key=_observed_at)]
                kept.extend(instances)
            entity[key] = kept
    return collapsed


def export(package, out_dir, mode=EmissionMode.COMPILE, target_context=None):
    """Write knowledge.ttl, shacl.ttl and a model instance into out_dir.

    Returns a dict of what was written. The Turtle artifacts are copied from
    source text rather than reserialised, so they are byte-identical to the
    package and stable across runs.

    `target_context` points the exported model somewhere: by default at the
    package's PUBLISHED context, because the broker and the compiler resolve it
    themselves and a file naming a local path is useless to them. Locally the
    same file resolves against the local copy -- that is the whole point of
    declaring both.
    """
    mode = mode if isinstance(mode, EmissionMode) else EmissionMode(mode)
    os.makedirs(out_dir, exist_ok=True)
    written = {}

    for role, name in (('knowledge', 'knowledge.ttl'), ('shapes', 'shacl.ttl')):
        destination = os.path.join(out_dir, name)
        with open(package.sources[role], encoding='utf-8') as source:
            text = source.read()
        with open(destination, 'w', encoding='utf-8') as handle:
            handle.write(text)
        written[role] = destination

    with open(package.sources['model'], encoding='utf-8') as handle:
        entities = json.load(handle)
    if not isinstance(entities, list):
        entities = [entities]
    if mode is EmissionMode.BROKER:
        written['collapsed'] = collapse_for_broker(entities)

    from ..package.context import context_config

    config = context_config(package.path)
    context_value = target_context if target_context is not None else config.published
    if context_value:
        retargeted = 0
        for entity in entities:
            if isinstance(entity, dict) and entity.get('@context') != context_value:
                entity['@context'] = context_value
                retargeted += 1
        written['context_url'] = context_value
        written['retargeted'] = retargeted

    model_path = os.path.join(out_dir, 'model-instance.jsonld')
    with open(model_path, 'w', encoding='utf-8') as handle:
        # sort_keys and fixed indent: the JSON must not reorder between runs,
        # for the same reason the Turtle must not.
        json.dump(entities, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write('\n')
    written['model'] = model_path

    # The compiler needs a LOCAL context; the package's model may reference a
    # remote one, which is not something a build should depend on.
    context = os.path.join(package.path, 'context.jsonld')
    if os.path.exists(context):
        shutil.copyfile(context, os.path.join(out_dir, 'context.jsonld'))
        written['context'] = os.path.join(out_dir, 'context.jsonld')
    return written
