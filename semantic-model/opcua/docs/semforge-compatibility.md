# OPC UA output as a SemForge package

How far is the output of the OPC UA tools (`nodeset2owl.py`, `owl2instances.py`)
from being a package SemForge can open, validate and test? Measured on the
pump example (`translate_pumpExample.make`): 1710 constraints in 50 node
shapes, the Pumps/Machinery/DI/Core type system, and one pump instance with 21
entities.

## Result

| Package | errors | violations | validate | check | test --coverage |
|---|---|---|---|---|---|
| as copied: `knowledge.ttl` = instance ontology, `shacl.ttl`, `model-instance.jsonld` | **788** | 3 | 2 s | 2 s | 3 s |
| knowledge as a directory holding the `owl:imports` closure | 0 | 0 | 22 s | 103 s | 68 s |
| + `semforge.yaml` and a local context | 0 | 0 | 22 s | 110 s | 72 s |

With the type system present SemForge validates the package clean, and the
three `sh:or` violations of the first row disappear: they were `sh:class`
alternatives that cannot match without the class hierarchy. Every one of the
1710 constraints is still *unexercised* — the example ships one valid
instance and no cases.

`owl2semforge.py` builds the third row:

```bash
python3 owl2semforge.py instanceexample.owl.ttl entities.ttl -s shacl.ttl \
    -m instances.jsonld -c context.jsonld --ngsild ../../ontology/ngsild.ttl \
    -o ../kms/opcua-pumps
```

## Why the type system was missing

`knowledge.ttl` holds the instance ontology only: 2692 triples, no
`owl:Class`, no `rdfs:subClassOf`. The type system is in the ontologies it
names with `owl:imports`. Protégé follows `owl:imports`; SemForge does not —
a package is what is in its files. Every `sh:targetClass` therefore named a
class nothing declared (`undeclared-class`) and every `sh:path` an attribute
nothing declared (`undeclared-path`).

The imports are not portable either: `lib/nodesetparser.py` `create_header`
writes them through `utils.file_path_to_uri`, so every local input becomes an
absolute `file:///home/<user>/...` IRI. A copy of the files on another machine
imports nothing. `OPCUA_PREFIX` (REMOTE) switches to urls for the default
nodesets, and to the placeholder `TBD` for the pump example.

**The knowledge as a directory** solves both: `owl2semforge.py` copies the
closure, one file per ontology, byte for byte, and records each file's source
in `semforge.yaml`. W3C vocabularies and `ngsild.ttl` are neither copied nor
followed (`--exclude`); the package declares its NGSI-LD vocabulary with
`ngsild:`.

## Gaps on the OPC UA side

In order of what they cost:

1. **Entity ids are not IRIs.** `-i "sn1234"` is glued to the base64url node
   id (`lib/utils.py` `generate_node_id`): `sn1234c3Z1PXVy...`. NGSI-LD
   requires a URI, so every JSON-LD processor resolves it against the
   document — SemForge reports `file:///.../sn1234c3Z...`. `-i` must end in a
   URN prefix (`urn:sn1234:`); the default `urn:uaentity:` already does.
2. **The local context does not describe the data.** Entities name the
   PUBLISHED context (`-xc`, default `staging/opcua/v0.2/context.jsonld`) and
   are written with ITS prefixes (`devices:` for DI). The `context.jsonld`
   written beside them is built from the graph's namespaces instead: it calls
   DI `di:`, has no `devices:`, and carries rdflib's defaults (`brick`, `csvw`,
   `dcat`, ...). SemForge answers the published url from the local copy, so
   `devices:hasConfiguration` expands to nothing. One context for both, built
   from the prefixes the instances actually use.
3. **Two versions of `base.ttl`.** The default nodesets import
   `ontology/v0.3/base.ttl`; the instance ontology imports `ontology/v0/base.ttl`,
   because `translate_pumpExample.make` defines `BASE_ONTOLOGY` (v0.1) and never
   passes it (`--baseOntologyURL`). Protégé merges both silently; the package
   now shows both files.
4. **Placeholder names leak into attribute names.** The `<Drive>` placeholder
   becomes the attribute `pumps:has%3CDrive%3E` (`lib/nodesetparser.py`
   `add_semantic_bridge` quotes the browse name), and the instance's datasetId
   is the full predicate IRI (`http://opcfoundation.org/UA/Pumps/has%3CDrive%3E`).
   SemForge flags it `dataset-unregistered`. A datasetId should be a name in a
   registered namespace (`attribute[prefix:name]`); the placeholder should name
   the attribute without brackets.
5. **`base:hasNodeRef` is declared nowhere.** owl2instances emits it on every
   entity (`-sb`/`-nr`, a `VocabProperty`), but no knowledge file declares it
   and no shape constrains it.
6. **Attributes say neither Property nor Relationship.** Generated attributes
   are `owl:ObjectProperty ; rdfs:subPropertyOf uardf:semanticBridgeReferenceType`;
   `entities.ttl` adds `rdfs:domain`. Only the shapes tell a Property
   (`sh:path ngsi-ld:hasValue`) from a Relationship. SemForge reads the kind
   from `rdfs:range ngsild:Property|Relationship`; without it the editor cannot
   offer the right payload for a new value.
7. **Size.** `pumps.owl.ttl` is 8.6 MB: 9616 instance-declaration nodes, each
   with about 12 triples under a long base64url IRI, plus engineering-unit,
   EURange and two-state sub-nodes. Validation needs the classes and the
   attribute declarations; it does not need the instance declarations.

## Gaps on the SemForge side

1. **Speed.** Validation scales (22 s for 12.8 MB of knowledge); the editor
   paths do not. In `check`, 100 of 160 s (profiled) rebuild the Turtle text
   index 16 times over the same files, and 27 s go to `declared_prefixes`,
   which re-reads the configuration 5,600 times. Both are missing caches.
2. **A `JsonProperty` payload is read as attributes.** OPC UA ExtensionObjects
   arrive as `{"type": "JsonProperty", "json": {"xsd:TypeId": …}}`; the
   undeclared-key scan walks into `json` and reports `xsd:Body`, `xsd:TypeId`,
   … (12 notes). A `json` payload is opaque (`@json`).
3. **`owl:imports` is ignored.** Right for a package (it is what is in its
   files), but a package that still carries imports SemForge cannot see should
   be told so, instead of 788 undeclared names.
4. **Without `semforge.yaml` prefixes do not expand.** The entities' inline
   `@context` is not used for the package's prefix table, so a bare directory
   reports every key as undeclared (97 notes). `owl2semforge.py` writes one.

## Next

- OPC UA: ids as URNs; one context; pass `--baseOntologyURL`; placeholder
  names and datasetIds; declare `base:hasNodeRef`; `rdfs:range` on attributes.
- SemForge: the two caches, the `JsonProperty` scan, an `owl:imports`
  diagnostic.
- Then the experiment this example is for: generate good and bad cases for
  the 1710 constraints and run them at this size.
