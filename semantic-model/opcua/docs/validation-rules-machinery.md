# Validation Rule Catalog — OPC 40001-1 (Machinery Basic Building Blocks)

Complete first pass over the Machinery companion specification: every section
from §1 to §20 and the three annexes was read, and each one either yields rules
or is recorded below with the reason it does not. Same conventions as the
[DI catalog](./validation-rules-di.md).

Source: [OPC 40001-1, v1.03](https://reference.opcfoundation.org/Machinery/v103/docs/).

Manifest:
[`../validation/specs/opc-40001-1-machinery/spec.json`](../validation/specs/opc-40001-1-machinery/spec.json).
Depends on `opc-10000-100-devices`, which depends on
`opc-10000-3-address-space`.

**Nothing here is enforced yet** — catalogued only, no shapes, no fixtures.
25 rules, of which 7 are checkable against the translated graph today.

## Status legend

Extends the [DI catalog's legend](./validation-rules-di.md#status-legend) with
one value Part 3 also uses:

| Status | Meaning |
|---|---|
| **Blocked** | Real and static, but `nodeset2owl.py` does not extract the Attribute the rule depends on, so the data never reaches the graph. |

## Confidence, and a conflict worth knowing about

Section numbers and quoted text come from structured readings of the online
specification, not from the PDF. **Two independent readings of §6.3 disagreed on
its modal verb** — one reported "shall have an *Object* of type *FolderType*",
the other "should have". That is the difference between a constraint and a
recommendation, and it decides whether MA-001 and MA-002 are enforceable rules
at all. Both are marked *Needs verification* until the primary text settles it.

The same caution applies to Table 12 (MA-010): both readings agreed on the list
of building blocks under a "Shall be referenced" heading, but a column header is
not a normative sentence, and the list is longer than the specification's
generally optional treatment of building blocks would suggest. Read the table
itself before writing a shape.

Two claims from the previous version of this catalog are corrected below.
MA-003 is a **direct**-reference rule, not a reachability rule — §9.2 says
"referenced directly from this *Object*", so it is not the same shape as DI-002.
And MA-008 turned out to be a mandatory-AddIn obligation from a definition table
rather than a reachability rule; §11 contains no normative sentences at all.

---

## §1 Scope, §2 Normative References — no rules

§1 states what the document covers and §2 lists the standards it references.
Neither contains graph-shape language. Same outcome as Part 3's treatment of
Part 1.

## §3 Terms, Definitions and Conventions — 2 rules

§3.1–3.3 define terms (MachineryItem, MachineryEquipment) and abbreviations, and
carry no constraints. §3.4's conventions do, and they are unusual in this
catalog: they constrain **the Machinery nodeset itself** rather than a vendor
model, so their fixture is a type-level one.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-011 | 3.4.3.1–3.4.3.3 | For every Node, Object and Variable specified in this specification, the Attributes named in Tables 7–9 shall be set as the tables specify; Attributes not marked optional are mandatory and shall be provided. | Gap | "Attributes not marked as optional are mandatory and **shall be provided by a Server**" / "**shall be set as specified in the table**". Checkable in principle against the published Machinery nodeset, which is this spec's `commonNodeset` — but the shape needs the three tables transcribed, so it shares MA-010's and PU-003's transcription risk. Implement the specific attributes that matter (`base:isAbstract`, BrowseName namespace) rather than the whole table at once. |
| MA-023 | 3.4.3.5 | All Methods defined in this specification shall be executable unless their definition says otherwise. | Blocked | The `Executable` Attribute is not extracted by `lib/nodesetparser.py` — no `base:hasExecutable` or equivalent reaches the graph. Nothing to write a shape against until the translator carries it. First genuinely *Blocked* rule in the companion catalogs, and a concrete argument for extending the parser. |

§3.4.2 (NodeIds and BrowseNames) states that the NodeIds in the document are
symbolic names, and imposes nothing on a model. The "NodeId shall not be
writable" sentence in §3.4.3.1 is a Server access-control statement, not an
address-space shape.

## §4 General information, §5 Use Cases — no rules

§4 introduces machinery and then OPC UA itself; §5 states eight use cases in
aspirational form ("all machines **shall be easy to find** in an OPC UA
Server"). The use cases are not themselves checkable — each names the section
that realises it, and those sections are where the rules live. §5.2 points at
§9 (MA-003/MA-013/MA-014), §5.4 at §11, §5.8 at §18.

Recorded so a later pass does not mistake the use-case wording for a rule: the
"shall" in §5 binds the specification's own later sections, not a model.

## §6 Machinery Information Model overview — 3 rules

§6.1 and §6.2 describe the building-block idea and list the blocks; neither
contains a normative sentence. §6.3 is the structural core of the specification
— and the subclause whose modality is in doubt (above).

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-001 | 6.3 | An Object or ObjectType representing a MachineryItem that supports the AddIns has an Object of type FolderType, or a subtype, with the BrowseName `MachineryBuildingBlocks`. | Needs verification | Two conditions — the BrowseName, and the type definition being FolderType *or a subtype*, so `rdfs:subClassOf*` rather than equality. `base:hasBrowseName` is on every translated node, so the data is there. Blocked only on shall-versus-should. |
| MA-002 | 6.3 | Every AddIn this specification defines is referenced with `HasAddIn`, or a subtype, **directly** from the Object or ObjectType representing the MachineryItem, **and in addition** from the MachineryBuildingBlocks Object. | Needs verification | A double-reference obligation: the same AddIn reachable two ways, deliberately. Nothing else in the toolchain checks reference topology like this, and a model can violate it while looking entirely reasonable in a browser — which is what makes it worth the verification effort. `opcua:HasAddIn` is present in the translated core; traverse `rdfs:subPropertyOf*`. Downgraded from *Gap*: the previous version of this catalog called it the highest-value rule here, which was premature while its modal verb is unsettled. |
| MA-010 | 6.2, Table 12 | The building blocks Table 12 places under "Shall be referenced" are referenced by every MachineryItem. | Needs verification | Both readings return the same seven blocks — MachineryItemState, MachineryOperationMode, OperationCounters, LifetimeCounters, Monitoring, MachineryEquipment, Notifications — and place Identification (§8), Component Identification (§10) and Find Components (§11) under "May be referenced". That is the opposite of what the per-section definitions suggest, where identification is the best-established block and the counters are optional. A column header is not a normative sentence; read the table before implementing, and split it into per-block rules when you do. |

## §7 General Recommendations — 3 rules

Small section, disproportionately useful: every one of its three subclauses
produces an entry, and two of them are entries about *not* writing a shape.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-012 | 7.1 | Where a text value is language-neutral, the locale of the LocalizedText shall be null or an empty string. | Instance-level | Checkable, with a caveat that belongs in the shape's header: `lib/nodesetparser.py` turns a LocalizedText into `Literal(text, lang=locale)` and maps a whitespace-only locale to `None`, so in the graph the rule reads "this literal carries no language tag". A whitespace-only locale and a genuinely absent one are indistinguishable after translation — harmless here, because the rule permits both. |
| MA-019 | 7.2 | If the information behind an optional Node is unavailable and the Node would be read-only, the optional Node shall not be provided. | N/A | Normative, and not checkable: "the information is unavailable" is a fact about the machine, not about the address space. A Node's absence is observable; the reason for it is not. |
| MA-020 | 7.3 | Where a TypeDefinition offers several paths to the same Node, let several References lead to that one Node rather than duplicating it. | N/A (advisory) | "it is recommended", not "shall". Recorded because it is the Machinery-level echo of Part 3's AS-012, which *is* normative for directly-connected InstanceDeclaration pairs — if a shape is ever wanted for this, AS-012 is where it belongs, not here. |

## §8 Machine Identification and Nameplate — 8 rules

The most rule-dense section. §8.1 is an overview; §8.2–8.6 define the two
nameplate Interfaces and the two Identification ObjectTypes.

Mandatory/optional, confirmed from the definition tables:

- **MachineryItemIdentificationType (8.3)** — Mandatory: `Manufacturer`,
  `SerialNumber`. Everything else optional.
- **MachineIdentificationType (8.6)** — Mandatory: `Manufacturer`,
  `SerialNumber`, `ProductInstanceUri`. Everything else optional.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-004 | 8.3 | `Manufacturer` and `SerialNumber` are present on every MachineryItemIdentification instance. | Push down | The obligation is Part 3's: an instance carries every InstanceDeclaration whose ModellingRule is `Mandatory`. Implement once in `opc-10000-3-address-space` and this closes, along with DI-007. |
| MA-006 | 8.6 | `ProductInstanceUri` is present on every MachineIdentification instance, and is read-only. | Push down + instance-level | Two halves. Presence is MA-004's rule again. Read-only is separately checkable: `base:hasAccessLevel` *is* extracted (15 occurrences across the translated DI and Machinery graphs); confirm how `AccessLevelType` is encoded as a content class first, since it is not a plain literal. |
| MA-005 | 8.2 | `MonthOfConstruction` shall only be provided if `YearOfConstruction` is provided as well. | Gap | A conditional-presence constraint, a shape family the Part 3 suite has no example of, and an unusually clean fixture set: one `pass-` provides neither Property, the other provides both, and the `fail-` provides only the month. Best first shape in this specification — no transcription, no modality doubt, no instance values needed. |
| MA-007 | 8.2 | `YearOfConstruction` shall be a four-digit number, and shall never change during the life-cycle of the MachineryItem. | Instance-level (split) | Two rules in one sentence. "Four digits" is a value constraint on `base:hasValue`, checkable on an instance fixture. "Never changes" is temporal and belongs with the N/A entries — this pipeline validates one snapshot. Split them; do not let the temporal half justify dropping the checkable half. |
| MA-017 | 8.2 | `ProductInstanceUri` is restricted to 255 characters. | Instance-level | A plain string-length constraint on `base:hasValue`, and the cheapest instance-level rule in the catalog. The surrounding sentence — that global uniqueness is the manufacturer's responsibility — is not checkable. |
| MA-024 | 8.2 | Clients shall not assume the uniqueness of the manufacturer based on `ProductInstanceUri`. | N/A | Binds Client behaviour. Nothing in an address space can satisfy or violate it. |
| MA-009 | 8.5, 8.6 | Servers shall support at least 40 Unicode characters for `AssetId` and `ComponentName`, at least 60 for `Location`, and at least two locales for `ComponentName`. | N/A | A Server capability. A nodeset carries values, not the range of values the Server would accept. |
| MA-025 | 8.3, 8.4, 8.6 | Properties inherited from `IMachineryItemVendorNameplateType` shall be used as that Interface defines them. | Push down | An interface-conformance statement, which in Part 3 terms is the override rules AS-010 and AS-044: a subtype may narrow a Node but not contradict it. Already covered conceptually by the Virtual-Types/HermiT machinery. Nothing Machinery-specific to implement. |

## §9 Finding all Machines in a Server — 4 rules

Four normative sentences in one subclause, three of them structural. The richest
single subclause in the specification.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-003 | 9.2 | Every Object representing a Machine that the Server manages shall be referenced **directly** from the `Machines` Object with an `Organizes` Reference or a subtype of it. | Gap | "shall be referenced **directly** from this *Object*". **Correction:** the previous version of this catalog treated this as reachability, the same shape as DI-002. It is not — a machine two hierarchical hops below `Machines` violates this rule, and a reachability shape would pass it. One hop, `rdfs:subPropertyOf* opcua:Organizes`. |
| MA-013 | 9.2 | Every Object referenced from the `Machines` Object shall provide the `MachineIdentificationType` AddIn. | Gap | "In order to identify the referenced *Objects* as representations of *Machines*, each of those *Objects* shall provide the *MachineIdentificationType* *AddIn*." Pairs with MA-003: MA-003 says which Objects must be there, MA-013 says what those Objects must carry. One fixture can exercise both, and the `fail-` case for either is a good `pass-` candidate for the other. |
| MA-014 | 9.2 | The `Machines` Object shall be referenced from the `0:Objects` Object with an `Organizes` Reference. | Gap | Anchors the whole entry point to a fixed NS0 node, so the shape needs `Objects` (i=85) in the baseline nodeset — a concrete addition to whatever ends up in `specs/opc-40001-1-machinery/common/`. |
| MA-022 | 9.2 | Clients aware of this standardized Object shall not access it via its parent but directly via its standardized NodeId. | N/A | Client behaviour. |

## §10 Component Identification and Nameplate — 1 rule

§10.1 is an overview. §10.2 defines `MachineryComponentIdentificationType` as a
non-abstract subtype of `MachineryItemIdentificationType` whose only addition,
`DeviceRevision`, is optional — so the type contributes no presence rules of its
own beyond MA-004's, which it inherits.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-021 | 10.2 | Machine vendors shall not use the `2:ComponentName` Property to manage their own identification of the component. | N/A | A "shall not" about *purpose*. The Property being present and populated is compliant or not depending on who wrote it and why, which no graph carries. The two neighbouring statements — that a machine vendor should not generate `ProductInstanceUri` for components, and should not change `InitialOperationDate` — are "should", and advisory besides. |

## §11 Finding all identifiable Components of a Machine — 1 rule

**No normative sentences at all.** §11.1 is descriptive ("provides", "may
organize", "does not preclude") and §11.2 is a definition table. The one
obligation is in that table.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-008 | 11.2 | Every component under `MachineComponentsType` carries a mandatory `HasAddIn` Reference to an `Identification` Object of type `MachineryItemIdentificationType`. | Push down | **Correction:** previously catalogued as a reachability rule about finding all components. It is not — it is the Mandatory marking in Table 27, so it is Part 3's Mandatory-ModellingRule obligation once more. Third rule in this catalog that closes when that one shape is written. |

## §12 MachineryItemState, §13 MachineryOperationMode — no rules

Both define a `FiniteStateMachineType` subtype — four states and sixteen
transitions each — in definition tables, with no normative sentences. §13 is
explicit that transitions between all states exist so that instances may impose
their own constraints, which is the opposite of a constraint to check.

A subtype that *removed* a state would be non-conforming, but that is Part 3's
override rule (AS-010/AS-044, see MA-025), not a Machinery rule. Nothing to add
here.

## §14 Operation Counter — 1 rule

All three Properties — `PowerOnDuration`, `OperationDuration`,
`OperationCycleCounter` — are optional, so there is no presence rule. All three
carry the same behavioural constraint.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-018 | 14.2 | These counter values shall only increase during the life-cycle of the MachineryItem and shall not be reset when it is restarted. | N/A | Monotonicity over time. This pipeline validates one snapshot, and no single snapshot can be non-monotonic — the same reasoning that excludes Part 3's ModelChangeEvent/NodeVersion rule and MA-007's "never changes" half. Worth recording precisely because it *reads* like a strong constraint. |

## §15 Lifetime Counter — 1 rule

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-015 | 15.2 | A `MachineryLifetimeCounterType` instance shall contain at least one lifetime variable. | Gap | "There shall be at least one lifetime variable" (Table 38). A non-empty-container rule — the mirror image of PU-001, which forbids an *empty* FunctionalGroup — so the two share an idiom and should share a reviewer. Members are instances of DI's `LifetimeVariableType`, which puts a second cross-spec dependency in the shape and makes it a good test of whether the merged shape set actually works. |

## §16 Monitoring — 1 rule

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-016 | 16.1, 16.2 | If the `Status` Object is provided, it shall reference the `MachineryItemState` AddIn when the MachineryItem provides one, and the `MachineryOperationMode` AddIn when the MachineryItem provides one. | Gap | Stated twice, in the overview and in Table 41's Status row, which is as close to corroboration as this specification gets. A doubly-conditional rule — the constraint applies only when both the Status Object and the referenced AddIn exist — so both `pass-` fixtures matter: one where neither exists, one where both exist and are correctly referenced. |

## §17 MachineryEquipment, §18 Notifications — no rules

Both are written in recommending language throughout ("should be represented",
"is recommended", "may define"). §17.3's `IMachineryEquipmentType` and §18.2's
`NotificationsType` are definition tables whose entries are optional. §18
explicitly permits notifications as either Events or Objects, which is a choice
offered rather than a constraint imposed.

## §19 Profiles and Conformance Units — no rules

Conformance units are phrased descriptively ("Supports", "There is at least one
instance") and defer their normative content to §8–§18, which this catalog has
already covered. The Facet tables mix address-space requirements with Server
service support; the address-space half is not additional to the sections it
cites.

Worth revisiting only if the suite ever wants to validate *by profile* — "does
this model satisfy the Machinery Machine Identification Server Facet" is a
meaningful question, and a different shape of work from per-rule validation.

## §20 Namespaces — no rules

Namespace metadata (`http://opcfoundation.org/UA/Machinery/`) and guidance on
namespace index handling. Descriptive.

## Annexes — no rules

Annex A is normative but is the nodeset and supplementary files themselves — the
artefact this suite consumes, not a statement about it. Annexes B (examples) and
C (KPI calculation with ISO 22400 and SEMI E10) are informative.

---

## What the full pass changed

Ten rules became twenty-five, but the useful numbers are different ones.

**Seven rules are checkable today** — MA-003, MA-005, MA-011, MA-013, MA-014,
MA-015, MA-016. Only one of them (MA-003) was in the partial catalog, and it was
catalogued wrongly. Reading §9, §15 and §16 properly produced more enforceable
rules than the sections a partial pass had prioritised.

**Four rules are the same Part 3 obligation** — MA-004, MA-006, MA-008, and
DI-007 next door, all close when the Mandatory-ModellingRule shape is written.
The partial catalog found two of them. The case for writing that shape first
strengthens with every specification read.

**Nine rules are N/A, and finding them is the point.** Client behaviour (MA-022,
MA-024), Server capability (MA-009), monotonicity over time (MA-018, and MA-007's
second half), facts not in the graph (MA-019, MA-021), advisory language
(MA-020). A suite that had gone straight to implementation would have discovered
these one at a time, each after someone had started writing a shape.

**One rule is Blocked** (MA-023) and names a specific translator gap: the
`Executable` Attribute is not extracted.

**Three rules hang on unresolved source text** (MA-001, MA-002, MA-010) — all
three structural, all three in §6.3 and Table 12. Resolving that one subclause
against the PDF is the highest-value hour available in this specification.
