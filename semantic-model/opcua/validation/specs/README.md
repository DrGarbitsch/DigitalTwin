# The specification tree

One directory per specification. `run_suite.py` discovers any directory here
containing a `spec.jsonld`, so adding a specification needs no code change.

```
specs/
  opc-10000-3-address-space/    Address Space Model            9 shapes,  70 catalogued
  opc-10000-100-devices/        Devices (DI)                   0 shapes,  36 catalogued
  opc-40001-1-machinery/        Basic Building Blocks          0 shapes,  25 catalogued
  opc-40223-pumps/              Pumps and Vacuum Pumps         0 shapes,  16 catalogued
```

Each directory has the same five parts:

```
<spec>/
  spec.jsonld     the manifest: identity, dependencies, baseline nodeset, rules
  catalog.md      the prose rule catalog -- every rule, sourced to a subclause
  common/         the nodeset(s) every fixture in this spec is layered on
  shapes/         one <RULE-ID>-<slug>.shacl.ttl per implemented rule
  testcases/      one directory per rule: two pass- and two fail- fixtures
```

## They are a chain, not four islands

The specifications build on each other, and the suite mirrors that exactly. The
chain is not invented here — it is the one `translate_default_nodesets.make`
already uses to translate the nodesets:

```
opc-10000-3-address-space  <--  opc-10000-100-devices  <--  opc-40001-1-machinery  <--  opc-40223-pumps

read "<--" as "is built on by": opc-40223-pumps builds on opc-40001-1-machinery
```

| Spec | Baseline its fixtures are layered on |
|---|---|
| `opc-10000-3-address-space` | the complete `Opc.Ua.NodeSet2.xml`, all 4957 nodes |
| `opc-10000-100-devices` | NS0 + `Opc.Ua.Di.NodeSet2.xml` |
| `opc-40001-1-machinery` | NS0 + DI + `Opc.Ua.Machinery.NodeSet2.xml` |
| `opc-40223-pumps` | NS0 + DI + Machinery + `Opc.Ua.Pumps.NodeSet2.xml` |

**The directories stay flat.** `specs/` holds four siblings and always will; a
specification is never nested inside the one it builds on. The chain above is a
*relation between manifests*, declared by the `dependsOn` field in each
`spec.jsonld` and read by the runner — not a location on disk.

Keeping it out of the filesystem is deliberate. Nesting would force a single
parent per spec, and that is already wrong for the specs this project
translates: MachineTool builds on **both** Machinery and IA, PADIM on **both**
DI and the IRDI dictionary. `dependsOn` is a list precisely because the real
graph is a DAG, not a tree. Nesting would also bury `opc-10000-3-address-space` four levels
deep under its dependents, and move a directory every time a dependency is
discovered.

Three things follow from the relation, and they are the reason to declare it at
all rather than treat the four as independent suites:

**1. The data graph is layered.** A fixture in `opc-40223-pumps/` is translated on top of
the nodesets `dependsOn` names, transitively and in order. Without DI underneath
it, `nodeset2owl.py` hard-fails on the first unresolvable ReferenceType; with it,
a pump fixture is a realistic address space rather than a fragment.

**2. The shape set is layered too — this is the part that pays.** The cross check
should validate every `pass-` fixture against the merged shapes of the spec *and
all its ancestors*. `pumps:PumpType` is a subtype of `di:TopologyElementType`
(verified in `pumps.owl.ttl`), so a pump that violates a DI FunctionalGroup rule
is genuinely broken, and a Pumps-only shape set would never notice. Layering
means the 16 catalogued Pumps rules buy validation against all 147 rules in the
four catalogs — and Pumps needs it more than any of them, since four of its 16
rules are inheritance facts rather than rules of its own.

> Not yet implemented. `Spec.merged_shapes()` currently merges one
> specification's shapes. Following `dependsOn` is a small change and is the
> highest-value one available to the runner — see the backlog in
> `../../docs/adding-a-validation-specification.md`.

