# Heuristic rules vs. the standard classification: differences and outliers

Evaluation of the static/dynamic classification of nodeset2owl.py on the 20 nodesets of
`translate_default_nodesets.make` (UA-Nodeset UA-1.05.03-2023-12-15), all built with `--serverUri`.

## The rules

The first matching rule decides, in the order R1 to R5. R3 and R5 are the rules of the OPC UA standard
(`--strict-classification`), R1, R2 and R4 the heuristic rules (default).

| Rule | Name | Statement |
|---|---|---|
| R1 | instance-with-Variables rule (heuristic) | An instance which has (direct) Variables is dynamic together with its Variables, also against R3. |
| R2 | containment rule (heuristic) | An Object below a dynamic instance (HasChild) is dynamic, also against R3. |
| R3 | NamespaceMetadata rule (standard) | The NamespaceMetadata of the namespace decides. |
| R4 | definition rule (heuristic) | Instances which are definitions rather than data are static: DataType encodings, dictionary entries, ModellingRules and the legacy type dictionaries (instances of DataTypeEncodingType, DictionaryEntryType, ModellingRuleType, DataTypeSystemType, DataTypeDictionaryType, DataTypeDescriptionType and subtypes, with the Variables of the type dictionaries). Types refer to them by NodeId. R4 does not overrule R3; R1 and R2 never make them dynamic. |
| R5 | default rule (standard) | Types and instance declarations are static, instances dynamic. |

HasChild means HasChild and all its subtypes, resolved via the ReferenceType hierarchy (nodeset and imported
ontologies). Organizes, like every other reference which is not HasChild, never influences the classification:
organizing a node does not make it part of the organizer. R1 looks at the direct Variables of the instance on purpose: transitively
it would make static entry points such as core's `Objects` folder dynamic. The Variables declared by its
TypeDefinition are not considered either (see the limitations below).

## Differences to the standard classification

| | R1 static → dynamic | R2 static → dynamic | R4 dynamic → static |
|---|---|---|---|
| core | 232 | 12 | 0 |
| every other companion specification with NamespaceMetadata | 8–14 (its NamespaceMetadata object; DI also `OnlineAccess`, `MaxInactiveLockTime`; DEXPI also `DEXPISupplementaryData`) | 0 | 0 |
| Dictionary/IRDI | 0 | 0 | 51 dictionary entries |
| PackML | 0 | 0 | 28 (12 encodings, 16 type dictionary nodes) |
| ISA95 | 0 | 0 | 20 (8 encodings, 12 type dictionary nodes) |
| the 4 instance examples | 0 | 0 | 0 |
| **Total** | **337** | **12** | **99** |

All 448 nodes are listed in [classification-changes.md](classification-changes.md), the core findings are in
[core-heuristic-changes.md](core-heuristic-changes.md).

## Outlier checks

| Check | Meaning | Standard rules | Heuristic rules |
|---|---|---|---|
| S1 | dynamic node referenced from a static type-level node (HasEncoding, HasDescription, HasModellingRule, HasDictionaryEntry, …) – should be static | 79 | **0** |
| S2 | dynamic instance of a definition type (encoding, dictionary entry, type dictionary, …) – should be static | 95 | **0** |
| D2 | static instance Variable without a value fixed by the specification, outside dynamic structures – should be dynamic | 7 | **0** |
| D1 | static node below a dynamic node (HasChild ancestor) – possibly dynamic | 615 | **327** |

The 327 remaining D1 nodes are static by design:

- **150 method signatures** (`InputArguments`/`OutputArguments`): constants fixed by the specification.
- **126 Methods** of the dynamic objects (`AddIdentity`, `Open`, `CloseAndUpdate`, …): no state; a call addresses
  Object and Method, the server context comes with the Object. R2 does not apply to Methods.
- **51 IRDI dictionary entries** below core's `Server/Dictionaries`: global definitions which PADIM refers to; R4
  keeps them static although the folder is dynamic (R2).

The checks are heuristics as well: they cover what the specifications allow to detect (references from type level,
definition types, Variables without fixed value, containment), not every semantic intention of a node.

## Known limitations

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

- **Server content folders** (12 core folders, e.g. `SecurityGroups`, `PublishedDataSets`, `CertificateGroups`,
  `Dictionaries`, `Resources`): static by R3, but components (HasChild) of dynamic instances. Fixed by R2.
- **ModellingRules in nodesets without NamespaceMetadata** (test nodeset `test_references_special`): dynamic by
  R5, so a copy of `Mandatory` (`i=78`) and all `HasModellingRule` references to it were dropped from the static
  export. Static by R4.
- **Instance Variables with a ModellingRule** (DEXPI `DEXPISupplementaryData`): R1 lets them follow their instance.

Not fixed: the root-less core prototype `HA Configuration` (`i=11202`) is made dynamic by R1 (see [core-heuristic-changes.md](core-heuristic-changes.md)). Not covered by R4: `PackMLObjects`
(`i=72`), an entry folder without NamespaceMetadata decision, stays dynamic (R5) until PackML fills its
`StaticNumericNodeIdRange`.
