# Validation Rule Catalog — OPC 10000-100 (Devices / DI)

Complete first pass over the DI companion specification: every section from §1 to
§12 and the three annexes was read, and each one either yields rules or is
recorded below with the reason it does not.

Source: [OPC 10000-100, Devices, v1.03](https://reference.opcfoundation.org/DI/v103/docs/).

Manifest:
[`../validation/specs/opc-10000-100-devices/spec.jsonld`](./spec.jsonld).
Depends on `opc-10000-3-address-space`. Method and the shared vocabulary traps:
[`adding-a-validation-specification.md`](../../../docs/adding-a-validation-specification.md)
and [`../validation/README.md`](../../README.md).

**Nothing here is enforced yet** — catalogued only, no shapes, no fixtures.
36 rules, of which 21 are checkable against the translated graph today. DI is the
richest of the three companion specifications catalogued so far, and by some
distance: it carries more enforceable structural rules than Machinery and Pumps
combined.

## Status legend

| Status | Meaning |
|---|---|
| **Gap** | Checkable today — the data the rule needs is already in the translated graph — but no shape exists yet. |
| **Instance-level** | Real and checkable, but only against a nodeset that *instantiates* the types, not one that defines them. Needs an instance fixture. |
| **Push down** | Not really a rule of this specification: it is a core (Part 3) rule surfacing here. Implement it once in `opc-10000-3-address-space` and every companion spec inherits it. |
| **Advanced** | Structurally real but not a simple shape — needs a table from the spec text, a recursive walk, or a cross-consistency check. |
| **Blocked** | Real and static, but `nodeset2owl.py` does not extract the Attribute the rule depends on. |
| **Needs verification** | Extracted from a secondary reading; re-read the primary subclause before writing a shape. |
| **N/A** | Normative, but not a static property of one AddressSpace snapshot (runtime or Client behaviour, Server capability, advisory "should"). Recorded so it is not re-derived later. |

## Confidence and coverage

Section numbers and quoted text come from structured readings of the online
specification, not from the PDF.

**One conflict.** Two readings of §5.2 disagree: one reported "The *BrowseName*
of each instance of a *ProtocolType* shall define the *Communication Profile*",
the other reported §5.2 as carrying no normative sentence at all. DI-009's
status is unaffected — it is unenforceable either way, for want of a closed
vocabulary of profile names — but the disagreement is recorded rather than
silently resolved.

**One coverage gap.** §8 is by far the largest section in the specification, and
the rendering truncated after §8.4.9.7. **§8.5 (DataTypes), §8.6 (ReferenceTypes
— `UpdateParent` and `CanUpdate`) and §8.7 (Software Package file format) have
not been read.** §8.6 is the one most likely to hold rules: a ReferenceType
definition in Part 3 terms carries source/target NodeClass constraints, which is
exactly the shape family AS-031 and AS-035 already cover. Treat DI's §8 as
partially catalogued.

---

## §1 Scope, §2 Normative references — no rules

Standard front matter. §1 states what the document covers, §2 lists referenced
standards. No graph-shape language.

## §3 Terms, definitions, abbreviated terms, and conventions — 5 rules

§3.1 defines eighteen terms (Block, Device, Network, Software Package, and the
software-update version vocabulary) and §3.2 lists abbreviations; neither
constrains a model. §3.3's conventions do, and — like Machinery's §3.4 — they
constrain **the DI nodeset itself**, so their fixtures are type-level.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-014 | 3.3.3.3, 3.3.3.4 | If a Variable's or VariableType's ValueRank specifies an array of a specific dimension (ValueRank > 0), the ArrayDimensions Attribute shall be specified. | Gap | **The best first shape in this specification.** A pure two-attribute consistency check with no transcription, no external table and no instance values needed — and both attributes are already emitted: `base:hasValueRank` and `base:hasArrayDimensions` appear 68 times each in the translated DI graph. It also holds for every companion specification, which makes it a strong candidate for pushing down into Part 3 later; catalogue it here first, where the sentence actually is. |
| DI-013 | 3.3.3.1–3.3.3.3 | For every Node, Object and Variable specified in this document, the Attributes named in Tables 7–9 shall be set as those tables specify. | Gap | Same rule family as Machinery's MA-011, and the same caveat: the shape needs the three tables transcribed, so implement the attributes that matter rather than the whole table at once. |
| DI-016 | 3.3.1.1 | If two Nodes defined by this specification are both exposed, all References between them that the specification defines shall be exposed as well. | Advanced | "If two *Nodes* are exposed, all *References* between the *Nodes* defined in this specification shall be exposed as well." A genuine and unusually interesting constraint — it says a Server may omit optional Nodes but may not omit the edges between the ones it kept. Implementing it means holding the specification's own reference set as reference data, which the DI nodeset *is*: the `commonNodeset` already contains every reference the spec defines. Hard but not blocked. |
| DI-015 | 3.3.3.5 | All Methods defined in this document shall be executable (Executable = True) unless their definition says otherwise. | Blocked | The `Executable` Attribute is not extracted by `lib/nodesetparser.py`. Identical to Machinery's MA-023 — two specifications now blocked on the same missing attribute, which is the argument for extending the parser rather than a coincidence. |
| DI-017 | 3.3.3.1 | Non-server-specific Attributes shall be set to not writable, and the NodeId shall not be writable. | Blocked | Expressed through `WriteMask`/`UserWriteMask`, and `grep -rn WriteMask lib/` returns nothing — the attribute never reaches the graph. Static and real, unlike the Server-capability entries below, which is why it is Blocked rather than N/A. |

§3.3.2 (NodeIds and BrowseNames) explains the document's symbolic-name notation
and imposes nothing on a model.

## §4 Device model — 8 rules

The core section. §4.1 (General) and §4.2 (Usage guidelines) are introductory,
and §4.2 defers entirely to Annex C.

### §4.3–4.4 TopologyElement, ParameterSet, MethodSet, FunctionalGroups

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-001 | 4.4.1 | All BrowseNames of Nodes referenced by one FunctionalGroup with an `Organizes` Reference shall be unique. | Gap | Direct analog of AS-006, which scopes the same uniqueness test to a Node's Properties. Compare (name, namespace) pairs, scope to one owner, traverse `rdfs:subPropertyOf* opcua:Organizes` so a subtype of `Organizes` still counts. The shape it most resembles is already working, which makes it the cheapest way to prove the scaffolding of a new spec directory. |
| DI-004 | 4.3 | The MethodSet Object is only present if it includes at least one Method. | Gap | "The *MethodSet* is only available if it includes at least one *Method*." A `FILTER NOT EXISTS` over components with `opcua:MethodNodeClass`. Note the Part 3 idiom: never `COUNT` over an `OPTIONAL` for a zero test. Mirror image of DI-031's non-empty rule and of PU-001. |
| DI-012 | 4.4.1 | A FunctionalGroup that can be hidden on an instance shall carry an appropriate ModellingRule on the TypeDefinition. | Advanced | "Appropriate" is not enumerated in the sentence; which ModellingRules qualify needs the surrounding text. Not a shape until that is pinned down. |
| DI-011 | 4.4.2 | Servers exposing a FunctionalGroup for a described purpose use the well-known BrowseName. | N/A (advisory) | "should", not "shall". Recorded so a future pass does not promote it. |

### §4.5 Interfaces

Eight subsections defining the VendorNameplate, TagNameplate, DeviceHealth,
OperationCounter, SupportInfo and AssetLocationIndication Interfaces. Almost all
of it is definition tables.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-008 | 4.5.4 | DeviceHealth is one of the five NAMUR NE107 values (NORMAL, FAILURE, CHECK_FUNCTION, OFF_SPEC, MAINTENANCE_REQUIRED). | Instance-level | `base:hasValue` and the enum machinery (`base:hasEnumValue`, `base:hasValueList`) are all emitted, so this is checkable — but only against a fixture carrying an actual value. §4.5.4 additionally says the DeviceHealthAlarms folder *should* be used for Alarm instances: advisory, not a rule. |
| DI-018 | 4.5.5 | `PowerOnDuration`, `OperationDuration` and `OperationCycleCounter` shall only increase during the lifetime of the Device. | Gap, `checkableIn: NgsiLdTemporal` | **Reclassified from N/A.** Unanswerable against a NodeSet2, which carries no time; ordinary SHACL against the NGSI-LD temporal representation, where each attribute instance has its own `ngsild:observedAt`. Identical to Machinery's MA-018 — the same Interface, catalogued twice because both specifications restate it, which is a small argument that DI is where the shape belongs. |

### §4.6–4.9 ComponentType, DeviceType, SoftwareType, DeviceSet

§4.6 (ComponentType), §4.8 (SoftwareType), §4.10 (DeviceFeatures entry point),
§4.11 (BlockType) and §4.12 (DeviceHealth Alarm Types) contain no normative
sentences — all are definition tables and type-hierarchy description. §4.6 is
explicit that ComponentType "does not mandate any Properties".

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-002 | 4.9 | The DeviceSet Object shall, directly or indirectly, reference every instance of a ComponentType subtype with a hierarchical Reference. | Gap | "shall either directly or indirectly reference all instances of a subtype of *ComponentType* with a *Hierarchical Reference*." Reachability from a named anchor over `opcua:HierarchicalReferences` — the first rule in the project needing a `+` property path rather than a fixed number of hops. |
| DI-003 | 4.9 | For a complex Device composed of Devices, only the root instance shall be referenced from DeviceSet. | Gap | The negative half of DI-002, and the half implementers get wrong: a sub-Device that is already a component of another Device must not *also* hang directly off DeviceSet. The two rules pull in opposite directions, so a fixture satisfying one and violating the other is the interesting test case — write them as a pair with shared fixtures. |
| DI-007 | 4.7 | The Properties DeviceType declares Mandatory are present on every DeviceType instance. | Push down | DeviceType declares SerialNumber, Manufacturer, Model, DeviceManual, DeviceRevision, SoftwareRevision and HardwareRevision mandatory. The *obligation* is Part 3's: an instance carries every InstanceDeclaration whose ModellingRule is `Mandatory`. Implementing it in `opc-10000-3-address-space` covers this rule, Machinery's MA-004, MA-006 and MA-008, and the same rule in every companion specification that will ever be added. The single highest-leverage shape available to the project. The spec's carve-out — "vendors shall provide the following defaults" where a Property is unsupported — does not weaken it: the Property is still present. |

## §5 Device communication model — 5 rules

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-005 | 5.6 | All Networks shall be components of the NetworkSet Object. | Gap | One hop, `rdfs:subPropertyOf* opcua:HasComponent`, anchored on a named Object. |
| DI-006 | 5.4 | Every ConnectionPoint shall carry the inverse `ComponentOf` Reference to its Device. | Gap | Inverse References are materialised as forward triples on the source node, so in the translated graph this reads as: every instance of a ConnectionPointType subtype is the target of some `HasComponent`. |
| DI-009 | 5.2 | The BrowseName of each ProtocolType instance defines the Communication Profile. | N/A | No closed vocabulary of profile names to check a BrowseName against, and an external list would go stale. See the conflict note above: one reading does not find this sentence in §5.2 at all. Unenforceable under either reading. |
| DI-010 | 4.3, 5.3 | Clients shall use LockingServices when making a set of changes that is only consistent once all are applied; an InitLock is rejected if a subordinate Device or Network is already locked; where Online/Offline is supported the lock applies to both versions. | N/A | Client and Server runtime behaviour over time. |
| DI-036 | 12.2 | The standard namespaces shall have fixed indices (0 for the OPC UA namespace, 1 for the local Server URI). | N/A | A Server namespace-table statement. `nodeset2owl.py` works in namespace URIs, not indices, so the concept the rule constrains does not survive translation — and correctly so. |

§5.1 (General) is overview and figures. §5.5 (ConnectsTo and ConnectsToParent
ReferenceTypes) defines two ReferenceTypes through definition tables and figures
with no normative sentence — worth a second look against primary text, since a
ReferenceType definition usually carries source/target NodeClass constraints of
exactly the kind AS-031 enforces.

## §6 Device integration host model — 4 rules

§6.1 (General) and §6.2 (DeviceTopology Object) are descriptive. §6.3.2 is the
productive subclause: `IsOnline` is a DI-defined ReferenceType, and its
definition carries both a typing constraint and a cardinality constraint.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-019 | 6.3.2 | The source and target Node of an `IsOnline` Reference shall be instances of the same subtype of ComponentType. | Gap | "shall be an instance of the **same** subtype of a *ComponentType*." A same-type constraint across a reference — a shape family nothing in the suite has yet, and one that cannot be expressed by targeting a class: it has to compare the two endpoints' type definitions. Remember the Part 3 trap that Objects carry `base:instanceOf` while Variables keep plain `rdf:type`. |
| DI-020 | 6.3.2 | Each Device shall be the source of at most one `IsOnline` Reference. | Gap | A maximum-cardinality rule, structurally the same as AS-008's "more than one" half — and unlike AS-008's, this one *can* be given a failing fixture, because nothing in the translation collapses duplicate `IsOnline` references. Use the grouped-subquery idiom from AS-008 rather than `COUNT` over an `OPTIONAL`. |
| DI-021 | 6.4.3 | The Object containing the TransferServices Methods shall have the BrowseName `Transfer`. | Gap | A fixed-BrowseName rule; `base:hasBrowseName` is on every translated node. Compare with §7.3's Lock Object, where the equivalent sentence is "should" — the two subclauses are otherwise parallel, which makes the difference in modality worth preserving exactly. |
| DI-022 | 6.4.1, 6.4.2 | The Device shall have been locked by the Client before these Methods are invoked, and `Bad_MethodInvalid` shall be returned where locking is not supported. | N/A | Method-invocation preconditions and StatusCode returns. Runtime. |

## §7 Locking model — 3 rules

§7.1 is an overview; §7.5–7.8 specify the InitLock, ExitLock, RenewLock and
BreakLock Method signatures and status codes, with no address-space content.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-023 | 7.3 | The LockingServices Object shall be referenced using `HasComponent` or `HasAddIn` from the lock-owner Object. | Gap | An alternation over two reference types — traverse `rdfs:subPropertyOf*` of each and accept either. Note the neighbouring sentence, that the Object *should* have the BrowseName `Lock`, is advisory: the structural requirement is the reference, not the name. Getting that distinction right in the shape is the whole point of quoting modality in this catalog. |
| DI-024 | 7.4 | The `MaxInactiveLockTime` Property shall be added to the ServerCapabilities Object. | Gap | Anchors to a fixed NS0 node, so `ServerCapabilities` (i=2268) has to be in the baseline nodeset — a concrete addition to whatever ends up in `specs/opc-10000-100-devices/common/`, alongside Machinery's need for `Objects` (i=85). |
| DI-025 | 7.2, 7.4 | `Bad_MethodInvalid` and `Bad_UserAccessDenied` shall be returned in the stated circumstances, and calling RenewLock shall reset the timer. | N/A | Runtime behaviour and Server-side timers. |

## §8 Software update model — 5 rules (partially catalogued)

The largest section in the specification: 22 supported use cases, 12 ObjectTypes,
and its own file format. Most of it is Method behaviour, state-machine semantics
and Client obligations — none of which is address-space shape. The structural
content concentrates in §8.3.11 (the AddIn model).

**§8.5, §8.6 and §8.7 were not reached** — see the coverage note above.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-026 | 8.3.11 | An instance of `SoftwareUpdateType` shall be attached to an Object that implements the `IVendorNameplateType` Interface. | Gap | A constraint on *where* an AddIn may be attached, which is the same family as Machinery's MA-002 and equally invisible to schema validation. Interface implementation is materialised as type membership in the translated graph, so the shape checks the owner's types rather than looking for a reference. |
| DI-027 | 8.3.11 | The SoftwareUpdate AddIn instance shall use the fixed BrowseName `SoftwareUpdate`. | Gap | Fixed-BrowseName rule; pairs naturally with DI-026 in one fixture, the way MA-003 and MA-013 do. |
| DI-028 | 8.3.11 | The implementing Interface shall support at least the Variables `Manufacturer`, `ManufacturerUri`, `ProductCode` and `SoftwareRevision`, with valid values. | Gap + instance-level | Two halves again: presence is checkable on a type fixture, "valid values" needs an instance fixture and a definition of valid this subclause does not give. Implement presence; record the rest. |
| DI-029 | 8.4.1.2 | The `Loading` Object is required for all variations of software installation. | Gap | A mandatory-component rule stated in prose rather than through a Mandatory ModellingRule — worth checking against the nodeset whether the ModellingRule is actually present, in which case this collapses into DI-007 and needs no shape of its own. |
| DI-030 | 8.3.4.2, 8.4.3.3.2, 8.4.5.3, 8.4.7.2, 8.4.8.1, 8.4.9.4 | Clients shall use the PrepareForUpdate state machine unless UpdateBehavior says otherwise; shall write files in chunks where WriteBlockSize is supported; version Objects shall be empty where no software is pending; `InstallSoftwarePackage` shall not return before the state has changed. | N/A | Collected as one entry: all are Client obligations or Method-return semantics. None constrains a static address space. |

## §9 Specialized topology elements — 2 rules

§9.1 is introductory. §9.3 (Block Devices) and §9.4 (Modular Devices) describe
composition patterns without normative sentences — both build on the
ConfigurableObjectType pattern §9.2 defines, so the rules below cover them.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-031 | 9.2.1 | A configurable Object shall contain a folder called `SupportedTypes` that references the available Types with `Organizes` References. | Gap | Presence of a named folder plus the reference type used from it — two conditions, one shape. The non-empty mirror of DI-004, and close kin to Machinery's MA-015. |
| DI-032 | 9.2.1 | The configured instances shall be components of the configurable Object. | Gap | Pairs with DI-031: DI-031 constrains where the *types* live, DI-032 where the *instances* live. Both are needed for the pattern to be navigable, and a model can satisfy either alone. |

## §10 Lifetime model — 2 rules

§10.1 is an overview, and §10.3–§10.9 define seven indication types
(Time, NumberOfParts, NumberOfUsages, Length, Diameter, SubstanceVolume and their
shared base) purely through definition tables. All the normative content is in
§10.2.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-033 | 10.2 | The DataType of `StartValue`, `LimitValue` and `WarningValues` shall be the same as the DataType of the Variable's Value. | Gap | Stated three times in one subclause, once per Property. A same-DataType consistency check across Properties of one Variable; `base:hasDatatype` is emitted 327 times across the DI and Machinery graphs, so the data is there. Structurally similar to DI-019 — compare two nodes' attributes rather than test one node against a constant — and the two would make a good pair to implement together. |
| DI-034 | 10.2 | If provided, `WarningValues` shall lie between `StartValue` and `LimitValue`. | Instance-level | An ordering constraint over three values, so it needs a fixture carrying actual values. Note "if provided": the constraint is conditional, like Machinery's MA-005 and MA-016, so a `pass-` fixture omitting WarningValues entirely is a required case. |

## §11 Profiles and ConformanceUnits — no rules

Two sentences, both pointing elsewhere: to OPC 10000-7 for what Profiles mean,
and to the online profile database for DI's own. Nothing normative here, and
unlike Machinery's §19 there is not even a conformance-unit table to read. Any
structural requirement would come from the online database, which is outside
what this catalog covers.

## §12 Namespaces — 2 rules

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-035 | 12.2 | The NodeIds of Nodes not defined in this specification shall not use the standard namespaces. | Gap | "All *NodeIds* of *Nodes* not defined in this specification shall not use the standard namespaces." A genuine and cheaply checkable rule about vendor extensions: a node the vendor added must not claim namespace 0 or the DI namespace. `base:hasNamespace` is emitted on every node (412 occurrences in the DI graph), and the baseline nodeset already carries the standard namespaces to compare against, so the shape needs no external data. The extension-governance counterpart of Pumps' PU-005 — worth implementing alongside it. |
| DI-036 | 12.2 | The standard namespaces shall have fixed indices. | N/A | Listed under §5 above with the other Server-configuration entries. |

§12.1 (Namespace Metadata) records the DI namespace URI, version and publication
date. Descriptive.

## Annexes — no rules

Annex A is normative but is the nodeset and supplementary files themselves — the
artefact this suite consumes, not a statement about it. Annex B (examples:
FunctionalGroup usage, the Identification group, and six software-update
sequences) and Annex C (guidelines for building companion specifications on DI,
combining them, and managing Variables defined in several places) are both
informative. Annex C is worth reading for anyone extending this suite to another
DI-based specification — it is the OPC Foundation's own version of the advice in
`adding-a-validation-specification.md` — but it contains nothing to enforce.

---

## What the full pass changed

Twelve rules became thirty-six, and the shape of the specification looks
different from what the partial pass suggested.

**Twenty-one rules are checkable today**, against seven in Machinery and six in
Pumps. The partial catalog found six of them. Everything in §6, §7, §9 and §10 —
eleven rules, nine of them enforceable — was missed entirely, because the partial
pass had prioritised the sections whose *names* sounded structural (Device model,
Communication model) over the ones that actually define ReferenceTypes and
patterns.

**DI-014 is the best first shape in the suite**, and it was not in the partial
catalog. `ValueRank > 0` implies `ArrayDimensions`: two attributes, both already
emitted, no transcription, no instance values, no modality doubt, and it holds
for every specification the project will ever catalogue.

**Two rules are Blocked, both on missing attributes** (DI-015 on `Executable`,
DI-017 on `WriteMask`). Machinery is blocked on `Executable` too. Two
specifications independently blocked on the same attribute turns "the parser
could extract more" from an observation into a work item.

**Three shape families are new to the project**: same-type-across-a-reference
(DI-019), same-DataType-across-Properties (DI-033), and namespace provenance
(DI-035). None has an analogue in the Part 3 suite, so each is a genuine
extension of what the runner has been shown to handle.

**Seven rules are N/A**, concentrated in §8, where an entire large section of a
specification turns out to be almost entirely Client behaviour and Method
semantics. Recording that is what stops the next reader spending a day in §8
looking for shapes.

**§8.5–8.7 remain unread.** §8.6 defines the `UpdateParent` and `CanUpdate`
ReferenceTypes, and ReferenceType definitions are exactly where Part 3 finds
source/target NodeClass rules. That is the first thing to pick up on the next
pass through this specification.