**3. A rule appearing in two siblings belongs in their ancestor.** DI-007 (the
mandatory Properties of DeviceType) and MA-004 (Manufacturer and SerialNumber on
MachineryItemIdentification) are the same Part 3 obligation: an instance carries
every InstanceDeclaration whose ModellingRule is `Mandatory`. Both are marked
`push-down` rather than implemented twice. The chain is what makes
that visible; four independent suites would have grown two near-identical shapes.

## Rule IDs and IRIs

Rule IDs are namespaced per specification and stable forever: `AS-` for Part 3
(address space), `DI-`, `MA-`, `PU-`. They are referenced from the prose
catalogs, from shape filenames, from `testcases/` directory names and from
commit messages, so they are renumbered under no circumstances. A rule that
turns out not to be a rule keeps its ID and gets status `n/a`.

Every rule, specification and shape also has a URN, so that a validation report
identifies what it violated rather than only where the file sat:

```
urn:opcua:validation:spec:10000-3
urn:opcua:validation:rule:10000-3:AS-039
urn:opcua:validation:shape:10000-3:AS-031:source
```

Built from `documentNumber` in the manifest, never hand-written twice —
`run_suite.py` fails a rule whose shape file declares an IRI that does not
match. The scheme, and why it is a URN carrying no organisation name, is
documented in [`../vocabulary.ttl`](../vocabulary.ttl).

Rule and shape are separate identities because they are one-to-many, and for
three independent reasons. A shape carrying constraints that need different
target classes has to be split, since every constraint in a node shape runs
against every target class of that shape. A rule constraining both model kinds
needs one shape per kind. And a rule checked in more than one translated form
needs one shape per form. Nine Part 3 rules are eleven node shapes today, all
from the first reason alone.

The `<part>` slot carries whatever distinguishes a shape from its siblings —
`source`/`target` for a target-class split, a model kind, a representation, or
a combination. It is a readable name, not a parsed structure: the authority is
the RDF each shape declares, and `run_suite.py` checks the declarations.

**The manifest is the graph.** `spec.jsonld` is JSON-LD, so `run_suite.py`
reads it as plain JSON — `json.load`, no context resolution — and rdflib reads
the same bytes as RDF. There is no generated copy of the catalog and therefore
nothing to fall out of date. Terms the shared
[`../context.jsonld`](../context.jsonld) does not map (`baselineNodeset`,
`catalogCoverage`, and the other build inputs) are simply invisible to the RDF
reader, which is the intended split: they are instructions to the runner, not
statements about the specification.

`../tools/rules_graph.py` collects the four manifests into one graph, so the
catalog is queryable:

```sparql
PREFIX opcv: <urn:opcua:validation:vocab:>
SELECT ?id WHERE {
  ?spec opcv:buildsOn+ <urn:opcua:validation:spec:10000-3> .
  ?rule opcv:definedBy ?spec ; opcv:ruleId ?id ; opcv:status "blocked" .
}
```

returns DI-015, DI-017, MA-023 and PU-009 — every rule blocked on an
unextracted Attribute anywhere in the tree. Reading that out of four Markdown
catalogs by hand is how it was done before.

## Two populations: the specification, and models that use it

A companion specification is validated twice over, against two different
things, and conflating them is the easiest way to write a shape that is wrong
half the time.

| | **TypeModel** | **InstanceModel** |
|---|---|---|
| What is under test | the specification's own nodeset | a vendor or Server model that instantiates it |
| A violation means | the standard is defective, or our reading of it is | that product is defective |
| Nodes the shape targets | ObjectTypes, VariableTypes, InstanceDeclarations | Objects and Variables that are *not* InstanceDeclarations |
| The fixture | defines types | instantiates them, with the CS underneath |

Every rule declares which it constrains, with `appliesTo` in the manifest:

```json
{ "@id": "rule:PU-001", "id": "PU-001", "status": "gap",
  "appliesTo": ["TypeModel", "InstanceModel"] }
```

