# Validation Rule Catalog — OPC 40223 (Pumps and Vacuum Pumps)

Complete first pass over the Pumps companion specification: every section from §1
to §10 and the three annexes was read, and each one either yields rules or is
recorded below with the reason it does not.

Source: [OPC 40223, v1.00](https://reference.opcfoundation.org/Pumps/v100/docs/).

Manifest:
[`../validation/specs/opc-40223-pumps/spec.jsonld`](../validation/specs/opc-40223-pumps/spec.jsonld).
Depends on `opc-40001-1-machinery` → `opc-10000-100-devices` →
`opc-10000-3-address-space`. Pumps sits at the end of the longest dependency
chain in the suite, and — as the inheritance rules below show — that is where
most of its validation comes from.

**Nothing here is enforced yet** — catalogued only, no shapes, no fixtures.
16 rules, of which 6 are checkable against the translated graph today.

Status legend: as in the [DI catalog](./validation-rules-di.md#status-legend).

## Confidence and coverage

**Two corrections to the partial catalog, both from modal verbs.** A second
reading of §6.2.2 gives *"If no value is specified, the `0:EngineeringUnits`
Property **shall not** be instantiated, or the Value Attribute **shall** be
Null"* — stronger than the "should not" the first reading reported, so PU-002 is
a real constraint. The same sentence pair gives *"the default values specified
**should** be used"*, which is weaker than the "shall be used" first reported.
PU-003 therefore drops from *Advanced* to *N/A (advisory)* and needs no shape at
all — the opposite of what the partial catalog said.

**§7 is covered structurally but sampled textually.** It is 51 ObjectType
definitions, and the online rendering truncates §7.1 in particular. Every type's
*structure* is nonetheless verified, because the translated `pumps.owl.ttl`
carries all 51 — subtype relations, and 9104 `HasModellingRule` references
recording every Mandatory/Optional marking. What is sampled rather than
exhaustive is the *prose* between the tables: §7.34 and §7.36 were read in full,
§7.1 only via the translated ontology. §7.36 turned up one constraint sentence
(PU-010) that exists only in that prose, so assume others are hiding in the
other 48 subsections.

---

## §1 Scope, §2 Normative references — no rules

Standard front matter.

## §3 Terms, definitions and conventions — 3 rules

§3.1–3.2 define five terms (PumpClass, FunctionalGroup, KindOfQuantity, Port,
Pump). §3.3's conventions constrain the Pumps nodeset itself, exactly as DI's
§3.3 and Machinery's §3.4 do — the third specification in a row to carry this
boilerplate, and the third to carry it near-verbatim.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| PU-007 | 3.3.3.3, 3.3.3.4 | If a Variable's or VariableType's ValueRank specifies an array of a specific dimension (ValueRank > 0), the ArrayDimensions Attribute shall be specified. | Gap | Word-for-word DI-014. Three specifications now state the same rule, which settles the question DI-014 raised: implement it once in `opc-10000-3-address-space` and let all three inherit it. Cheap either way — both attributes are already emitted. |
| PU-008 | 3.3.3.1–3.3.3.3 | For every Node, Object and Variable specified in this specification, the Attributes named in Tables 4–6 shall be set as those tables specify. | Gap | DI-013 and MA-011 again. Same transcription caveat: implement the attributes that matter rather than the whole table. |
| PU-009 | 3.3.3.5 | All Methods defined in this specification shall be executable unless defined otherwise. | Blocked | The `Executable` Attribute is not extracted by `lib/nodesetparser.py`. **Third** specification blocked on it, after DI-015 and MA-023. |

## §4 General information, §5 Use cases — no rules

§4 introduces pumps and then OPC UA itself. §5's four use cases (Device
Identification, Configuration, Maintenance Management, Operation) are written as
"the Pump should provide" — aspirational, and realised by §7's types.

## §6 Information model overview — 5 rules

§6.1 (Modelling Concepts, on asset administration shells) and §6.2.1 (Ports)
are descriptive. The rest is the most rule-dense part of the specification.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| PU-001 | 6.2.3 | A FunctionalGroup that would have no Variables, Objects or Methods if instantiated shall not be instantiated. | Gap | An empty-container rule, and the best first shape here: self-contained, no reachability path, small fixtures. Its reach is much wider than it looks — **34 of the Pumps ObjectTypes are subtypes of `di:FunctionalGroupType`** (counted in `pumps.owl.ttl`), so this one shape polices most of the specification's type inventory. Shares its zero-test idiom with DI-004: `FILTER NOT EXISTS`, never `COUNT` over an `OPTIONAL`. |
| PU-002 | 6.2.2 | Where no value is specified, the `0:EngineeringUnits` Property shall not be instantiated, or its Value Attribute shall be Null. | Instance-level | **Corrected**: the first reading had "should not be instantiated", making the first branch advisory. It is "shall not". Still a disjunction — absent *or* null — so the shape must not simply require absence, and both `pass-` fixtures matter: one omitting the Property, one carrying it with a Null Value. |
| PU-003 | 6.2.2 | The default values the specification names for `0:EngineeringUnits` should be used. | N/A (advisory) | **Corrected**: catalogued as *Advanced* on a first reading of "shall be used". The second reading gives "**should** be used", which makes it a recommendation. This is the happier kind of correction — it removes the most expensive rule in the catalog, the one that would have needed a per-Variable table transcribed out of the spec text. |
| PU-004 | 6.3 | Additional Variables, Objects or Methods shall be added to an appropriate FunctionalGroup; where none fits, a new Object shall be created for them. | Gap | "Appropriate" is not machine-checkable; "organized by *some* FunctionalGroup" is, and is the enforceable core. Say so in the shape's header — a shape that silently implements less than its rule states is how a catalog starts lying. |
| PU-005 | 6.3 | No new Variables, Objects or Methods shall be created that are already available in this specification. | Gap | A BrowseName-collision check against the Pumps vocabulary, and uniquely cheap here because the Pumps nodeset *is* this spec's `baselineNodeset` — the comparison set is already in the data graph, with no external list to maintain. Note the hedge "In general" in the source text. The extension-governance counterpart of DI-035/PU-015. |

## §7 OPC UA ObjectTypes — 5 rules

Fifty-one ObjectType definitions: the pump itself, nameplates and identification,
five maintenance types, eight supervision types, configuration and operational
groups, signals and measurements, multi-pump management, and thirteen port and
connection types. Almost all of it is definition tables, and — checked against
`pumps.owl.ttl` — almost all components are Optional.

Four of the five rules below are **inheritance facts**, verified locally rather
than quoted from the spec text. They are catalogued as rules because they are
what makes the dependency chain pay: each one imports another specification's
enforcement into this one.

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| PU-006 | 7.1 | `PumpType` is a subtype of DI's `TopologyElementType`, so every rule holding for a TopologyElement holds for a pump. | Inherited | Verified in `pumps.owl.ttl`: `pumps:PumpType rdfs:subClassOf di:TopologyElementType`. Nothing to implement — this is why DI-001, DI-004 and the DeviceSet rules apply to pumps unchanged, and why a Pumps-only shape set would be nearly worthless. |
| PU-011 | 7 (34 types) | The bulk of the Pumps type inventory is FunctionalGroups, so DI's FunctionalGroup rules govern most of this specification. | Inherited | 34 Pumps ObjectTypes are `rdfs:subClassOf di:FunctionalGroupType`, counted in the translated ontology — including `MultiPumpType` (§7.34), the configuration and operational groups, and all eight supervision types. DI-001 (BrowseName uniqueness across an `Organizes` group) therefore has 34 type families to police here, and PU-001 has the same reach. |
| PU-012 | 7.4 | `PumpIdentificationType` is a subtype of Machinery's `MachineIdentificationType`, so Machinery's identification rules apply to pumps. | Inherited | Verified: `pumps:PumpIdentificationType rdfs:subClassOf machinery:MachineIdentificationType`. This is the concrete justification for `dependsOn: opc-40001-1-machinery` — without it MA-004, MA-006 and MA-013 would never be checked against a pump. |
| PU-013 | 7 | The Mandatory components the definition tables mark are present on every instance. | Push down | Part 3's Mandatory-ModellingRule obligation once more, and it has real work to do here: `HasModellingRule` appears 9104 times in the translated Pumps graph. The same shape that closes DI-007, MA-004, MA-006 and MA-008 covers all 51 types in this section. |
| PU-010 | 7.36 | A Port with direction `In` may only be connected to a Port with direction `Out` or `InOut`. | Instance-level | The one genuine constraint sentence found in §7's prose, and it is not in any definition table — which is the reason to keep reading the other 48 subsections. A compatibility rule across a connection: read `Direction` (a `PortDirectionEnum`) at both endpoints and reject the illegal pairings. Needs an instance fixture carrying values. Structurally the same shape family as DI-019, which compares the two ends of an `IsOnline` Reference. |

`PortType` itself (§7.36) is a subtype of `0:BaseObjectType` with all three
components optional, and `MultiPumpType` (§7.34) a subtype of DI's
`FunctionalGroupType` with every component optional — so neither contributes a
presence rule of its own.

## §8 OPC UA DataTypes — 1 rule

Nineteen DataTypes: one structure (`PhysicalAddressDataType`), five OptionSets
and thirteen enumerations. No normative sentences — but the enumerations
constrain by definition, which is a rule even though no sentence says "shall".

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| PU-014 | 8 | A Variable whose DataType is one of this specification's enumerations or OptionSets carries a value drawn from that definition. | Push down | Not a Pumps rule: it is DataType conformance, which holds for every enumerated DataType in every specification — DI-008 (DeviceHealth and NE107) is the same rule wearing a different name. The enum machinery is emitted (`base:hasEnumValue`, `base:hasValueList`, `base:hasDatatype`), so one generic shape in `opc-10000-3-address-space` would cover all nineteen types here and DI-008 next door. |

## §9 Profiles and Conformance Units — no rules

Conformance units are phrased descriptively ("The PumpType is implemented", "At
least one … is implemented") and the Facet tables use M/O markings rather than
imperative language. §9 bundles requirements established in §7 and §8 rather
than adding any; the two Server Facets (Pump Base, Pump Advanced) delegate their
structural content to the sections they cite.

One thing here is not covered elsewhere: the conformance units add semantic
constraints about `GeneratesEvent` References targeting particular alarm types.
That is profile-level validation — "does this model satisfy the Pump Advanced
Server Profile" — and is a different shape of work from per-rule validation.
Recorded as a possible direction, not as a rule. Machinery's §19 ends in exactly
the same place.

## §10 Namespaces — 2 rules

| ID | Section | Rule | Status | Notes |
|---|---|---|---|---|
| PU-015 | 10.2 | The NodeIds of Nodes not defined in this document shall not use the standard namespaces. | Gap | Verbatim DI-035, so two specifications state it and the shape should be written once and parameterised on the namespace set. Cheaply checkable: `base:hasNamespace` is on every translated node and the baseline nodesets carry the standard namespaces to compare against. Table 157 makes the set explicit for Pumps — standard OPC UA, local server, DI, Machinery and Pumps — which is also an independent confirmation of this spec's `dependsOn` chain. |
| PU-016 | 10.2 | The standard namespaces carry fixed namespace indices. | N/A | A Server namespace-table statement. `nodeset2owl.py` works in namespace URIs, not indices, so the concept does not survive translation — correctly so. |

## Annexes — no rules

Annex A is normative but is the namespace and identifier tables themselves.
Annex B (an example model) and Annex C (bibliography) are informative.

---

## What the full pass changed

Six rules became sixteen, and the two corrections both moved rules in the
direction of *less* work.

**PU-003 disappeared as an implementation task.** It was the most expensive rule
in the catalog — a per-Variable table of EngineeringUnits defaults that would
have had to be transcribed out of the spec text — and the sentence turns out to
say "should". Catching that before anyone started is most of the value of doing
a modality-sensitive reading at all.

**PU-002 got stronger**, from a half-advisory disjunction to a real constraint.

**Only six rules are checkable here, against twenty-one in DI and seven in
Machinery — and that is the correct result, not a disappointment.** Pumps is a
thin specification over a deep stack. Four of its sixteen rules are inheritance
facts, and they are the interesting ones: `PumpType` is a DI TopologyElement,
`PumpIdentificationType` is a Machinery MachineIdentification, and 34 of its 51
ObjectTypes are DI FunctionalGroups. A pump validated against the merged
`opc-10000-3-address-space + opc-10000-100-devices + opc-40001-1-machinery +
opc-40223-pumps` shape set is tested against all 147 catalogued rules in the four
catalogs. Validated against its own six, it is barely tested at all.

That is the strongest argument yet for making the cross check follow
`dependsOn` — the single change that would turn this catalog from thin into
comprehensive.

**Three specifications now state the same three boilerplate rules** (ValueRank
implies ArrayDimensions; common Attributes per the tables; Methods executable).
The first is the cheapest useful shape in the project and should be written once
in Part 3. The third is blocked in all three, on the same missing `Executable`
Attribute.
