# Heuristic rules vs. the standard classification: differences and outliers

Evaluation of the static/dynamic classification of nodeset2owl.py on the 20 nodesets of
`translate_default_nodesets.make` (UA-Nodeset UA-1.05.03-2023-12-15), all built with `--serverUri`.

## The rules

The first matching rule decides, in the order R1 to R5. R1 is an *override* (it overrules the
NamespaceMetadata), R2, R4 and R5 are *fallbacks* (they only apply where the NamespaceMetadata does not decide). R3 and R5 are
the rules of the OPC UA standard (`--strict-classification`), R1, R2 and R4 heuristics (default).

| Rule | Name | Statement |
|---|---|---|
| R1 | instance-with-Variables override (heuristic) | An instance which has (direct) Variables is dynamic together with its Variables. Definition nodes are excluded. |
| R2 | ParentNodeId fallback (heuristic) | A node whose ParentNodeId (nodeset attribute, not HasChild) is dynamic is dynamic. Methods, instance declarations and definition nodes are excluded. Only where R3 does not decide. |
| R3 | NamespaceMetadata rule (standard) | The NamespaceMetadata of the namespace decides. |
| R4 | definition fallback (heuristic) | Definition nodes, i.e. Objects and Variables which are definitions rather than data, are static: DataType encodings, dictionary entries, ModellingRules and the legacy type dictionaries (instances of DataTypeEncodingType, DictionaryEntryType, ModellingRuleType, DataTypeSystemType, DataTypeDictionaryType, DataTypeDescriptionType and subtypes, with the Variables of the type dictionaries). Types refer to them by NodeId. Only where R3 does not decide. |
| R5 | default fallback (standard) | Types and instance declarations are static, instances dynamic. |

R2 follows the ParentNodeId of the nodeset (not part of the AddressSpace), R1 HasChild. HasChild means HasChild and all its subtypes, resolved via the ReferenceType hierarchy (nodeset and imported
ontologies). Organizes, like every other reference which is not HasChild, never influences the classification:
organizing a node does not make it part of the organizer. R1 looks at the direct Variables of the instance on purpose: transitively
it would make static entry points such as core's `Objects` folder dynamic. The Variables declared by its
TypeDefinition are not considered either (see the limitations below).

## Differences to the standard classification

| | R1 static → dynamic | R2 static → dynamic | R4 instead of R5: dynamic → static |
|---|---|---|---|
| core | 232 | 0 | 0 |
| every other companion specification with NamespaceMetadata | 8–14 (its NamespaceMetadata object; DI also `OnlineAccess`, `MaxInactiveLockTime`; DEXPI also `DEXPISupplementaryData`) | 0 | 0 |
| Dictionary/IRDI | 0 | 0 | 51 dictionary entries |
| PackML | 0 | 0 | 28 (12 encodings, 16 type dictionary nodes) |
| ISA95 | 0 | 0 | 20 (8 encodings, 12 type dictionary nodes) |
| the 4 instance examples | 0 | 0 | 0 |
| **Total** | **337** | **0** | **99** |

R2 never decides a node on its own: where R3 does not decide, the default fallback R5 already makes every instance dynamic, and the nodes R5 makes static (types and instance declarations) are excluded from R2. All 436 nodes are listed in [classification-changes.md](classification-changes.md), the core findings are in
[core-heuristic-changes.md](core-heuristic-changes.md).

## Outlier checks

| Check | Meaning | Standard rules | Heuristic rules |
|---|---|---|---|
| S1 | dynamic node referenced from a static type-level node (HasEncoding, HasDescription, HasModellingRule, HasDictionaryEntry, …) – should be static | 79 | **0** |
| S2 | dynamic instance of a definition type (encoding, dictionary entry, type dictionary, …) – should be static | 95 | **0** |
| D2 | static instance Variable without a value fixed by the specification, outside dynamic structures – should be dynamic | 7 | **0** |
| D1 | static node below a dynamic node (HasChild ancestor) – possibly dynamic | 615 | **339** |

The 339 remaining D1 nodes:

- **150 method signatures** (`InputArguments`/`OutputArguments`): constants fixed by the specification; their
  ParentNodeId is a static Method.
- **126 Methods** of the dynamic objects (`AddIdentity`, `Open`, `CloseAndUpdate`, …): no state; a call addresses
  Object and Method, the server context comes with the Object. R2 does not apply to Methods.
- **8 core folders with a dynamic ParentNodeId** (`CertificateGroups`, `SecurityGroups`, `PublishedDataSets`,
  `SubscribedDataSets`, `DataSetClasses`, `KeyPushTargets`, `AggregateFunctions`, `EventTypes`): core's
  NamespaceMetadata declares them static, and R2 as a fallback does not overrule it, see
  [specification-issues.md](specification-issues.md) C1.
- **51 IRDI dictionary entries** below core's `Server/Dictionaries`: global definitions which PADIM refers to, static
  by design (R4).