Pumps is classified: 6 rules are TypeModel, 9 are InstanceModel, and one is
both. That split is itself informative — a companion specification's §3
conventions constrain its own nodeset, while everything operational constrains
the products built on it.

### Worked example: PU-001, the rule that is both

OPC 40223 §6.2.3: *"A FunctionalGroup that would have no Variables, Objects, or
Methods if instantiated shall not be instantiated."*

"if instantiated" is doing a lot of work in that sentence, and it is why one
sentence produces two obligations that cannot share a shape:

- **TypeModel** — the specification must not *define* a FunctionalGroup type
  whose instantiation would necessarily be empty. Target: ObjectTypes that are
  subtypes of `di:FunctionalGroupType`, with no InstanceDeclaration beneath
  them and no inherited member.
- **InstanceModel** — a Server must not *instantiate* a FunctionalGroup that
  ends up empty. Target: Objects whose type definition derives from
  `di:FunctionalGroupType` and that carry no `HasModellingRule` (Part 3's test
  for "is an instance, not an InstanceDeclaration" — see AS-039). A type may
  legitimately be empty in the abstract while every instance of it is
  populated, and vice versa, so neither shape implies the other.

The `<part>` slot in the shape IRI, which already distinguishes shapes split by
target class, carries the model kind:

```
urn:opcua:validation:rule:40223:PU-001                  the rule -- one requirement
urn:opcua:validation:shape:40223:PU-001:TypeModel       enforces it against the CS
urn:opcua:validation:shape:40223:PU-001:InstanceModel   enforces it against a model
```

Both shapes assert `opcv:implementsRule <urn:opcua:validation:rule:40223:PU-001>`,
so a report naming either resolves back to one rule, one subclause, one status.

Fixtures split the same way, and `run_suite.py` requires two passing and two
failing nodesets **per kind**, not four in total — four between them would
cover neither properly:

```
shapes/
  PU-001-empty-functionalgroup.shacl.ttl     both node shapes, one file
testcases/PU-001/
  TypeModel/
    pass-1-group-with-mandatory-member.NodeSet2.xml
    pass-2-group-populated-by-supertype.NodeSet2.xml
    fail-1-type-with-no-members.NodeSet2.xml
    fail-1-type-with-no-members.NodeSet2.expected
    fail-2-...
  InstanceModel/
    pass-1-populated-pump-group.NodeSet2.xml
    pass-2-group-with-only-optional-members-present.NodeSet2.xml
    fail-1-instantiated-empty-group.NodeSet2.xml
    fail-1-instantiated-empty-group.NodeSet2.expected
    fail-2-...
```

A rule constraining one kind keeps the flat `testcases/<ID>/` layout — which is
every rule implemented today. The subdirectory appears only when `appliesTo`
names both, and the runner cross-checks the two against each other: a
directory not in `appliesTo`, or an `appliesTo` kind with no directory, fails.

### The second axis: which translated form the shape is written against

Model kind says what a rule is *about*. It says nothing about which graph a
shape *matches*, and in this pipeline those are two different questions,
because an address space is translated more than one way:

| | **`opcv:OpcUaOwl`** | **`opcv:NgsiLd`** |
|---|---|---|
| Produced by | `nodeset2owl.py` | `owl2instances.py` |
| Vocabulary | `opcua:` / `base:` — one node per Node, References as predicates | NGSI-LD entities — `Property`, `ListProperty`, `Relationship`, carrying values |
| Validated with | `validate.py -m ontology` | `validate.py -m instance` |

A third, `opcv:NgsiLdTemporal`, is NGSI-LD carrying more than one instance of an
attribute, each with its own `ngsild:observedAt`. It matters far more than a
third serialisation normally would, because **it is the difference between a
graph with no time axis and a graph where time is ordinary data.** A rule about
change over time — a counter that may only increase, a Property that may never
change — is unanswerable against a NodeSet2 and is a routine self-join with
`FILTER(?earlier < ?later)` here. Rules say where they are answerable with
`opcv:checkableIn`; MA-018, DI-018 and MA-007 carry it today, having been
reclassified out of N/A once this was noticed.

