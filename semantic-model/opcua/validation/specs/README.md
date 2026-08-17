# The specification tree

One directory per specification. `run_suite.py` discovers any directory here
containing a `spec.json`, so adding a specification needs no code change.

```
specs/
  opc-10000-3-address-space/    Address Space Model            9 shapes,  70 catalogued
  opc-10000-100-devices/        Devices (DI)                   0 shapes,  36 catalogued
  opc-40001-1-machinery/        Basic Building Blocks          0 shapes,  25 catalogued
  opc-40223-pumps/              Pumps and Vacuum Pumps         0 shapes,   6 catalogued
```

Each directory has the same five parts:

```
<spec>/
  spec.json       the manifest: identity, dependencies, baseline nodeset, rules
  common/         the nodeset(s) every fixture in this spec is layered on
  shapes/         one <RULE-ID>-<slug>.shacl.ttl per implemented rule
  testcases/      one directory per rule: two pass- and two fail- fixtures
  (catalog)       the prose rule catalog, in ../../docs/, named by spec.json
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
| `opc-10000-3-address-space` | a generated 70-node subset of Namespace 0 |
| `opc-10000-100-devices` | NS0 + `Opc.Ua.Di.NodeSet2.xml` |
| `opc-40001-1-machinery` | NS0 + DI + `Opc.Ua.Machinery.NodeSet2.xml` |
| `opc-40223-pumps` | NS0 + DI + Machinery + `Opc.Ua.Pumps.NodeSet2.xml` |

**The directories stay flat.** `specs/` holds four siblings and always will; a
specification is never nested inside the one it builds on. The chain above is a
*relation between manifests*, declared by the `dependsOn` field in each
`spec.json` and read by the runner — not a location on disk.

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
means six catalogued Pumps rules buy validation against every rule in
the four catalogs.

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

## Rule IDs

Namespaced per specification and stable forever: `AS-` for Part 3 (address
space), `DI-`, `MA-`, `PU-`. They are referenced from the prose catalogs, from
shape filenames, from `testcases/` directory names and from commit messages, so
they are renumbered under no circumstances. A rule that turns out not to be a
rule keeps its ID and gets status `n/a`.

## Catalogued is a real state, not a to-do

A rule in `spec.json` without a `shape` key is catalogued: named, sourced to a
subclause, and given a status, but not enforced. The runner skips it, and
`--coverage` counts it in the denominator. Three of the four specifications here
are entirely in that state.

This is deliberate. Cataloguing a specification in prose is a separate, complete
piece of work from implementing it, and it is the piece that establishes what
*could* be checked — including the rules that turn out to be Server capabilities
or runtime behaviour and can never be checked at all. Those are recorded too, so
the next reader does not re-derive them. See
`../../docs/adding-a-validation-specification.md` for the method.

## Status values used in the manifests

| Status | Meaning |
|---|---|
| `implemented` | Default when a rule has a `shape`. Enforced, with fixtures. |
| `gap` | Checkable against the translated graph today; no shape written yet. |
| `instance-level` | Checkable, but needs a fixture that instantiates the types rather than defining them. |
| `push-down` | A core rule surfacing in a companion spec. Implement once in the spec it really belongs to, named in the rule's catalog entry. |
| `inherited` | Holds by subtyping from an ancestor spec; nothing to implement here. |
| `advanced` | Needs a transcribed table, a recursive walk, or a cross-consistency check. |
| `needs-verification` | Extracted from a secondary reading; re-read primary text first. |
| `blocked` | Static and real, but `nodeset2owl.py` does not extract the Attribute it needs. |
| `n/a` | Normative, but not a static property of one AddressSpace snapshot. |

## Where the baseline nodesets are

`opc-10000-3-address-space/common/` holds a checked-in, generated 20 KB subset of Namespace 0.
The companion specs do not have their nodesets checked in — see the `.gitignore`
in each `common/` directory. Deciding what lands there (the whole published
nodeset, or a generated subset in the style of `tools/make_ns0_subset.py`) is
phase 1 of implementing each of them, and it is not started. Until a rule in
those specs has a shape, the runner never looks for the file.
