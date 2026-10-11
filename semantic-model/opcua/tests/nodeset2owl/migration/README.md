# Proof of the nodeset2owl identification migration

The expected files of `tests/nodeset2owl` were regenerated when nodeset2owl switched to the uardf
identification (namespace + base64url of the canonical ExpandedNodeId, static/dynamic nodes, `uardf:`
attributes). These scripts prove that the new output is exactly the old expected output transformed by the
agreed rules, i.e. nothing was lost or changed by accident.

- `uaclassify.py` classifies nodes as static or dynamic from the nodeset XML only (independent of
  `lib/nodesetparser.py`): NamespaceMetadata where it decides, otherwise types and instance declarations are
  static and all other instances dynamic.
- `predict.py old.ttl new.ttl target.xml [dependency.xml ...] [--enforce]` transforms the old expected file and
  compares the prediction with the new output (graph isomorphism):
  - node IRIs `<ns>node<idtype><id>` become `<ns>` + base64url(canonical ExpandedNodeId, no `nsu` for core);
    dynamic nodes and all triples touching them are removed (no `--serverUri` in these tests). A node of a
    namespace exported by a dependency but missing there is dynamic; nodes of namespaces without any export
    are static.
  - `opcua:*NodeClass` -> `uardf:*`; `base:hasNodeId`/`hasIdentifierType` -> `uardf:nodeId`; `base:hasNamespace` ->
    `uardf:namespaceUri`; `base:hasBrowseName`/`hasBrowseNameNamespace` -> `uardf:name`/`uardf:browseName`
    (`nsu=<uri>;<name>`); `base:hasSymbolicName` -> `uardf:symbolicName` (defaults to the BrowseName);
    `base:hasDisplayName`/`hasDescription` -> `uardf:displayName`/`uardf:description` as `@en` (empty ones
    dropped); `base:instanceOf` and the `rdf:type` of variables -> `uardf:hasTypeDefinition` (`rdf:type` with
    `--enforce`); `base:definesType` -> `uardf:definesType`; `base:isAbstract` (string on the class) ->
    `uardf:isAbstract` (boolean on the type node); semantic bridge properties -> `owl:ObjectProperty` +
    `rdfs:subPropertyOf uardf:semanticBridgeReferenceType`.
  - additions: `uardf:parent` from ParentNodeId; semantic bridge triples by rule (`has<BrowseName>` in the
    namespace of the target's BrowseName for every Aggregates reference); bridge property declarations
    without usage are not created; RDF lists of removed triples are removed.
  - Language tags of values are not compared (checked separately).

## Result (2026-10-11)

All 15 cases of `test.bash` (core, core without inputs, DI, Machinery, Pumps, core and DI with
`--enforce-opcua-type-semantic`, 8 feature tests) are proven: new output == prediction.
The only behavioural differences to the old output besides the renamings are:

- dynamic nodes (core: the 116 nodes of the Server subtree; test nodesets: instances without modelling rule)
  are not exported without `--serverUri`, together with all references to them and bridge properties which
  were used by those references only;
- semantic bridge triples to targets whose BrowseName namespace was not declared in the inputs (e.g. core
  targets in the feature tests without core import) are now created; the old query needed the namespace
  declaration with `base:hasUri` and silently skipped them.

## Rerun

```bash
OLD=06b5b164   # commit with the old expected files
git show $OLD:semantic-model/opcua/tests/nodeset2owl/devices_cleaned.ttl > /tmp/devices_cleaned.old.ttl
# new output of the DI case, created like in test.bash and cleaned with cleangraph.py -> /tmp/devices.ttl
python3 predict.py /tmp/devices_cleaned.old.ttl /tmp/devices.ttl Opc.Ua.Di.NodeSet2.xml Opc.Ua.NodeSet2.xml
```