A shape written for one shares **nothing** with a shape written for the other —
not the target class, not the predicates, not the traversal. "MonthOfConstruction
only alongside YearOfConstruction" is a walk over `opcua:HasProperty` plus
`base:hasBrowseName` in the OWL form, and a presence test on two NGSI-LD
Properties of one entity in the other. Same sentence in the specification, two
unrelated SPARQL queries.

So every node shape declares which form it matches:

```turtle
<urn:opcua:validation:shape:40223:PU-001:InstanceModel> a sh:NodeShape ;
    opcv:implementsRule <urn:opcua:validation:rule:40223:PU-001> ;
    opcv:representation opcv:OpcUaOwl ;
```

Declared on the **shape**, not the rule. The rule is a sentence in a
specification and is representation-neutral; which encodings this project
chooses to check it in is our decision, not the standard's. All eleven shapes
today declare `opcv:OpcUaOwl`.

**The runner refuses to run a shape it cannot build.** Only `opcv:OpcUaOwl` has
a pipeline here, so a shape declaring `opcv:NgsiLd` fails the identity check
rather than being quietly validated against an OWL graph it was never written
for — which is the exact mistake this facet exists to prevent. A shape with no
declaration at all fails too. (`owl2instances.py` is not on this branch, which
is the immediate reason the NGSI-LD pipeline is declared and not built.)

Three facts follow for anyone adding the NGSI-LD side later:

- **The fixture is still a NodeSet2.** Both pipelines start from the same
  nodeset; they diverge after translation. So one `InstanceModel` fixture can
  feed both an `OpcUaOwl` shape and an `NgsiLd` shape, which is a real saving
  and keeps the two honest against each other.
- **The expectations cannot be shared.** Different vocabularies mean different
  focus nodes and different messages, so a fixture validated in two forms needs
  two recorded results: `fail-1-x.NodeSet2.expected` stays the `OpcUaOwl` one,
  and the other form adds `fail-1-x.NodeSet2.NgsiLd.expected`. The twenty
  existing expectation files are all verified and do not move.
- **`owl2instances.py` needs `-n <namespace>` and a root type**, so an NGSI-LD
  fixture carries more build configuration than an OWL one. That belongs in the
  manifest next to the rule, not hard-coded in the runner.

### When one query is not enough

Some rules do not fit a single SPARQL query. That is a fact about one query, not
about the stack, and the difference matters: the answer is more declarative
steps, never a procedural check written in Python.

The reason is not purity. A rule expressed as SHACL and SPARQL is *data* — it
carries an IRI, it says which specification subclause it came from, it can be
queried, diffed and reasoned over, and `rules_graph.py` can count it. A rule
expressed as a Python function is none of those things: it is opaque to every
tool here, and the catalog would go back to being a list of filenames with
prose beside them.

Three declarative escapes, in order of preference:

1. **Entailment.** `rdfs:subPropertyOf` is core RDFS entailment. Materialising
   it means every subtype of a ReferenceType already appears under the
   supertype's predicate, and a fixed property path then does what a variable
   predicate could not. This project already runs a reasoner: two Part 3 rules
   are enforced by HermiT over the Virtual-Types machinery rather than by SHACL,
   which is the precedent.
2. **Materialisation before validation.** A SHACL-AF `sh:rule`, or a plain
   SPARQL `CONSTRUCT`, writes the derived triples the shape needs, and the shape
   runs against the enlarged graph. Two declarative steps, both inspectable,
   both versioned next to the rule.
3. **Chained construction to a fixpoint** for the genuinely recursive cases —
   Part 3's structural-correspondence rules (AS-011, AS-012) are the example.
   The iteration needs a driver, but the driver only decides *when to stop*; the
   logic stays in SPARQL.

