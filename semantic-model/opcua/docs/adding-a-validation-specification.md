# Adding a Validation Specification

How the Part 3 validation project is built, and how the same structure carries a
companion specification — worked through with candidate rules extracted from DI
(OPC 10000-100) and Machinery (OPC 40001-1).

This document is the *method*. For the mechanics of writing a single shape —
directory layout, the runner's flags, and the vocabulary traps in the translated
graph — see [`../validation/README.md`](../validation/README.md). For how the
four specifications sit together as a dependency chain, see
[`../validation/specs/README.md`](../validation/specs/README.md).

The catalogs themselves:
[Part 3](../validation/specs/opc-10000-3-address-space/catalog.md) (70 rules, 9 enforced),
[DI](../validation/specs/opc-10000-100-devices/catalog.md) (36, near-complete pass),
[Machinery](../validation/specs/opc-40001-1-machinery/catalog.md) (25, complete pass),
[Pumps](../validation/specs/opc-40223-pumps/catalog.md) (16, complete pass).

---

## 1. What already exists

The work has two halves, and they must not be confused with each other.

The **catalog** is prose: every checkable rule found in OPC 10000-3, given a
stable ID, the subclause it came from, a plain-language statement, and a status.
Seventy rules, built up over five reading passes — including the ones
deliberately marked *not* a rule, so nobody re-derives them later.

The **suite** is executable: for nine of those rules, a SHACL shape, four
NodeSet2 fixtures, and a runner. `make test` runs it.

| Rule | Part 3 § | What it enforces |
|---|---|---|
| AS-005 | 4.5.2, 5.6.3 | A Property is never the source of any hierarchical Reference |
| AS-006 | 4.5.2 | Properties of one Node have distinct BrowseNames |
| AS-008 | 4.6.1, 7.13 | Object/Variable has exactly one HasTypeDefinition |
| AS-031 | 7, 5.6.4 | HasComponent source and target NodeClasses |
| AS-035 | 7.13 | HasTypeDefinition target matches the source's NodeClass |
| AS-039 | 6.2.1 | An instance's type definition is not abstract |
| AS-056 | 5.6.3 | A Property's HasTypeDefinition is PropertyType |
| AS-057 | 5.6.3, 5.6.4 | Property and DataVariable are mutually exclusive |
| AS-063 | 7.17 | HasEventSource chains never return to their origin |

Each test case runs the way a person would run it by hand, which is why the
suite catches translator regressions and not just shape typos:

```
fixture.NodeSet2.xml  →  nodeset2owl.py  →  + full NS0    →  validate.py -s <shape>
one planted defect,      real translator,   70 generated    diffed against the
correct siblings         real CLI           core nodes      .expected file
```

## 2. The structure, and the one idea holding it together

```
validation/
  run_suite.py                    the runner; discovers any spec.jsonld under specs/
  tools/make_ns0_subset.py        regenerates the shared Namespace 0 subset
  specs/
    opc-10000-3-address-space/
      spec.jsonld                   manifest: id, title, catalog, catalogRuleCount,
                                  commonNodeset, rules[{id, section, summary, shape}]
      common/                     the nodeset every fixture here depends on
      shapes/AS-NNN-<slug>.shacl.ttl
      testcases/AS-NNN/
        pass-1-*.NodeSet2.xml     must conform
        pass-2-*.NodeSet2.xml
        fail-1-*.NodeSet2.xml     must produce exactly...
        fail-1-*.NodeSet2.expected   ...these focus nodes and messages
        fail-2-*.NodeSet2.xml
        fail-2-*.NodeSet2.expected
```

The filename is the assertion — a fixture cannot be silently mis-filed — and the
`.expected` file is the review artefact. You generate it with
`--update-expectations` and then *read* it: the question is whether the focus
nodes are exactly the ones you planted, and no others.

### Two checks, and why the second one is the whole point

**Targeted.** Each fixture against its own rule's shape. This proves a rule
detects what it claims to detect.

**Cross.** Every `pass-` fixture of *every* rule, against the merged shape set of
the whole specification. This is what makes the corpus compound. A passing
nodeset written for AS-039 is also just an ordinary conforming address space, so
it becomes a false-positive guard for AS-005, AS-031, AS-057 and everything added
afterwards. Nine rules with four fixtures each are not nine tests; they are nine
detection tests and eighteen shared false-positive guards, and the eighteen grow
every time anyone adds a rule.

