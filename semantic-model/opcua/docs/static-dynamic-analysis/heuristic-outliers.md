# Heuristics vs. the formal classification: differences and outliers

Evaluation of the static/dynamic classification of nodeset2owl.py on the 20 nodesets of
`translate_default_nodesets.make` (UA-Nodeset UA-1.05.03-2023-12-15), all built with `--serverUri`.

## The rules

| | Formal (`--strict-classification`) | Default (heuristics) |
|---|---|---|
| 1 | – | An instance with (direct) Variables is dynamic together with its Variables, also against the NamespaceMetadata. ModellingRules and type system instances are excluded. |
| 2 | NamespaceMetadata decides | NamespaceMetadata decides |
| 3 | Types and instance declarations static, instances dynamic | Types and instance declarations static. An Object is dynamic if a Variable is in its HasChild subtree (Method arguments do not count) or declared by its TypeDefinition (or a supertype), or if its HasChild parent is dynamic; otherwise it is static. A Method follows its parent, its arguments follow the Method; the Variables of the type dictionaries are static. |

HasChild means HasChild and all its subtypes, resolved via the ReferenceType hierarchy (nodeset and imported
ontologies); Organizes does not count. Rule 1 stays *direct* on purpose: transitive it would make static entry
points such as core's `Objects` folder dynamic, because the Server object below has Variables.

## Differences to the formal classification

| | static → dynamic (rule 1) | dynamic → static (rule 3) |
|---|---|---|
| core | 232 | 0 |
| every companion specification with NamespaceMetadata | 8–14 (its NamespaceMetadata object, DI also `OnlineAccess`, `MaxInactiveLockTime`) | 0 |
| Dictionary/IRDI | 0 | 51 dictionary entries |
| PackML | 0 | 29 (12 encodings, `PackMLObjects`, 2 dictionaries + 14 descriptions/properties) |
| ISA95 | 0 | 20 (8 encodings, 12 dictionary nodes) |
| the 4 instance examples | 0 | 0 |
| **Total** | **337** | **100** |

The full lists are in [heuristic-overrides.md](heuristic-overrides.md) and, for core, in
[core-heuristic-changes.md](core-heuristic-changes.md).

## Outlier checks

| Check | Meaning | Formal | Heuristics |
|---|---|---|---|
| S1 | dynamic node referenced from a static type-level node (HasEncoding, HasDescription, HasModellingRule, HasDictionaryEntry, …) – should be static | 79 | **0** |
| S2 | dynamic instance of a type system or dictionary type – should be static | 95 | **0** |
| D2 | static instance Variable without a value fixed by the specification, outside dynamic structures – should be dynamic | 7 | **0** |
| D1 | static node below a dynamic node (HasChild or Organizes ancestor) – possibly dynamic | 615 | **354** |

D1 is what remains, all of it in core and IRDI:

- **154 method signatures** (`InputArguments`/`OutputArguments`): constants – fine.
- **128 Methods** of the objects rule 1 makes dynamic (`AddIdentity`, `Open`, `CloseAndUpdate`, …): static
  by core's NamespaceMetadata and without state – fine (a Method is identified together with its Object).
- **51 IRDI dictionary entries** below core's `Server/Dictionaries` folder: global definitions – correctly
  static; the folder itself is a static node in the server specific Server object.
- **21 folders** static by core's NamespaceMetadata below dynamic objects, without Variables:
  `CertificateGroups` (`i=14053`), `SecurityGroups` (`i=15443`), `PublishedDataSets` (`i=17371`),
  `Dictionaries` (`i=17594`), `AuthorizationServices` (`i=17732`), `KeyCredentialConfiguration` (`i=18155`),
  `TagVariables` (`i=23479`), `Topics` (`i=23488`), `SubscribedDataSets` (`i=23658`), `DataSetClasses`
  (`i=23685`), `Resources` (`i=24226`), `Communication` (`i=24227`), `MappingTables` (`i=24228`),
  `NetworkInterfaces` (`i=24229`), `Streams` (`i=24230`), `TalkerStreams` (`i=24231`), `ListenerStreams`
  (`i=24232`), `KeyPushTargets` (`i=25440`), `Quantities` (`i=32530`), `AggregateFunctions` (`i=32643`),
  `EventTypes` (`i=32755`). **These are the remaining doubtful nodes:** they carry no state themselves, but they
  are containers of server specific content (security groups, data sets, aliases, …). Composed for several
  servers, every server would attach its content to the same global folder. Rule 3 would make them dynamic
  (dynamic parent), but the NamespaceMetadata decides them static and rule 1 does not apply (no Variables).

## Outliers found and fixed during the evaluation

- **Partial instances** (test nodeset `test_static_dynamic`, `Device2`): an instance of a type with Variables,
  whose Variables are not part of the nodeset, would have been static by its own (empty) subtree. Rule 3 now
  also counts the Variables declared by the TypeDefinition.
- **ModellingRules and encoding prototypes in nodesets without NamespaceMetadata** (test nodesets
  `test_references_special`, `test_objects`): formally dynamic, so e.g. a copy of `Mandatory` (`i=78`) and all
  `HasModellingRule` references to it were dropped from the static export. Now static.
- **Instance Variables with a ModellingRule** (DEXPI `DEXPISupplementaryData`): rule 1 lets them follow their
  instance.

Not fixed: core's `HA Configuration` (`i=11202`), a root-less prototype of Part 11, is made dynamic by rule 1
(see [core-heuristic-changes.md](core-heuristic-changes.md)).
