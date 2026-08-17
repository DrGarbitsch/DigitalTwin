# Validation Rule Catalog — OPC 40223 (Pumps and Vacuum Pumps)

First pass over the Pumps companion specification. Same conventions as the
[DI catalog](./validation-rules-di.md), including its status legend.

Source: [OPC 40223, v1.00](https://reference.opcfoundation.org/Pumps/v100/docs/),
sections 6 (information model overview and extension rules) and 7 (ObjectTypes).

Manifest: [`../validation/specs/opc-40223-pumps/spec.json`](../validation/specs/opc-40223-pumps/spec.json).
Depends on `opc-40001-1-machinery` → `opc-10000-100-devices` →
`opc-10000-3-address-space`; Pumps sits at the end of the
longest dependency chain in the suite.

**Nothing here is enforced yet** — catalogued only, no shapes, no fixtures.

**Coverage note.** Sections 4 and 5 were read and produced no rules: §4 is
introductory prose about pumps and about OPC UA itself, and §5 is use cases
written in "the Pump should provide" language. §7 is 51 ObjectType definitions;
its normative content is the Mandatory/Optional columns of the definition tables
rather than "shall" sentences, which is why PU-006 below is the only rule taken
from it. Sections 8 (DataTypes) and 9 (Profiles) have not been read yet.

## §6.2 What may be instantiated

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| PU-001 | 6.2.3 | A FunctionalGroup that would have no Variables, Objects or Methods if instantiated shall not be instantiated. | Gap | "A *FunctionalGroup* that would have no *Variables*, *Objects*, or *Methods* if instantiated **shall not be instantiated**." An empty-container rule, and a clean one: find instances of `di:FunctionalGroupType` (or a subtype) with no organized members and no components. Shares its zero-test idiom with DI-004 — `FILTER NOT EXISTS`, never `COUNT` over an `OPTIONAL`. Worth implementing in this spec first: it is self-contained, needs no reachability path, and its fixtures are small. |
| PU-002 | 6.2.2 | Where the specification says a unit does not apply, the `0:EngineeringUnits` Property is either not instantiated at all, or its Value Attribute shall be Null. | Instance-level | "the 0:EngineeringUnits *Property* should not be instantiated, or the Value *Attribute* **shall be Null**." A disjunction — absent *or* null — so the shape must not simply require absence. Needs an instance fixture carrying values; `base:hasValue` is emitted. |
| PU-003 | 6.2.2 | The default values the specification names for `0:EngineeringUnits` shall be used. | Advanced | "To comply with this Companion Specification, the default values specified **shall be used** for the 0:EngineeringUnits *Property*." Real and normative, but the constraint is a table of per-Variable defaults in the spec text. Implementing it means transcribing that table into the shape or into a side file, and a transcribed table is exactly what the Part 3 catalog's confidence note warns about. Not a first rule. |

## §6.3 Extending the model

These two are the most interesting rules in the specification, because they
constrain *what a manufacturer may add* rather than what the standard itself
defines — and a companion spec's own nodeset can never violate them. They only
bite on a vendor model, which makes them the clearest example in the suite of a
rule needing an instance fixture rather than a type fixture.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| PU-004 | 6.3 | Additional Variables, Objects or Methods shall be added to an appropriate FunctionalGroup; if none fits, a new Object shall be created for them. | Gap | "the additional *Variables*, *Objects*, or *Methods* **shall be added to** an appropriate *FunctionalGroup*" and "If there is no *FunctionalGroup* available the *Variables*, *Objects*, and *Methods* fit in, the manufacturer or system integrator **shall create** a new *Object*." In graph terms: no extension node hangs off a pump without being organized by some FunctionalGroup. "Appropriate" is not machine-checkable; "organized by *some* FunctionalGroup" is, and is the enforceable core of the rule. Say so in the shape's header comment — a shape that silently implements less than its rule states is how a catalog starts lying. |
| PU-005 | 6.3 | No new Variables, Objects or Methods shall be created that are already available in this specification. | Gap | "In general, no new *Variables*, *Objects*, or *Methods* **shall be created** that are already available in this specification." A BrowseName-collision check against the Pumps vocabulary — and uniquely cheap here, because the Pumps nodeset is *already in the data graph* as this spec's `commonNodeset`. The shape compares an extension node's BrowseName against the BrowseNames the specification defines, with no external list to maintain. Note the hedge "In general" in the source text: confirm against primary text whether the spec names exceptions before treating this as a hard constraint. |

## §7 ObjectTypes

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| PU-006 | 7.1 | `PumpType` is a subtype of DI's `TopologyElementType`, so every rule that holds for a TopologyElement holds for a pump. | Inherited | Verified locally rather than from the spec text: `pumps.owl.ttl` carries `pumps:PumpType rdfs:subClassOf di:TopologyElementType`. Not a rule to implement — a rule to *inherit*. It is the reason the `opc-40223-pumps` spec declares `dependsOn: opc-40001-1-machinery` (and transitively `opc-10000-100-devices`), and the reason the cross check has to merge shapes up the dependency chain: a pump fixture that violates DI-001 or DI-004 is a genuine failure, and a Pumps-only shape set would never see it. |

## What this catalog says about the suite

Pumps contributes only one rule family the other specs do not have — extension
governance (PU-004, PU-005), which constrains vendor additions rather than the
standard's own model. Everything else it needs, it inherits: PumpType is a DI
TopologyElement, so DI's FunctionalGroup, ParameterSet and DeviceSet rules apply
to pumps unchanged.

That is the payoff of the dependency chain, and the argument for building it
before writing shapes. Six catalogued rules understate what a pumps suite
would actually check, because a pump fixture validated against the merged
merged shape set of all four specifications is tested against all
twenty-eight rules in the four catalogs, not against these six.