The complete baseline nodeset is merged into the data graph of every case, so the
specification's own nodes are held to the same shapes. A shape that
false-positives on the OPC Foundation's own definitions fails the suite before it
ever reaches a customer model.

> **Why the baseline is generated, not written.**
> `common/opcua-ns0-subset.NodeSet2.xml` is 70 nodes extracted from the official
> `Opc.Ua.NodeSet2.xml` by `tools/make_ns0_subset.py`, seeded from a list of
> BrowseNames. NodeIds, `IsAbstract` flags and subtype hierarchies are therefore
> the specification's own and cannot drift. Fixtures stay hermetic — no
> downloads, no 3.6 MB core nodeset — without being fictional.

## 3. The lifecycle, phase by phase

This is a genuine sequence: each phase's output is the next phase's input, and
skipping the first is how rule suites turn into a pile of shapes nobody can audit
against the standard.

### Phase 0 — Catalog the specification, in prose, before writing any SHACL

Read section by section. Extract every "shall" / "shall not" / cardinality
statement. Give each a stable ID, the exact subclause, and a plain-language
statement of what must hold *in the graph*.

Then — and this is the part that pays off later — record what you decided is
**not** a rule and why: advisory "should" language, runtime behaviour,
multi-Server statements this pipeline cannot represent. The Part 3 catalog does
this explicitly, and it is why a re-read does not re-litigate the same sections.

Mark confidence. The Part 3 catalog records which rules were checked against
primary text and which came from a bulk fetch, and it names a transcription error
caught that way. Do the same; a rule catalog that hides its own uncertainty is
worse than one that admits it.

### Phase 1 — Fix the baseline graph the fixtures will stand on

Decide `baselineNodeset`. Fixtures must be hermetic but cannot be standalone,
because `nodeset2owl.py` hard-fails on a DataType or ReferenceType it cannot
resolve. Part 3 uses the generated NS0 subset. A companion specification uses its
own published nodeset plus its dependencies — which for Machinery means NS0, DI,
*and* Machinery.

### Phase 2 — One rule at a time, five steps, no shortcuts

Write the shape → register it in `spec.jsonld` with section and one-line summary →
write two `pass-` and two `fail-` fixtures → generate and *read* the expectations
→ run the whole suite so the cross check sees the new fixtures.

What makes a fixture pair worth having:

- The `pass-` case should be the one a *wrong* implementation would reject.
  AS-039's `pass-2` types an InstanceDeclaration with an abstract type — legal,
  and rejected by any blanket reading of the rule.
- The `fail-` case should plant the defect next to correct siblings, and plant it
  a second way if the rule has a second way to be broken. AS-057's `fail-2` uses
  `HasOrderedComponent`, catching a shape that matched `HasComponent` by name
  instead of by subtype.

### Phase 3 — Wire it in and let the catalog track itself

The runner discovers any directory under `specs/` containing a `spec.jsonld`, so a
new specification needs no code change. `--coverage` reports enforced-versus-
catalogued. The catalog's status column and `spec.jsonld` are the two ends of the
same thread; keep them consistent and "what is actually enforced" is never a
guess.

## 4. Worked example — DI and Machinery

The rules below were extracted from OPC 10000-100 (Devices, v1.03) and
OPC 40001-1 (Machinery, v1.03), and checked against what the pipeline already
produces: `di.owl.ttl` and `machinery.owl.ttl` are both built by
`translate_default_nodesets.make`, so the vocabulary each rule needs can be
verified today rather than assumed.

Status column: **Enforceable** — the graph already carries what the rule needs.
**Instance-level** — needs a fixture that instantiates, not just defines.
**Push down** — not really a rule of this spec; it belongs in Part 3.
**N/A** — real, but not a static graph property.

### DI — OPC 10000-100

