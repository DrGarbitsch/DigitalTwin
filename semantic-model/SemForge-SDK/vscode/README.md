# SemForge for VS Code

Semantic modelling feedback while you edit: validation, coverage and
cross-artifact navigation over a SemForge package.

The extension itself decides nothing. It starts the SDK's language server and
renders what it sends, so the editor, the CLI and CI always agree — which is the
whole point of `architecture.md` §8.4.

---

## What you get

Open `shacl.ttl` in a package and the shapes are annotated in place.

**Errors** — things that would break, marked on the shape that causes them:

- *capability*: a shape the target profile cannot compile. Compiled to nothing,
  it would produce no alert — and no alert is exactly what a satisfied
  constraint produces, so this must never be discovered later.
- *view*: a shape that aggregates while reading the `current` data view, where
  each attribute has already been resolved to its latest instance. The aggregate
  would run over one observation where several were meant and return a
  plausible wrong number.

**Warnings** — *fires*: this shape currently raises violations, listing which
constraint on which entity.

**Information** — *unexercised*: no example makes these constraints fire.

That last one is the one worth having an editor for. A constraint whose
condition can never match produces exactly what a satisfied constraint
produces, so a green test run cannot tell "correct" from "dead". The only
available signal is that no example has ever made it fire. A real instance of
this sat in the KMS for months: `StateOnFilterShape` asked for
`?pc a Plasmacutter` where the instances are typed `Cutter`, and every test
stayed green.

**Hover** a shape name for its provenance — where it came from, its tier, and
the file and line that declares it.

**Go to definition** (`F12`) on a property in `sh:path` jumps from `shacl.ttl`
to the `owl:ObjectProperty` in `knowledge.ttl` that declares it. Nothing else in
the toolchain can follow that link: the two files are related only through the
graph.

**Outline** lists every shape in the file.

---

## Install

### 1. The SDK

```bash
cd semantic-model/SemForge-SDK
make setup          # creates venv/ and installs pinned dependencies
make test           # optional: 142 tests should pass
```

The extension finds `venv/bin/python` on its own. If you keep your interpreter
elsewhere, set `semforge.pythonPath` in VS Code settings.

### 2. The extension

```bash
cd semantic-model/SemForge-SDK/vscode
npm install
```

Then pick one of three ways to run it.

**A. One command, no F5.** The most reliable, because it depends on nothing in
your VS Code setup:

```bash
cd semantic-model/SemForge-SDK/vscode
code --extensionDevelopmentPath="$PWD" ../..
```

A new window opens with the extension loaded and `semantic-model/` as its
folder. Open `kms/shacl.ttl` in it.

**B. F5 from the extension folder.**

1. Open **`semantic-model/SemForge-SDK/vscode`** as the VS Code window — the
   folder itself, not the repository root. `.vscode/launch.json` lives there and
   is what teaches F5 what to do.
2. Press `F5`, or pick **Run SemForge Extension** in the Run and Debug panel.
3. A second window opens on `semantic-model/`. Open `kms/shacl.ttl`.

> If F5 asks you to *select a debugger* or offers Node.js/Chrome, VS Code has
> not found `launch.json`. That means the open folder is not the `vscode/`
> directory — check the title bar. Use method **A**, which does not depend on
> it.

**C. Install a packaged build.**

```bash
npm install -g @vscode/vsce
vsce package                       # produces semforge-0.1.0.vsix
code --install-extension semforge-0.1.0.vsix
```

Installed this way it loads in every window, so open the repository normally.

### 3. What you should see

Open `semantic-model/kms/shacl.ttl`. The file itself looks no different — the
extension adds no syntax colouring beyond what VS Code already does for `.ttl`.
**Everything it contributes is in three places, and none of them is the editor
text by default:**

**Problems panel** — `Ctrl+Shift+M` (`Cmd+Shift+M` on macOS), or View → Problems.
This is the main thing. On the shipped KMS it should hold **11 entries**:

```
⚠  3 violation(s) here: MinCountConstraintComponent(hasXXXWorkpiece) on urn:filter:2 …   [160]
ⓘ  7 constraint(s) here have no example that makes them fire (hasCartridge/MaxCount…)    [14]
ⓘ  20 constraint(s) here have no example that makes them fire (hasFilter/ClassCons…)     [46]
…
```

**Squiggles in the file** — a yellow underline on line 160 (`:MachineShape`) and
faint blue ones on each other shape's first line. Hover one to read the message.
Clicking a Problems entry jumps to it.

**The SemForge view** — click the SemForge icon in the activity bar (left
edge). This is the cooked view: entity types, their attributes, and the
constraints on each.

```
Filter                            2 shape(s)
└── :FilterShape                  2 attribute(s)
    └── hasStrength
        ├── ✎ sh:maxCount   1
        ├── ✎ sh:minCount   1
        ├── ✎ sh:nodeKind   sh:BlankNode
        └── value                 hasValue
            ├── ✎ sh:maxInclusive  100.0
            ├── ✎ sh:minInclusive  0.0
            └── 🔒 or (raw only)   structure, not a parameter
```

A pencil means editable: click it and you get a picker of what the model
allows, or an input box where the value is free (a count, a bound, a pattern).

For `sh:class` the picker knows which half of the ontology applies, because the
two sides of the NGSI-LD encoding mean different things:

