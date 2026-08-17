# OPC UA validation-rule suites

This directory turns rule catalogs like [`docs/validation-rules-part3.md`](../docs/validation-rules-part3.md)
into something executable: a SHACL shape per rule, a corpus of NodeSet2 fixtures
that must pass and must fail, and a runner that checks both.

The point is not only to have the rules. It is to have **data that catches
regressions**, and to make that data cheap enough to keep adding, so a change to
a shape, to `nodeset2owl.py`, or to the OWL vocabulary shows up as a failing
fixture rather than as a silent behaviour change discovered months later.

```
validation/
  run_suite.py            the runner
  tools/
    make_ns0_subset.py    regenerates the shared Namespace 0 subset
  ontology/               older, hand-written shapes (see "Relationship to ontology/")
  specs/
    opc-10000-3-address-space/           one directory per specification
      spec.json           manifest: which rules have a shape
      common/             the NS0 nodeset every fixture in this spec depends on
      shapes/            one *.shacl.ttl per rule
      testcases/
        AS-008/           one directory per rule
          pass-1-*.NodeSet2.xml
          pass-2-*.NodeSet2.xml
          fail-1-*.NodeSet2.xml
          fail-1-*.NodeSet2.expected
          ...
```

## Running it

```bash
python3 validation/run_suite.py                 # everything
python3 validation/run_suite.py -r AS-008       # one rule
python3 validation/run_suite.py --coverage      # what is enforced, and how much of the catalog
python3 validation/run_suite.py --no-cross      # skip the cross check while iterating
```

`make test` runs the whole suite.

Each test case is executed the way a user would run it by hand:

```bash
nodeset2owl.py <case>.NodeSet2.xml -i <ns0-subset>.ttl -o <case>.owl.ttl
validate.py -m ontology -ni -s <rule>.shacl.ttl <ns0-subset + case merged>.ttl
```

so the suite exercises the real translation and the real CLI. Intermediate files
land in `.build/` and are rebuilt only when an input is newer.

## The two checks, and why the second one matters

**Targeted.** Every `fail-*` fixture is validated against its own rule's shape
and must produce exactly the findings recorded in the neighbouring `.expected`
file. Every `pass-*` fixture is validated against the same shape and must
conform. This proves a rule detects what it claims to detect.

**Cross.** Every `pass-*` fixture of *every* rule is also validated against the
merged shape set of the whole specification, and must still conform.

The cross check is what makes the corpus compound. A passing nodeset written for
AS-039 is also a perfectly ordinary, conforming address space, so it is
automatically a false-positive guard for AS-005, AS-031, AS-057 and everything
added later. Twelve rules with four fixtures each do not give twelve independent
tests; they give twelve detection tests and twenty-four shared false-positive
guards. Every fixture added for a new rule strengthens all the older ones.

## Adding a rule to an existing specification

1. **Write the shape** in `specs/<spec>/shapes/AS-NNN-<slug>.shacl.ttl`. Read
   "Writing shapes against the translated graph" below first; the vocabulary has
   several traps.
2. **Register it** in `specs/<spec>/spec.json` with its section reference and a
   one-line summary.
3. **Write four fixtures** in `specs/<spec>/testcases/AS-NNN/`. Two `pass-` and
   two `fail-` NodeSet2 XML files; the runner enforces the count.
4. **Record the expectations**: `run_suite.py -r AS-NNN --update-expectations`,
   then read the generated `.expected` files. They are the review artefact --
   check that the focus nodes are the ones you planted and no others.
5. **Run the whole suite** so the cross check sees the new fixtures.

What makes a fixture pair worth having:

- A `pass-` fixture should cover the case a *wrong* implementation would reject,
  not just an easy one. `AS-039/pass-2` types an InstanceDeclaration with an
  abstract type, which a blanket "no abstract types" reading would reject and
  which would break most companion specifications.
- A `fail-` fixture should contain correct siblings next to the planted defect,
  so an over-firing shape fails too, and should plant the defect in more than one
  way where the rule has more than one shape. `AS-057/fail-2` uses
  `HasOrderedComponent` so that a shape matching `HasComponent` by name instead
  of by subtype is caught.
- Say in the XML comment *why* the fixture exists, not what it contains. The
  file already shows what it contains.

## Adding a new specification

Copy the structure of `specs/opc-10000-3-address-space/`:

1. `mkdir -p specs/<spec>/{shapes,testcases,common}`.
2. Write `spec.json` with `id`, `title`, `catalog` (the prose rule catalog),
   `catalogRuleCount`, `commonNodeset`, and an empty `rules` list.
3. Provide the `commonNodeset` the fixtures build on. For a companion
   specification this is that specification's own nodeset plus its
   dependencies; `opc-10000-3-address-space` uses a generated subset of Namespace 0 (below).
4. Add rules one at a time as above.

The runner discovers any directory under `specs/` containing a `spec.json`, so a
new specification needs no code change.

### The shared NS0 subset

Fixtures must be hermetic: no downloads, no dependency on the 3.6 MB core
nodeset. But they cannot be standalone either, because nearly every Part 3 rule
is phrased in terms of Namespace 0 nodes, and `nodeset2owl.py` hard-fails on a
DataType or ReferenceType it cannot resolve.

