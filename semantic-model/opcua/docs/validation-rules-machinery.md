# Validation Rule Catalog — OPC 40001-1 (Machinery Basic Building Blocks)

First pass over the Machinery companion specification. Same conventions as the
[DI catalog](./validation-rules-di.md), including its status legend.

Source: [OPC 40001-1, v1.03](https://reference.opcfoundation.org/Machinery/v103/docs/),
sections 5 (use cases), 6 (building blocks), 8 (identification), 9 (Machines),
11 (components).

Manifest:
[`../validation/specs/opc-40001-1-machinery/spec.json`](../validation/specs/opc-40001-1-machinery/spec.json).
Depends on `opc-10000-100-devices`, which depends on `opc-10000-3-address-space`.

**Nothing here is enforced yet** — catalogued only, no shapes, no fixtures.

**Confidence note.** Section numbers below come from a structured reading of the
online specification rather than from the PDF, and Machinery's numbering moved
between versions. Re-verify each subclause against primary text before writing
its shape — the same discipline the Part 3 catalog applies to itself. MA-010 in
particular is marked *Needs verification* because which building blocks are
mandatory is exactly the kind of table that a secondary reading gets wrong.

## §6.3 Building blocks — the structural core of the specification

This is where Machinery earns a rule suite. The building-block pattern is a
convention about *how things are referenced*, and conventions about reference
topology are invisible to schema validation and to most modelling tools.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-001 | 6.3 | Each Object or ObjectType representing a MachineryItem that supports the AddIns shall have an Object of type FolderType (or a subtype) with the BrowseName `MachineryBuildingBlocks`. | Gap | "Each *Object* or *ObjectType* representing a *MachineryItem* supporting the AddIns shall have an *Object* of type *FolderType* or a subtype with the *BrowseName* 'MachineryBuildingBlocks'." Two conditions in one: the BrowseName, and the type definition being FolderType *or a subtype* — so the shape needs `rdfs:subClassOf*`, not equality. `base:hasBrowseName` is on every translated node. |
| MA-002 | 6.3 | Every AddIn defined by this specification shall be referenced with `HasAddIn` (or a subtype) **directly** from the Object or ObjectType representing the MachineryItem, **and additionally** from the MachineryBuildingBlocks Object. | Gap | "Those AddIns shall be referenced directly from the *Object* or *ObjectType* representing the *MachineryItem*, and shall be referenced in addition by the *MachineryBuildingBlocks* Object." The highest-value rule in this catalog: a genuine double-reference obligation that nothing else in the toolchain checks, and one that a model can violate while looking perfectly reasonable in a browser. `opcua:HasAddIn` is present in the translated core ontology, so the vocabulary is there. Traverse `rdfs:subPropertyOf* opcua:HasAddIn`. |
| MA-010 | 6.3 | The building blocks the specification marks mandatory are referenced by every MachineryItem. | Needs verification | A secondary reading lists MachineryItemState, MachineryOperationMode, OperationCounters, LifetimeCounters, Monitoring, MachineryEquipment and Notifications as mandatory. That is more than expected — most building blocks in 40001-1 are optional, applied per profile. Read the table in primary text and split this into per-block rules before implementing anything; a shape written from this row as it stands would fire on conforming models. |

## §8 Identification

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-004 | 8.2 | `Manufacturer` and `SerialNumber` are mandatory on MachineryItemIdentification. | Push down | Same finding as DI-007: the obligation is Part 3's Mandatory-ModellingRule rule, not a Machinery rule. Two specifications independently asking for the same shape is the signal that it belongs in `opc-10000-3-address-space`. Implement it once there and this row closes for free. |
| MA-005 | 8.2 | `MonthOfConstruction` shall only be provided if `YearOfConstruction` is provided as well. | Gap | "The *MonthOfConstruction* shall only be provided, if the *YearOfConstruction* is provided as well." A conditional-presence constraint, a shape family the Part 3 suite has no example of yet, and an unusually good fixture: one `pass-` case provides neither Property, the other provides both, and the `fail-` case provides only the month. |
| MA-006 | 8.6 | `ProductInstanceUri` is mandatory and read-only on a machine (as opposed to a MachineryItem generally). | Instance-level | Checkable: `base:hasAccessLevel` *is* extracted by the parser (15 occurrences across the translated DI and Machinery graphs), so the read-only half has data behind it. Confirm how `AccessLevelType` is encoded as a content class before writing the constraint — it is not a plain literal. The mandatory half is again DI-007's rule. |
| MA-007 | 8.2 | `YearOfConstruction` shall be a four-digit number and shall never change during the life-cycle of the MachineryItem. | Instance-level (split) | Two rules wearing one sentence. "Four digits" is a value constraint, checkable on an instance fixture via `base:hasValue`. "Never changes" is temporal and belongs with the N/A entries — this pipeline validates one snapshot, not a history. Split them before implementing; do not let the temporal half justify skipping the checkable half. |
| MA-009 | 8.3, 8.5 | Servers shall support at least 40 Unicode characters for AssetId and ComponentName, at least 60 for Location, and at least two locales for ComponentName. | N/A | A Server capability, not an address-space shape. There is nothing in a nodeset that could satisfy or violate it. |

## §9, §11 Finding machines and their components

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| MA-003 | 9 | Every machine shall be reachable from the `Machines` Object. | Gap | The specification's stated use case is "all machines shall be easy to find in an OPC UA Server", realised by the Machines Object. Structurally identical to DI-002: reachability from a named anchor over hierarchical References. Write DI-002's shape parameterised on (anchor, type) and this row is a second instantiation of it rather than a second shape. |
| MA-008 | 11.2 | All components of a machine shall be reachable, via MachineComponentsType. | Gap | Third instance of the same reachability family. Three rules across two specifications sharing one shape is the argument for making that shape reusable rather than copying SPARQL between files. |

## What this catalog says about the suite

Three of ten rules (MA-003, MA-008, and DI-002 next door) are the same
reachability shape with different anchors. Two (MA-004, DI-007) are the same
Part 3 rule seen from two companion specs. That is the pattern worth noticing
before writing any SHACL: **a companion specification adds fewer genuinely new
shapes than it adds rules**, and most of what it does add is either a reachability
constraint or a reference-topology convention like MA-002.