| slot | offers | because |
|---|---|---|
| `value → hasObject` | entity types — `Filter`, `Workpiece`, `Cutter` | a Relationship points at an entity |
| `value → hasValue` | vocabulary classes — `MachineState`, `Wasteclass`, `Material` | a Property with an IRI value points into the ontology |

Entity types are found by their root: the KMS declares `base_entities:Entity`
and everything else hangs beneath it. A package without such a root can declare
one as `entityRoot:` in `semforge.yaml`; a package with neither gets no
suggestions and is told why, rather than being offered every class in the file.

**The list is ranked, not alphabetical**, and each entry says why it is where it
is:

```
MachineState       vocabulary class · used by 1 shape(s) · 7 individual(s)
Wasteclass         vocabulary class · used by 1 shape(s) · 4 individual(s)
Material           vocabulary class · used by 1 shape(s) · 3 individual(s)
ChemicalElement    vocabulary class · 9 individual(s)
…
FieldType          vocabulary class · no individuals -- cannot be a value
```

Two signals do the ordering. A class already used as `sh:class` somewhere is a
proven value class rather than a guess. And a `sh:class` on a value says the
value IRI is an *individual* of that class, so a class with no individuals
cannot be the answer however plausible its name — those sink to the bottom and
say so. Alphabetically the KMS put `Binding`, `BoundConnector`, `BoundMap` and
`FieldType` ahead of the three you would actually pick.

**Typing narrows it.** For an ontology that fits, VS Code filters locally on the
name, the term and the detail. For one that does not, the server caps what it
sends and each keystroke asks it again — so a large ontology stays navigable
instead of arriving as a truncated list with no way to reach the rest. The
placeholder says which you are in (`showing 200 of 4,318; keep typing to
narrow`).

Every picker keeps **Enter a different value…** at the bottom. The suggestions
are a convenience, not a restriction — a list you cannot escape would make the
cooked view less capable than the file it edits.

The offered term is spelled for `shacl.ttl`, which matters more than it looks:
`knowledge.ttl` calls that namespace `default1:` while the shapes file calls it
`iffBaseKnowledge:`, and writing the wrong one would break the file on the next
parse.

The edit rewrites
**only that value** in `shacl.ttl` — changing `1` to `0` moves one byte and
leaves every comment in the file intact — then re-validates, so the Problems
panel follows immediately.

A padlock means shown but not editable here. Connectives (`sh:or`, `sh:node`)
are structure rather than a parameter, and a SPARQL body is not a form. They
appear so the tree does not lie about what the shape contains; edit them in the
`.ttl`.

**Output → SemForge** — pick "SemForge" in the dropdown of the Output panel.
This is where the server reports for itself, and the first place to look if the
Problems panel stays empty.

If you see none of that, the language server is not running — the table below
says why.

If nothing appears, open **Output → SemForge** in the dropdown for the server
log. The usual causes:

| Symptom | Cause |
|---|---|
| Problems panel empty, no SemForge output channel | the server exited at startup. Almost always `semforge` is not installed into the interpreter: run `make setup` again — it now does `pip install -e .`, which earlier versions did not |
| F5 offers a debugger list | the open folder is not `vscode/`; use method A |
| Output says `No module named semforge` | same as the first row: `cd semantic-model/SemForge-SDK && make setup` |
| Problems empty but the output channel exists | the file is not inside a package: its directory needs `knowledge.ttl`, `shacl.ttl` and `model-instance.jsonld` alongside it |
| Nothing after editing | analysis runs on open and on **save**, not on keystroke |

A language server that exits immediately is indistinguishable from one that
found nothing to report, which is why the first row is the first row.

---

## How it decides what to analyse

A *package* is any directory containing `knowledge.ttl`, `shacl.ttl` and
`model-instance.jsonld`. Opening any file inside one activates the service,
which walks up to find the root — an editor hands you a file, not a project.

Analysis runs on open and on save, over the whole package, because a constraint
in `shacl.ttl` is meaningless without the ontology and the examples.

---

## Commands

| Command | What it does |
|---|---|
| `SemForge: Restart Language Server` | after changing `semforge.pythonPath`, or if the server dies |
| `SemForge: Revalidate Package` | saves the active file, which re-runs analysis |

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `semforge.pythonPath` | `""` | Interpreter with `semforge` importable. Empty means look for `venv/bin/python`, then `python3`. |
| `semforge.trace.server` | `off` | LSP message tracing, for debugging the extension itself. |

---

## Limits worth knowing

- **Diagnostics land on `shacl.ttl` only.** Violations are attributed to the
  shape that raised them, not to the entity in `model-instance.jsonld` — mapping
  a finding back to a JSON-LD line needs a JSON position index that does not
  exist yet.
- **Cooked editing covers Core parameters only** — cardinality, datatype,
  class, nodeKind, ranges, lengths, pattern. That is deliberate rather than
  partial: those are the constraints that honestly fit one name and one scalar
  value. Connectives and SPARQL bodies are shown and locked.
- **No adding constraints from the tree yet.** You can change and remove what a
  shape declares; adding a new attribute or constraint is still a `.ttl` edit
  (the SDK can do it — `semforge.rdfio.add_property_constraint` — but no
  command is wired to it).
- **Analysis is whole-package on every save.** Fine at KMS scale (about a second);
  the incremental path exists in the plan and is not wired up.