**AS-063 is the worked case, and it is not the limit it looks like.** Its shape
enumerates `HasEventSource|HasNotifier` in the property path, because a SPARQL
property path cannot bind its predicate to a variable and so cannot itself
follow `rdfs:subPropertyOf*`. Left there, a companion specification defining a
further subtype would need adding to the alternation by hand. With escape 1 the
enumeration disappears entirely — under RDFS entailment the subtypes *are*
`opcua:HasEventSource` triples, and the path needs no alternation at all. The
shape's header records the enumeration as a limitation of how it is written
today, not of what SHACL can express.

### What this does not change

The dependency chain, the IRI scheme and the merged shape set all work
unaltered. An InstanceModel fixture for Pumps layers on NS0 + DI + Machinery +
Pumps exactly as `dependsOn` already says; the only difference is that the
fixture instantiates what the layers beneath it define, rather than adding more
definitions. TypeModel shapes still run against that fixture too, and still
pass, because the CS nodeset in its data graph is unchanged — which is a free
regression check on the standard every time an instance fixture is added.

## Catalogued is a real state, not a to-do

A rule in `spec.jsonld` without a `shape` key is catalogued: named, sourced to a
subclause, and given a status, but not enforced. The runner skips it, and
`--coverage` counts it in the denominator. Three of the four specifications here
are entirely in that state.

**Every catalogued rule belongs in the manifest, not only the implemented
ones.** Part 3's manifest listed just its nine shapes for a while, leaving the
other 61 rules alive only in the prose catalog — invisible to `rules_graph.py`,
missing from every query, and impossible to find by looking where a reader
would naturally look. All 147 rules across the four specifications are now
listed.

This is deliberate. Cataloguing a specification in prose is a separate, complete
piece of work from implementing it, and it is the piece that establishes what
*could* be checked — including the rules that turn out to be Server capabilities
or runtime behaviour and can never be checked at all. Those are recorded too, so
the next reader does not re-derive them. See
`../../docs/adding-a-validation-specification.md` for the method.

## Status values used in the manifests

| Status | Meaning |
|---|---|
| `implemented` | Default when a rule has a `shape`. Enforced by this suite, with fixtures. |
| `implemented-outside-suite` | Covered by an older hand-written shape in `../ontology/`, which has no fixtures here. |
| `implemented-reasoner` | Enforced by HermiT over the Virtual-Types machinery rather than by SHACL. |
| `new` | Named from the specification text but not yet assessed against the existing shapes. |
| `gap` | Checkable against the translated graph today; no shape written yet. |
| `instance-level` | Checkable, but needs a fixture that instantiates the types rather than defining them. |
| `push-down` | A core rule surfacing in a companion spec. Implement once in the spec it really belongs to, named in the rule's catalog entry. |
| `inherited` | Holds by subtyping from an ancestor spec; nothing to implement here. |
| `advanced` | Needs a transcribed table, a recursive walk, or a cross-consistency check. |
| `needs-verification` | Extracted from a secondary reading; re-read primary text first. |
| `blocked` | Static and real, but `nodeset2owl.py` does not extract the Attribute it needs. |
| `n/a` | Normative, but not a static property of one AddressSpace snapshot. |

## Where the baseline nodesets are

All four specifications are public, so all four point `baselineNodeset` at the
official published nodeset by URL, pinned to the `UA-1.05.03-2023-12-15` release
tag — the same version `translate_default_nodesets.make` uses. Nothing is
checked in and nothing can drift from what the OPC Foundation ships. A relative
path into `common/` is the fallback, for a specification that is private or not
yet published.

This also removes what used to be phase 1 of adding a specification: there is no
longer a decision about what lands in `common/`, because the answer is the
published nodeset and the manifest simply names it.

`opc-10000-3-address-space/common/` still holds a generated 20 KB NS0 subset
that the runner no longer uses; see
[`../README.md`](../README.md#the-shared-baseline-nodeset) for why validation
runs on complete content and why the subset was kept rather than deleted.