So all fixtures in `opc-10000-3-address-space` share one dependency:
`common/opcua-ns0-subset.NodeSet2.xml`, 70 nodes extracted from the official
`Opc.Ua.NodeSet2.xml` by `tools/make_ns0_subset.py`. It is generated, not
hand-written, so NodeIds, `IsAbstract` flags and subtype hierarchies are the
spec's own and cannot drift. To add a node, extend `SEED_BROWSE_NAMES` in the
tool and re-run it.

The subset is merged into the data graph of every test case, which means the
real (if pruned) Namespace 0 content is held to the same shapes as the fixtures.
A shape that false-positives on the spec's own nodes fails the suite.

## Writing shapes against the translated graph

Shapes here are validated against `nodeset2owl.py` **output**, not against the
NodeSet2 XML and not against a hand-written idealisation of it. The translation
is lossy and asymmetric in ways that decide how a shape has to be written.

**A node's type definition is not one predicate.** `HasTypeDefinition` is not
carried over as a reference. It becomes a type assertion -- but
`utils.replace_type_of_node_iris` only rewrites types below
`opcua:BaseObjectType` into `base:instanceOf`, so Objects end up with
`base:instanceOf` and Variables keep a plain `rdf:type`. Match both, and pin
down that the target is a type by requiring it to be an `owl:Class`:

```sparql
$this base:instanceOf|rdf:type ?type .
?type a owl:Class .
```

**Types carry no NodeClass.** The target above is an `owl:Class` and has no
NodeClass of its own. To find out whether it is an ObjectType or a VariableType,
hop back to the node that defines it: `?typenode base:definesType ?type` and read
`rdf:type` there. See `AS-035`.

**References keep their own IRI.** A `HasComponent` reference becomes the
predicate `opcua:HasComponent`, not a `base:` term. Always traverse the
ReferenceType hierarchy rather than matching a name, because the data carries
whichever concrete subtype the model used:

```sparql
?source ?reference $this .
?reference rdfs:subPropertyOf* opcua:HasComponent .
```

Part 3 section 4.4.4 treats a subtype of a concrete ReferenceType as that
ReferenceType for identification purposes, so this traversal *is* the rule, not
a convenience.

**`HasSubtype` disappears.** Subtyping is materialised as `rdfs:subClassOf`
between type classes (and `rdfs:subPropertyOf` between ReferenceType
properties). There is no `opcua:HasSubtype` predicate to match.

**Do not target `opcua:BaseNodeClass`.** That class and the NodeClass hierarchy
under it are declared in `base.ttl`, which these shapes deliberately do not
load, and matching it needs RDFS entailment. A shape targeting it silently
matches nothing. List the concrete NodeClasses instead. (Several shapes in
`ontology/` target it and are inert for this reason.)

**Attribute literals are untyped.** `base:isAbstract` and `base:isSymmetric` are
the XML attribute strings copied through, so compare against `"true"`, never
`"true"^^xsd:boolean`.

**Do not COUNT over an OPTIONAL.** The SPARQL engine behind `validate.py` counts
an unbound optional variable as one match, so a "zero of these" test written as
`COUNT` never fires. Use `FILTER NOT EXISTS` for the zero case and a grouped
subquery -- which only sees nodes that have at least one match -- for the
"more than one" case. `AS-008` shows both.

**A UNION branch is evaluated before the target-class join.** `validate.py`
injects `$this a <targetClass> .` after the first `WHERE {`. A UNION branch
containing only `FILTER`/`BIND` is evaluated with `$this` still unbound and
matches nothing, so anchor each branch on a triple pattern. `base:hasNodeId` is
the reliable anchor: every translated node has exactly one.

**Prefer a top-level `sh:sparql` with `sh:targetClass`.** `lib/shacl.py` runs
those directly against the merged graph, once per target class, which is the
fast path this codebase is built around. A shape carrying two constraints that
need different target classes must be split into two node shapes, because every
constraint runs against every target class of its shape.

### Rules that cannot be fixtured

Some catalog rules are real but cannot be given a failing nodeset, because the
translation normalises the defect away before it reaches the graph. AS-008's
"more than one HasTypeDefinition" is one: `nodeset2owl.py` keeps the first and
drops the rest without warning. Keep the check in the shape -- the graph can be
produced by other means -- and say so in the fixture comment, as
`AS-008/fail-2` does. A rule that cannot be fixtured at all belongs in the
catalog as a gap, not in `spec.json`.

## Relationship to `ontology/`

`ontology/` holds the older shapes, run by `validate.py -m ontology` by default
and covered by `tests/validation/`. They are kept as they are; nothing here
changes them.

They are written against a different vocabulary from the one `nodeset2owl.py`
emits -- `base:hasComponent` and `base:hasProperty` rather than
`opcua:HasComponent` and `opcua:HasProperty` -- and their fixtures are
hand-written Turtle in that same vocabulary, so they pass without ever being
exercised against real translator output. Several also target
`opcua:BaseNodeClass`, which never matches (above). Rules re-implemented here
therefore start from the specification text again rather than from those shapes;
where one supersedes an older shape, its header says so. `AS-005` and
`AS-031` are the two current cases.