| ID | § | Rule | Status | How it lands in the graph |
|---|---|---|---|---|
| DI-001 | 4.4.1 | All BrowseNames of Nodes referenced by a FunctionalGroup via `Organizes` shall be unique | Enforceable | Direct analog of AS-006: group by owner, compare (name, namespace) pairs. Traverse `rdfs:subPropertyOf* opcua:Organizes`. |
| DI-002 | 4.9 | The DeviceSet Object shall reference, directly or indirectly by a hierarchical Reference, every instance of a ComponentType subtype | Enforceable | Reachability from a named node over `opcua:HierarchicalReferences`; the first rule in the project needing a `+` path rather than a fixed hop. |
| DI-003 | 4.9 | For a complex Device, only the root instance shall be referenced from DeviceSet | Enforceable | The negative half of DI-002, and the one implementers get wrong: a sub-Device that is itself a component must not *also* hang off DeviceSet. |
| DI-004 | 4.3 | MethodSet is present only if it holds at least one Method | Enforceable | `FILTER NOT EXISTS` over components with `opcua:MethodNodeClass`. Note the "zero" idiom — never `COUNT` over an `OPTIONAL`. |
| DI-005 | 5.6 | All Networks shall be components of the NetworkSet Object | Enforceable | Same shape family as DI-002, one hop instead of a path. |
| DI-006 | 5.4 | Every ConnectionPoint shall carry the inverse `ComponentOf` Reference to its Device | Enforceable | Inverse references are materialised as forward triples on the source, so this reads as "every ConnectionPointType instance is the target of some HasComponent". |
| DI-007 | 4.7 | The mandatory Properties of DeviceType are present on every instance | Push down | Not a DI rule at heart. It is Part 3's ModellingRule `Mandatory` obligation. Implement it *once* in `opc-10000-3-address-space` and every companion spec inherits it. |
| DI-008 | 4.5.4 | DeviceHealth is one of the five NAMUR NE107 values | Instance-level | `base:hasValue` and the enum machinery (`base:hasEnumValue`) are both emitted; needs a fixture carrying an actual value. |
| DI-009 | 5.2 | A ProtocolType instance's BrowseName defines the Communication Profile | N/A | No closed vocabulary to check against. Catalog it as a non-rule so it is not re-derived. |

### Machinery — OPC 40001-1

| ID | § | Rule | Status | How it lands in the graph |
|---|---|---|---|---|
| MA-001 | 6.3 | A MachineryItem supporting AddIns shall have a FolderType Object with BrowseName `MachineryBuildingBlocks` | Enforceable | BrowseName plus type-definition check; `base:hasBrowseName` is on every translated node. |
| MA-002 | 6.3 | Each standard AddIn shall be referenced *twice* — directly from the MachineryItem *and* from MachineryBuildingBlocks | Enforceable | The highest-value rule of the set: a genuine double-reference obligation that no schema validator catches. `opcua:HasAddIn` is present in the translated core. |
| MA-003 | 9 | Every machine shall be reachable from the `Machines` Object | Enforceable | Same reachability shape as DI-002 — write it once, parameterise the anchor and the type. |
| MA-004 | 8.2 | `Manufacturer` and `SerialNumber` are mandatory on MachineryItemIdentification | Push down | Again the generic Mandatory-ModellingRule rule of DI-007. Two specs asking for the same shape is the signal to put it in Part 3. |
| MA-005 | 8.2 | `MonthOfConstruction` shall only be provided if `YearOfConstruction` is provided | Enforceable | Conditional presence — a shape family Part 3 has no example of yet, and an excellent fixture: one pass case provides neither, the other provides both. |
| MA-006 | 8.6 | `ProductInstanceUri` is mandatory and read-only on a machine | Instance-level | Checkable — `base:hasAccessLevel` *is* extracted (15 occurrences across the DI and Machinery graphs). Verify the AccessLevelType content-class encoding before writing the shape. |
| MA-007 | 8.2 | `YearOfConstruction` is a four-digit number and never changes | Split it | Two rules wearing one sentence. "Four digits" is instance-level and checkable; "never changes" is temporal and belongs with the Part 3 N/A entries. |
| MA-008 | 11.2 | All components of a machine are reachable via MachineComponentsType | Enforceable | Third instance of the reachability family. |
| MA-009 | 8.5 | Servers shall support ≥40/60 Unicode characters and ≥2 locales for these Properties | N/A | A Server capability, not an address-space shape. Catalog it as a non-rule. |

