# Heuristic rules vs. the standard classification: differences and outliers

Evaluation of the static/dynamic classification of nodeset2owl.py on the 20 nodesets of
`translate_default_nodesets.make` (UA-Nodeset UA-1.05.03-2023-12-15), all built with `--serverUri`.

## The rules

The first matching rule decides, in the order R1, R2, R3, R5, R4. R3 and R4 are the standard rules
(`--strict-classification`), R1, R2 and R5 the heuristic rules (default).

| Rule | Name | Statement |
|---|---|---|
| R1 | instance-with-Variables rule | An instance with (direct) Variables is dynamic together with its Variables, also against R3. |
| R2 | containment rule | An Object below a dynamic instance (HasChild) or organized by it (Organizes) is dynamic, also against R3. |
| R3 | NamespaceMetadata rule | The NamespaceMetadata of the namespace decides. |
| R5 | Variable-less Object rule | Where R3 does not decide: an Object is dynamic only if a Variable is in its HasChild subtree (Method arguments do not count) or declared by its TypeDefinition (or a supertype), or if a container (HasChild parent, organizer) is dynamic; otherwise it is static. A Method follows its parent, its arguments follow the Method, the Variables of the type dictionaries are static. |
| R4 | default rule | Types and instance declarations are static, instances dynamic. |
| – | type system exception | Instances of ModellingRuleType, DataTypeSystemType, DataTypeDictionaryType, DataTypeDescriptionType, DataTypeEncodingType, DictionaryEntryType (and subtypes) are not made dynamic by R1/R2 and are static by R5. |

HasChild means HasChild and all its subtypes, resolved via the ReferenceType hierarchy (nodeset and imported
ontologies). R1 stays *direct* on purpose: transitively it would make static entry points such as core's `Objects`
folder dynamic. Organizes counts only upwards (a node organized by a dynamic instance), a static entry folder can
organize dynamic machines.

## Differences to the standard classification

| | R1 static → dynamic | R2 static → dynamic | R5 dynamic → static |
|---|---|---|---|
| core | 232 | 21 | 0 |
| every other companion specification with NamespaceMetadata | 8–14 (its NamespaceMetadata object; DI also `OnlineAccess`, `MaxInactiveLockTime`; DEXPI also `DEXPISupplementaryData`) | 0 | 0 |
| Dictionary/IRDI | 0 | 0 | 51 dictionary entries |
| PackML | 0 | 0 | 29 (12 encodings, `PackMLObjects`, 16 type dictionary nodes) |
| ISA95 | 0 | 0 | 20 (8 encodings, 12 type dictionary nodes) |
| the 4 instance examples | 0 | 0 | 0 |
| **Total** | **337** | **21** | **100** |

All 458 nodes are listed in [classification-changes.md](classification-changes.md), the core findings are in
[core-heuristic-changes.md](core-heuristic-changes.md).

## Outlier checks

| Check | Meaning | Standard rules | Heuristic rules |
|---|---|---|---|
| S1 | dynamic node referenced from a static type-level node (HasEncoding, HasDescription, HasModellingRule, HasDictionaryEntry, …) – should be static | 79 | **0** |
| S2 | dynamic instance of a type system or dictionary type – should be static | 95 | **0** |
| D2 | static instance Variable without a value fixed by the specification, outside dynamic structures – should be dynamic | 7 | **0** |
| D1 | static node below a dynamic node (HasChild or Organizes ancestor) – possibly dynamic | 615 | **333** |

The 333 remaining D1 nodes are static by design:

- **154 method signatures** (`InputArguments`/`OutputArguments`): constants fixed by the specification.
- **128 Methods** of the dynamic objects (`AddIdentity`, `Open`, `CloseAndUpdate`, …): no state; a call addresses
  Object and Method, the server context comes with the Object. R2 does not apply to Methods.
- **51 IRDI dictionary entries** below core's `Server/Dictionaries`: global definitions which PADIM refers to; the
  type system exception keeps them static although the folder is dynamic (R2).

The checks are heuristics as well: they cover what the specifications allow to detect (references from type level,
type system types, Variables without fixed value, containment), not every semantic intention of a node.

## Outliers found and fixed during the evaluation

- **Partial instances** (test nodeset `test_static_dynamic`, `Device2`): an instance of a type with Variables, whose
  Variables are not part of the nodeset, would have been static by its own (empty) subtree. R5 also counts the
  Variables declared by the TypeDefinition.
- **Server content folders** (21 core folders, e.g. `SecurityGroups`, `PublishedDataSets`, `TagVariables`):
  static by R3 below dynamic instances. Fixed by R2, which also follows Organizes (9 of them are organized, not
  aggregated, e.g. `Quantities` by the Server object).
- **ModellingRules and encoding prototypes in nodesets without NamespaceMetadata** (test nodesets
  `test_references_special`, `test_objects`): dynamic by R4, so e.g. a copy of `Mandatory` (`i=78`) and all
  `HasModellingRule` references to it were dropped from the static export. Static by R5.
- **Instance Variables with a ModellingRule** (DEXPI `DEXPISupplementaryData`): R1 lets them follow their instance.

Not fixed: core's `HA Configuration` (`i=11202`), a root-less prototype of Part 11, is made dynamic by R1 (see
[core-heuristic-changes.md](core-heuristic-changes.md)).