- **4 core folders without ParentNodeId** (`Dictionaries`, `AuthorizationServices`, `KeyCredentialConfiguration`,
  `Resources`): HasComponent children of dynamic instances; R2 follows the ParentNodeId only, so R3 decides (static),
  see [specification-issues.md](specification-issues.md) C1a.

The checks are heuristics as well: they cover what the specifications allow to detect (references from type level,
definition types, Variables without fixed value, containment), not every semantic intention of a node.

## Known limitations

- **Components without ParentNodeId** (4 core folders, static by R3): `Dictionaries` (`i=17594`), `Resources`
  (`i=24226`), `AuthorizationServices` (`i=17732`) and `KeyCredentialConfiguration` (`i=18155`) are HasComponent
  children of dynamic instances, but R2 only follows the ParentNodeId, which the OPC UA nodesets use to express the
  coupling of a node to its parent.
- **Folders only organized by dynamic instances** (9 core folders, static by R3): `TagVariables` (`i=23479`) and
  `Topics` (`i=23488`) by `Aliases`; `Communication` (`i=24227`) by `Resources`, and below it `MappingTables`
  (`i=24228`), `NetworkInterfaces` (`i=24229`), `Streams` (`i=24230`), `TalkerStreams` (`i=24231`),
  `ListenerStreams` (`i=24232`); `Quantities` (`i=32530`) by the Server object. Organizing does not make them part
  of their organizer, so they keep the classification of the NamespaceMetadata. Composed for several servers, every
  server organizes its content below the same (global) folder.
- **Partial instances** (an instance whose Variables the nodeset does not contain): R1 does not consider the
  Variables declared by the TypeDefinition, so such an instance keeps the classification of R3. In the default
  nodesets this concerns `TagVariables` and `Topics`, whose type AliasNameCategoryType declares `LastChange`
  (the time of the last change of the server's alias names). Considering the type was evaluated and rejected: it
  would have fixed these 2 nodes, made `Quantities` dynamic only via a placeholder declaration and wrongly made the
  root-less prototype `FileSystem` (`i=16314`) dynamic.
- **Nodes missing in an imported nodeset** (open, decision pending): PADIM's `EnumDictionaryEntries`
  (`ns=3;i=1161`) has 38 IRDI entries as NodeId values which the published IRDI nodeset does not contain (it contains
  only 59 nodes; its `IsNamespaceSubset` has no value, i.e. completeness unknown). nodeset2owl.py treats a node of an
  imported namespace which its static export does not contain as dynamic, so these global dictionary identifiers
  get a server URI (with `--serverUri`) or are left out. Options: decide by `IsNamespaceSubset` of the imported
  namespace, or by the (static, type level) referencing node.

## Outliers found and fixed during the evaluation

- **ModellingRules in nodesets without NamespaceMetadata** (test nodeset `test_references_special`): dynamic by
  R5, so a copy of `Mandatory` (`i=78`) and all `HasModellingRule` references to it were dropped from the static
  export. Static by R4.
- **Instance Variables with a ModellingRule** (DEXPI `DEXPISupplementaryData`): R1 lets them follow their instance.

Not fixed: the root-less core prototype `HA Configuration` (`i=11202`) is made dynamic by R1 (see [core-heuristic-changes.md](core-heuristic-changes.md)). Not covered by R4: `PackMLObjects`
(`i=72`), an entry folder without NamespaceMetadata decision, stays dynamic (R5) until PackML fills its
`StaticNumericNodeIdRange`.

## Implementation and verification

| Rule | Implementation (`lib/nodesetparser.py`) | Unit tests (`tests/test_libidentification.py`) |
|---|---|---|
| R1 | `instances_with_variables` (direct HasChild Variables, also of instances of other nodesets) | `test_heuristic_instance_with_variables`, `test_r1_ignores_typedefinition` |
| R2 | `classify_with_heuristics` (ParentNodeId dynamic; only where R3 does not decide; no Methods) | `test_heuristic_instance_with_variables` (folder `4200` in the static range, Method `4500`, HasComponent folder `4600` without ParentNodeId, organized folder `4400`) |
| R3 | `scan_namespace_metadata`, `explicit_static` | `test_namespace_metadata_decides`, `test_explicit_static_undecided` |
| R4 | `definition_types`, `is_definition_type` (with subtypes), only where R3 does not decide | `test_heuristic_cases_without_metadata`, `test_r4_does_not_overrule_r3`, dictionary entry `4300` |
| R5 | `is_static_node`, `is_instance_declaration` | `test_fallback_rule_without_server_uri`, `test_default_rule_without_metadata` |
| strict | `--strict-classification` | `test_heuristic_instance_with_variables`, `test_heuristic_cases_without_metadata` |

HasChild is resolved via the ReferenceType hierarchy (`haschild_reference_types`; a custom subtype of HasComponent is
tested), Organizes is never followed. End to end, the final classification of the 20 default nodesets was compared with
an independent build under the standard rules: the nodes whose classification differs are exactly the 436 nodes of the
classification reports, in every nodeset.

The change requests to the specification owners which would make the heuristics unnecessary are collected in
[specification-issues.md](specification-issues.md).