> **What the exercise proves.**
> Eighteen candidate rules, of which eleven are enforceable against graphs the
> pipeline already builds, two are genuinely not rules, and two turn out to be
> the *same* Part 3 rule surfacing twice. That last finding is the argument for
> doing companion specs at all: they do not just add rules, they tell you which
> core rules are load-bearing. Nothing here required a new translator feature —
> which is the test of whether a specification is ready to be catalogued.

**Confidence.** Section numbers for the DI and Machinery candidates above are as
reported by `reference.opcfoundation.org` and should be re-verified against
primary text before any rule is registered in a `spec.jsonld` — the same discipline
the Part 3 catalog applies to itself.

## 5. What changes for a companion specification

The directory structure carries over unchanged. Four things do not.

### The published nodeset becomes a fixture in its own right

Part 3 has no nodeset of its own; the NS0 subset stands in for one. DI and
Machinery *do*. Merging the specification's own nodeset into the data graph means
the shapes run against the OPC Foundation's published model, so a DI shape that
false-positives on `Opc.Ua.Di.NodeSet2.xml` fails immediately. That is a real
check on the shape and, occasionally, on the standard.

### Rules split into two families, and the fixtures differ

Some rules constrain the companion nodeset itself (type-level: MA-001's
ObjectType obligation). Others constrain models that *implement* it
(instance-level: MA-006, DI-008). A type-level fixture defines types; an
instance-level fixture instantiates them. Worth a `kind` field on each rule in
`spec.jsonld`, because it decides what a reviewer should expect to see in the
fixture.

### The cross check should inherit the dependency's shapes

Today the cross check merges the shapes of one specification. A DI fixture is
also a well-formed address space, so it should conform to `opc-10000-3-address-space`'s shapes
too. Making the cross check follow the `baselineNodeset` dependency chain is a
small change to `run_suite.py`, and it doubles the value of every fixture written
from here on: each new DI nodeset becomes another false-positive guard for all
nine Part 3 rules.

### The semantic bridge is a trap as well as a convenience

Because `nodeset2owl.py` emits Semantic Bridge predicates, DI's `ParameterSet`
child is reachable as `di:hasParameterSet`, not only as `opcua:HasComponent`.
That is convenient, and it is the wrong tool for most rules here, because the
predicate is *derived from the BrowseName*. Any rule about BrowseName correctness
checked through a BrowseName-derived predicate is circular — it can only ever
confirm itself. (The encoding also leaks: placeholder children arrive as
`di:has%3CCPIdentifier%3E`.) Match on `opcua:HasComponent` and read
`base:hasBrowseName` explicitly.

### Carried over unchanged

The vocabulary traps in [`../validation/README.md`](../validation/README.md)
apply identically and are not obvious: a node's type definition is
`base:instanceOf` for Objects but plain `rdf:type` for Variables; types carry no
NodeClass, so hop back via `base:definesType`; always traverse
`rdfs:subPropertyOf*` rather than matching a ReferenceType by name; `HasSubtype`
is materialised as `rdfs:subClassOf` and has no predicate; never target
`opcua:BaseNodeClass`; attribute literals are untyped strings, so compare against
`"true"`; never `COUNT` over an `OPTIONAL`; anchor every `UNION` branch on a
triple pattern. Read that section before the first shape of a new spec, not after
the first three fail mysteriously.

## 6. Where to pick it up

1. **Implement the Mandatory-ModellingRule shape in `opc-10000-3-address-space`.** DI-007 and
   MA-004 are both this rule. It is the single highest-leverage shape available,
   and it can only be written once.
2. **Extend `SEED_BROWSE_NAMES`** in `make_ns0_subset.py` for what the companion
   specs need — `HasAddIn`, `FolderType`, `Organizes` — and regenerate.
3. **Implement DI-001, the first shape in `specs/opc-10000-100-devices/`.** The directory, manifest
   and catalog exist; every rule in it is catalogued and none has a shape.
   DI-001 is the direct analog of an already-working shape (AS-006), so the first
   rule of the new spec tests the scaffolding rather than the shape. Phase 1 —
   deciding what lands in `specs/opc-10000-100-devices/common/` — has to happen first.
4. **Write the reachability shape once** and instantiate it for DI-002, MA-003
   and MA-008.
5. **Then make the cross check follow the dependency chain**, so the DI fixtures
   start guarding the Part 3 rules.
