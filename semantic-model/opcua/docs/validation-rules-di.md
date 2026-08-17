# Validation Rule Catalog — OPC 10000-100 (Devices / DI)

First pass over the DI companion specification: identify and name the checkable
rules before any of them are implemented as SHACL. Each rule has a stable ID, the
subclause it was derived from, and a plain-language statement of what would need
to hold in the AddressSpace graph.

Source: [OPC 10000-100, Devices, v1.03](https://reference.opcfoundation.org/DI/v103/docs/),
sections 4 (Device Model) and 5 (Communication and Network Model).

Manifest: [`../validation/specs/opc-10000-100-devices/spec.json`](../validation/specs/opc-10000-100-devices/spec.json).
Method and the shared vocabulary traps:
[`adding-a-validation-specification.md`](./adding-a-validation-specification.md)
and [`../validation/README.md`](../validation/README.md).

**Nothing here is enforced yet.** Every rule below is catalogued only: no shape,
no fixtures. The manifest lists them with a `status` and no `shape` key, so
`run_suite.py` skips the specification entirely and `--coverage` reports
`0 of 12`.

## Status legend

Shared with the Machinery and Pumps catalogs.

| Status | Meaning |
|---|---|
| **Gap** | Checkable today — the data the rule needs is already in the translated graph — but no shape exists yet. |
| **Instance-level** | Real and checkable, but only against a nodeset that *instantiates* the types, not one that defines them. Needs an instance fixture. |
| **Push down** | Not really a rule of this specification: it is a core (Part 3) rule surfacing here. Implement it once in `opc-10000-3-address-space` and every companion spec inherits it. |
| **Advanced** | Structurally real but not a simple shape — needs a table from the spec text, a recursive walk, or a cross-consistency check. |
| **Needs verification** | Extracted from a secondary reading of the spec text; re-read the primary subclause before writing a shape. |
| **N/A** | Normative in the spec, but not a static property of one AddressSpace snapshot (runtime behaviour, Server capability, advisory "should"). Recorded so it is not re-derived later. |

## §4.3–4.4 TopologyElement, ParameterSet, MethodSet, FunctionalGroups

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-001 | 4.4.1 | All BrowseNames of Nodes referenced by one FunctionalGroup with an `Organizes` Reference shall be unique. | Gap | Direct analog of AS-006, which scopes the same uniqueness test to a Node's Properties. Compare (name, namespace) pairs and scope to one owner; traverse `rdfs:subPropertyOf* opcua:Organizes` so a subtype of `Organizes` still counts. Cheapest first rule to implement in this spec — the shape it most resembles is already working. |
| DI-004 | 4.3 | The MethodSet Object is only present if it includes at least one Method. | Gap | "The *MethodSet* is only available if it includes at least one *Method*." A `FILTER NOT EXISTS` over components with `opcua:MethodNodeClass`. Note the Part 3 idiom: never `COUNT` over an `OPTIONAL` for a zero test. |
| DI-012 | 4.4.1 | A FunctionalGroup that can be hidden on an instance shall carry an appropriate ModellingRule on the TypeDefinition. | Advanced | "If a *FunctionalGroup* can be hidden on an instance the TypeDefinition shall use an appropriate ModellingRule." "Appropriate" is not enumerated in the sentence; determining which ModellingRules qualify needs the surrounding text. Not a shape until that is pinned down. |
| DI-011 | 4.4.2 | Servers exposing a FunctionalGroup for a described purpose use the well-known BrowseName. | N/A (advisory) | "should", not "shall". Recorded so a future pass does not promote it to a constraint. |

## §4.5–4.7 Devices, DeviceHealth, ComponentType and DeviceType

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-007 | 4.7 | The Properties DeviceType declares Mandatory are present on every DeviceType instance. | Push down | DeviceType declares SerialNumber, Manufacturer, Model, DeviceManual, DeviceRevision, SoftwareRevision and HardwareRevision as mandatory. But the *obligation* is Part 3's: an instance must carry every InstanceDeclaration whose ModellingRule is `Mandatory`. Implementing it in `opc-10000-3-address-space` covers this rule, MA-004, and the same rule in every companion specification that will ever be added. Highest-leverage shape available to the project. Note the spec's own carve-out: "vendors shall provide the following defaults" where a Property is not supported — the Property is still present, so it does not weaken the rule. |
| DI-008 | 4.5.4 | DeviceHealth is one of the five NAMUR NE107 values (NORMAL, FAILURE, CHECK_FUNCTION, OFF_SPEC, MAINTENANCE_REQUIRED). | Instance-level | `base:hasValue` and the enum machinery (`base:hasEnumValue`, `base:hasValueList`) are all emitted by `nodeset2owl.py`, so this is checkable — but only against a fixture that carries an actual value. A type-only nodeset has nothing to test. |

## §4.9 DeviceSet — the entry point

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-002 | 4.9 | The DeviceSet Object shall, directly or indirectly, reference every instance of a ComponentType subtype with a hierarchical Reference. | Gap | "The DeviceSet *Object* shall either directly or indirectly reference all instances of a subtype of *ComponentType* with a *Hierarchical Reference*." Reachability from a named anchor over `opcua:HierarchicalReferences` — the first rule in the project needing a `+` property path rather than a fixed number of hops. Write the shape parameterised on (anchor, type), because MA-003 and MA-008 are the same shape with different anchors. |
| DI-003 | 4.9 | For a complex Device composed of Devices, only the root instance shall be referenced from DeviceSet. | Gap | "For complex *Devices* composed of various components that are also *Devices*, only the root instance shall be referenced from the DeviceSet *Object*." The negative half of DI-002 and the half implementers get wrong: a sub-Device that is already a component of another Device must not *also* hang directly off DeviceSet. Note the two rules pull in opposite directions — a fixture that satisfies one and violates the other is the interesting test case. |

## §5 Communication and Network Model

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| DI-005 | 5.6 | All Networks shall be components of the NetworkSet Object. | Gap | "All *Networks* shall be components of the **NetworkSet** *Object*." Same shape family as DI-002, one hop instead of a path. |
| DI-006 | 5.4 | Every ConnectionPoint shall have the inverse `ComponentOf` Reference to its Device. | Gap | "*ConnectionPoints* are components of a *Device*, represented by a subtype of *ComponentType*. To allow navigation from a *Network* to the connected *Devices*, the *ConnectionPoints* shall have the inverse *Reference (ComponentOf)* to the *Device*." Inverse References are materialised as forward triples on the source node, so in the translated graph this reads as: every instance of a ConnectionPointType subtype is the target of some `HasComponent`. |
| DI-009 | 5.2 | The BrowseName of each ProtocolType instance defines the Communication Profile. | N/A | "The *BrowseName* of each instance of a *ProtocolType* shall define the *Communication Profile*." Normative, but there is no closed vocabulary of profile names in the graph to check a BrowseName against. Not checkable without an external list, and an external list would go stale. |
| DI-010 | 4.3, 5.3 | Clients shall use LockingServices when making a set of changes that is only consistent once all of them are applied; an InitLock is rejected if a subordinate Device or Network is already locked. | N/A | Client and Server runtime behaviour over time, not a property of one AddressSpace snapshot — the same reasoning that puts Part 3's ModelChangeEvent/NodeVersion co-occurrence rule out of scope. |

## Open questions

- **DI-002 vs DI-003 interaction.** Both are about DeviceSet membership and they
  constrain each other. Implement them as one pair with shared fixtures, so the
  `pass-` case for one is checked against the shape for the other.
- **What lands in `common/`.** DI's nodeset is around a megabyte. Either check in
  the whole thing, or extend the subsetting approach of `tools/make_ns0_subset.py`
  to companion specifications. The second is more in keeping with the project —
  generated, not hand-maintained — but is real work and is not started.
