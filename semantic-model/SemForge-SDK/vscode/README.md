# SemForge for VS Code

Semantic modelling feedback while you edit: validation, coverage and
cross-artifact navigation over a SemForge package.

The extension itself decides nothing. It starts the SDK's language server and
renders what it sends, so the editor, the CLI and CI always agree — which is the
whole point of `architecture.md` §8.4.

---

## Getting started

**Once, ever:**

```bash
cd semantic-model/SemForge-SDK && make setup
```

That builds the venv and installs `semforge` into it. The extension finds it on
its own — it searches upward from whatever folder you opened.

**Then, every time:** open a folder in VS Code and click the SemForge icon in
the activity bar. Nothing else. No flags, no launch configuration, no terminal.

**Starting a new one?** Creating a project is a SemForge-level gesture, not a
constraint one, so it lives one layer above the artifact views: in the
**SemForge menu** on the status bar, in the **Package** view's title bar, and
on any folder in the Explorer (right-click ▸ SemForge):

| | does |
|---|---|
| **New project…** | makes a *folder* and scaffolds it, then offers to open it, open it in a new window, or add it to this workspace — the classical File ▸ New Project |
| **Create a package in this folder** | scaffolds the folder you already have |
| **Doctor** | what the extension sees and which server answers |
| **Delete project…** | moves the whole directory to the trash, after telling you what is in it |

On the command line: `semforge new "Plant Line"` creates `./plant-line`;
`semforge init <path>` scaffolds a directory you already have. Same scaffold
either way. An empty view also shows the buttons directly. It writes a package
that already works —
knowledge with one entity type and one vocabulary, shapes in the NGSI-LD
two-layer encoding, a scratchpad instance, and an example on *each side* of one
constraint so the suite proves the constraint can fire as well as be satisfied.
It refuses to write into a directory that already holds artifacts.

```bash
code semantic-model/kms        # or the repo root, or anything between
```

### If the trees are empty

Run **`SemForge: Doctor`** from the Command Palette (`Ctrl+Shift+P`). It prints
the folder it sees, the package it found, the interpreter it picked and where it
came from, whether that interpreter can import `semforge`, **which directory the
running server's code comes from and which methods it answers**, and the exact
command to fix it. Start there rather than in the output channel.

That second-to-last line matters more than it looks. The extension and the
server are shipped separately — the `.vsix` is JavaScript, the server runs from
your venv — so a server older than the extension shows every new icon and
answers none of them: the click does nothing, with no error and nothing in the
log. The doctor now says `This server is OLDER than the extension` and names the
missing methods. The fix is **`SemForge: Restart Language Server`** or a window
reload.

The usual answer is that `make setup` has not been run, or was run before
`semforge` became installable — in which case run it again and reload the
window.

### What counts as a package

Any directory holding `knowledge.ttl`, `shacl.ttl` and `model-instance.jsonld`
— **or a directory in place of any of them**: `shacl/` of `.ttl` files,
`knowledge/` of `.ttl` files, `model-instance/` of `.jsonld` files. The graph is
the union; an edit lands in the document that declares the thing being edited,
and the shape jump names that file. A file wins if both are present.

The data can also be grouped under **`model/`**, with the scratchpad and the
suite at the same level:

```text
model/
├── model-instance.jsonld   (or model-instance/, or bare *.jsonld)
└── examples/
```

The trees look identical either way.
`semantic-model/kms` is one. Open the package itself or the folder above it —
the trees look in each workspace folder and one level below it, so opening
`semantic-model/` finds `kms/`. Open higher than that and they wait until you
open a file inside a package.

### Which package am I on

The **status bar** says, bottom left: `📦 kms` — or `📦 kms/test`, because the
label is the path relative to the folder you opened and two directories called
`test` are not the same project. All the views show that one package; the
package is a property of the window, not of a view.

Clicking it opens the **SemForge menu**. VS Code gives an extension no way to
add a menu beside File and Edit — there is no contribution point for the menu
bar — so the status bar item is the one place everything hangs off, the same
answer the Python interpreter and the active Docker context use. Everything in
it is in the command palette under `SemForge:` as well.

| | |
|---|---|
| 📦 Switch package… | which package all the views show |
| ⚙ Project settings | name, contexts, namespaces — focuses the Package view |
| ✓ Revalidate | re-run analysis over the package |
| 📁 New project… / Create a package in this folder | scaffold — the level above the views, which is where a project belongs |
| ◎ Doctor · ⟳ Restart language server | when something is wrong |

**Switch package…** lists every package in the window — nested ones included,
which is where a scaffolded test project lives — and ends with **Follow the
active editor**:

* **following** (the default) — opening a file in another package moves all
  three views there. Right when you have one package.
* **pinned** (after you choose one) — the views stay put whatever you open.
  Right while you are reading a second package.

On the command line the same question is `semforge where`, and every command
that reads a package prints the one it resolved.

### Adding an entity

The **+** on a case or a model file asks for the type **first**, and offers
only what the knowledge declares — the entity hierarchy, each row saying which
shape will judge it and how many instances the model already has:

```text
Type — from the knowledge
  iffBaseEntities:Filter          judged by iffBaseShacl:FilterShape
                                  under iffBaseEntities:Machine · 2 in the model
  iffBaseEntities:Plasmacutter    judged by iffBaseShacl:CutterShape
                                  under iffBaseEntities:Cutter · 1 in the model
  ➕ New entity type…             declare it in the knowledge, then use it
```

There is no free-text box for the type, and that is the point: nothing rejects
an undeclared class, no shape targets it, so every constraint stays silent and
the entity reads as *validated*. A type that is genuinely missing is declared
first — the last entry writes the class into `knowledge.ttl` beneath a parent
you pick, opens the line it wrote, and then types the new entity with it.

The rule lives in the SDK, not in the extension: `add_entity` refuses a type
the knowledge does not declare, so no client can route around it.

Only the id is typed, and it is prefilled from the type (`urn:filter:3`).

### Adding an attribute

Same rule, one level down. The **+** on an entity offers the attributes the
knowledge declares *for that type* — `rdfs:domain` is the join, and it is
inherited, so a Plasmacutter is offered what a Cutter and a Machine carry:

```text
Attribute for urn:plasmacutter:1 — from the knowledge
  iffBaseEntities:hasState     Property · constrained
                               carried by iffBaseEntities:Machine
  iffBaseEntities:hasFilter    Relationship · constrained
                               carried by iffBaseEntities:Cutter
  iffBaseEntities:hasTrust     Property · constrained
                               no domain declared — carried by anything
  ➕ New attribute…            declare it in the knowledge, then use it
```

Then the **value** is picked the same way, from what the attribute's shape
allows — `hasState` on anything descending from Machine takes an individual of
`base:MachineState`, so the states are listed rather than typed. The shape is
found by walking the entity type's ancestors, so a type you declared a minute
ago gets its parent's constraints. *Type a value* is always the last entry, for
anything the shape does not constrain.

An attribute spelled wrong is not a broken document — it is an **invisible**
one. No `sh:path` selects it, so the constraint that should have judged the
value never fires and the entity reads as validated. The shipped kms has had
`iffBaseEntities:hasOutWorkpiecexx` in its model instance all along, two
letters from `hasOutWorkpiece`, and nothing ever said so.

**➕ New attribute…** asks for the name, whether it carries a *Property* (a
value) or a *Relationship* (another entity) — that decides which key holds the
payload and which half of the encoding a shape must constrain — and one line of
prose. It writes the declaration into `knowledge.ttl` with `rdfs:domain` (this
entity type) and `rdfs:range` (the NGSI-LD kind), and opens the line.

#### Nested attributes

A sub-attribute's subject is the parent's **attribute node**, and the encoding
types that node: `hasFilter` expands to a node `a ngsild:Relationship` carrying
`ngsild:hasObject`. So `rdfs:domain` works perfectly well — it is that node's
class:

```turtle
iffBaseEntities:hasTrust a owl:DatatypeProperty ;
    rdfs:domain <https://uri.etsi.org/ngsi-ld/Relationship> ;   # what carries it
    rdfs:range  <https://uri.etsi.org/ngsi-ld/Property> ;       # what it is
    rdfs:label  "a sub-attribute of hasFilter: how far the reading is trusted" .
```

An ordinary class, nothing invented, no punning — and the kms was already doing
it for `base:boundBy`. What domain constrains is the **kind** of carrier: this
may hang off any Relationship.

**Which** attribute it nests inside is the shapes', and only the shapes', to
say — a `sh:property` nested inside the parent's own property shape. The
two-layer encoding makes it exact: an inner `sh:property` on
`ngsild:hasValue`/`hasObject`/`hasJSON`/`hasValueList` is the *value*, and on
anything else a *sub-attribute*:

```turtle
sh:property [ sh:path iffBaseEntities:hasState ;
        sh:property [ sh:path ngsild:hasValue ; sh:class base:MachineState ] ,
                    [ sh:path iffBaseEntities:hasXXXWorkpiece ;      # ← nested
                      sh:property [ sh:path ngsild:hasObject ;
                                    sh:class iffBaseEntities:Workpiece ] ] ]
```

So the two halves answer different questions, and together they answer **which
attributes to offer when you nest one**:

| | says | used for |
|---|---|---|
| `rdfs:domain ngsild:Relationship` | may hang off any Relationship | the candidates |
| a nested `sh:property` | is placed inside *this* attribute | the ones already there |

Asking for the sub-attributes of `hasFilter` returns the placed ones first,
then the ones a Relationship is allowed to carry. Sub-attributes are **not**
offered among an entity's attributes — an entity does not carry one, and
putting `hasTrust` on a Filter would put it where no shape looks.

➕ **New attribute…** on a nested row names the parent attribute as the
carrier, and the declaration comes out as above. Placing the nested
`sh:property` in the shapes is still yours to do.

### Deleting a project

The one gesture no other gesture undoes, so it says the most before it happens.
The 🗑 sits on the **Project** row itself — the row that names the project — and
the same action is in the SemForge menu, in the Package view's title submenu,
and on a folder in the Explorer. It shows what the directory actually holds:

```text
Delete the project "test"?

/home/you/kms/test

10 file(s), 8 KB.

1 item(s) here are not part of the package: notes.md. Nothing else knows
what they are.
Nothing here is tracked by git, so nothing can bring it back.
```

Three things you cannot see from a tree row, and the reason the server is asked
first: what in there is **not** the package (a README somebody wrote, a scratch
file, a vendored copy — that is what a deletion actually costs), whether it
holds **packages of its own**, and whether **git has any of it**. Tracked files
come back with one command; untracked ones do not come back at all, and the
warning says which you have.

Then it asks again: type the folder name. A modal is dismissed by the same
reflex that opened it, and this is the wrong place for a reflex.

It goes to the **trash**, not to `unlink`. A confirmation is a guess about what
somebody meant; the trash is the thing that forgives being wrong. Nothing in
the SDK deletes — `semforge.package.removal` only plans, and has no `rmtree` in
it.

### The Package view (formerly Project)

The first of the views, and the one that says what the package *is*
rather than what it says. Its first row is **Health**, the package at a glance
(`6/6 cases pass · 3 violation(s) · 67 untested`); a click opens the health
page. It is red only for what is wrong with the package itself — a failing
case or a broken reference — since violations in the model data are
information. It is asked for after the rest of the view, so a slow first
computation never holds up the settings beneath it.

```text
Project      Cutting cell
  name       Cutting cell          ✎
  path       /home/you/kms/test
  recognised by  semforge.yaml
  manifest   semforge.yaml
Settings     semforge.yaml — click the pencil to change one
  local context      context.jsonld            ✎
  published context  https://…/context.jsonld  ✎
  entity root        —  not declared           ✎
  namespaces         4
  dependencies       0
Contents     13 shape(s) · 44 entity(s) · 6 case(s)
  knowledge / shapes / model   which file or directory, and how many documents
  test cases  6   4 suite(s): test_CartridgeShape, …
```

Every row that names a place carries `file:line`: clicking a setting opens its
line in `semforge.yaml`, so the paragraph explaining it is right there.

**Namespace prefixes are a package-wide table**, agreed once and binding on
every artifact: `knowledge.ttl`'s `@prefix`, `shacl.ttl`'s, and the model's
context all have to mean the same thing by the same name. rdflib binds one
prefix per namespace, so a second name evicts the first and a term copied
between artifacts changes meaning.

`rdf`, `rdfs`, `owl`, `xsd`, `sh` and `ngsild` are **known to every package**
and appear under *standard names* on that row. Nobody should have to write them
down: a package that listed them would carry boilerplate that can only drift,
and one that forgot would be told its own `shacl.ttl` had invented `sh:`.
They sit at the lowest precedence, so a package that has a reason to call one
of them something else declares it in `semforge.yaml` and that wins.

Every name appears **once**. A package that declares one of the standard names
with the standard IRI sees it under *standard names*, not in its own table — it
is the same name, and listing it above as this package's vocabulary is what
made `ngsild` look like two definitions. The row still carries its `file:line`
and says the line can go. Declaring one with a *different* IRI is a deliberate
override, so that one stays in the package's table and says what it overrides.

🗑 on a name **removes** it, in three steps depending on what the name is doing:

* **nothing uses it** — removed, no question;
* **in use, but removing it changes nothing** — because `context.jsonld` names
  it too, or it is one of the standard set — you are asked first, with what
  binds it and why it is safe: *"ngsild: is in use — <…> is bound in shacl.ttl
  and names 121 term(s). Removing this line is safe anyway: the standard set
  names it "ngsild:", so the table does not change."*;
* **in use and load-bearing** — refused: *"iffBaseShacl: cannot be removed — it
  is in use. <…> is bound in shacl.ttl and names 42 term(s), and nothing else
  in the package gives it a name."* Taking it out would leave every one of
  those terms undefined.

Usage is measured from both halves that matter: files whose `@prefix` binds the
namespace, and terms actually in it. A line that merely restates
`context.jsonld` says so on its row before you click — it reads as this
package's own vocabulary and is not.

The **namespaces** row is where that table lives. ➕ on it defines a new one —
it asks for the name and the IRI, refuses one that would collide with an
existing name or give a namespace a second name, and writes it to
`namespaces:` in `semforge.yaml`. The row itself turns red when an artifact
disagrees with the table, and the disagreement shows on the offending
`@prefix` line as a diagnostic. On the command line that is `semforge prefixes`
(`--define plant=https://example.org/plant/` to add one, `--fix` to align the
artifacts).

The pencil edits it. The write is **line-based**: it replaces the value on that
one line and leaves the rest of the file byte-for-byte, because the comments in
`semforge.yaml` are the documentation and a YAML round-trip deletes all of
them. A package with no `semforge.yaml` at all — the kms layout — gets one on
the first edit.

Two rows carry a warning rather than a blank: a **published context** that is
not declared (`semforge export` has nowhere to point the model) and **no test
cases** (nothing proves a constraint can fire). A setting that is simply not
set says so and names what applies instead — a list of whatever happens to be
in the file cannot show what you have *not* set, which is most of what you need
to know about a package you did not write.

**If a tree is empty it now says why** in the panel itself: no package found (and
what it looked for), the server not running, or whatever the server reported.
An empty panel with no message was indistinguishable from a broken extension,
which cost a day.

If you keep your interpreter somewhere the search will not find, set
`semforge.pythonPath`.

---

### The Vocabulary view (formerly Knowledge)

Three groups, for the three things `knowledge.ttl` declares:

```text
Entity types         8 type(s) under Entity
Vocabulary classes   …
Attributes           17 attribute(s) · 21 ontology relation(s)
  iffBaseEntities:Machine                1 attribute(s)
    iffBaseEntities:hasState             Property · 12 use(s)          ⚖
      iffBaseEntities:hasXXXWorkpiece    Relationship · inside hasState · 6 use(s)
  iffBaseEntities:Cutter                 5 attribute(s)
    iffBaseEntities:hasOutWorkpiece      Relationship · used by nothing   ⚠
  Ontology relations   used within the ontology, never as a document key
    material:contains                    22 statement(s)
```

Attributes sit under whatever **carries** them — the entity type from
`rdfs:domain`, shown where it is *declared* since it is inherited from there
down — and a sub-attribute sits under the attribute it nests inside, never at
the top. `rdfs:subPropertyOf` nests too, where a package uses it. The ⚖ on a
row opens the property shape that constrains it.

`knowledge.ttl` also declares the ontology's **own** relations —
`base:bindsFirmware`, `material:contains` — which are never keys in a document
and which no shape should constrain. They are shown apart and judged apart:
calling them unused and unchecked is true of a document and meaningless of an
ontology. They are flagged only when nothing uses them at all, data or
ontology.

An attribute is flagged when no shape constrains it (nothing is ever checked
against it), when no document carries it (no constraint about it can fire), or
when it has no `rdfs:range` (nothing says whether it is a Property or a
Relationship, and the two carry their payload under different keys).

### The NGSI-LD vocabulary

A fourth group, last, and not the package's: the terms of the **encoding**.

```text
NGSI-LD vocabulary   12 term(s) · shipped with the SDK
  Attribute kinds    what an attribute's `type` may say
    ngsild:Property        64 use(s) · a value: a literal, or an IRI naming a term
    ngsild:JsonProperty     3 use(s)
    ngsild:GeoProperty     not used here
  Slots and metadata  where the payload hangs, and what is recorded beside it
    ngsild:hasValue        62 use(s) · `value` in JSON-LD
    ngsild:observedAt       7 use(s) · orders the instances; the latest is validated
```

Until now this was the one rule the project did not apply to itself. Everything
else must be declared before it is used — but `rdfs:range ngsild:Property`
pointed at a class no file declared, so `ngsild:Propery` was not an error
anywhere: the attribute simply had no kind, and nothing said why. A term the
package uses and the vocabulary does not declare is now reported, in this group
and under `semforge test`.

It is **not an ordinary dependency**. A domain vocabulary is the package's
business and goes in `dependencies:`; the encoding is what makes it an NGSI-LD
package at all, every one needs it, and a package that forgot to declare it
would silently lose the terms every `sh:path` names. So the SDK ships it and
always loads it. To use your own copy:

```yaml
ngsild: ./vendor/ngsild.ttl        # or an http(s) url, fetched and cached
```

Upstream is
[`ngsild.ttl`](https://industryfusion.github.io/contexts/staging/ontology/v0/ngsild.ttl),
which declares `Property` and `Relationship`. The shipped kms uses **ten**
NGSI-LD terms, so what ships here is that file extended — the five attribute
kinds, the four payload slots, and the three metadata keys. Nothing is
invented: every class is a value of an attribute's `type` in the NGSI-LD API and
every predicate is what the NGSI-LD `@context` maps a payload or metadata key
to. The additions are marked in the Turtle so they can go back upstream.

## Working on the extension itself

Only needed if you are changing the extension's own code:

```bash
cd semantic-model/SemForge-SDK/vscode
npm install
code --extensionDevelopmentPath="$PWD" ../../kms   # or press F5 in this folder
```

Packaging and installing it instead:

```bash
npx @vscode/vsce package
code --install-extension semforge-0.1.0.vsix --force
```

Remember that VS Code loads extension JavaScript at window startup, so a change
there needs **`Developer: Reload Window`** — `SemForge: Restart Language Server`
only restarts the Python process.

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

**Find all references** (`Shift+F12`) goes the other way, from any term to every
place that names it: the `sh:path` that constrains it, the SPARQL body that
reads it, the ontology, and every example case that carries it -- as a key, as a
type, or as an IRI value like `{"@id": "base:state_OFF"}`. It works from a
`.ttl` or a `.jsonld`, and matches on the expanded IRI rather than the text: a
term is expanded the way the file it sits in would expand it (a Turtle file by
its prefixes, a query by its own `PREFIX` lines, a document by its `@context`),
so `iffBaseShacl:CartridgeShape` and `iffFilterShacl:CartridgeShape` stay two
terms, and `iffBaseEntities:hasObject` is not taken for `ngsild:hasObject`.
Only a name that cannot be expanded at all falls back to its local name.

**One click shows the row and leaves it open.** Selecting a row moves the file
to it *and* unfolds it. A click on a collapsible row toggles it, so the reveal
that showed you an entity also folded it shut — you had to click twice to see
what one click was supposed to show. The chevron still folds it.

**A click opens the row's page.** Tree → page → source: a click on a type or
an attribute in Constraints opens that type's page with the attribute marked; a
row inside a test case in Model opens the case page with its entity marked; an
entity type or one of its attributes in Knowledge opens the type page. One tab
is reused, and focus stays in the tree, so you can arrow through the rows and
watch the page follow. Rows that have no page yet — vocabulary, the model
scratchpad, settings — still move the editor to their source.

**The source is a right-click away**: **SemForge: Open source** on any row of
the three trees. Every node carries its own `file:line` — an attribute, a
single `sh:minCount`, not just the shape — so the editor lands on the line you
picked rather than the top of the block. To have a click do that instead, as it
used to, set *Settings → SemForge → Trees: Click* to `source`.

**One icon per kind**, the same in every view: `symbol-class` an entity type,
`symbol-field` an attribute, `symbol-event` a rule, `beaker` a test suite or
case, `symbol-object` an entity in the data, `symbol-enum` a vocabulary and
`symbol-enum-member` its values. Status is the icon's **colour** — red failing
or violated, yellow a warning, green a passing case, grey inherited — and the
description says it in words; a row never changes its icon to say it is wrong.
In summary mode rows have no hover buttons: their actions are on the right-click
menu and on the page. *Trees: Detail* `full` brings the buttons back.

**Outline** lists every shape in the file.

> Both halves of a click are ordered deliberately: the tree unfolds or reveals
> first, the editor moves second. Opening a file can refresh a tree, and a
> refresh makes VS Code drop the handles it uses to find nodes — a reveal after
> that silently resolves nothing. For the same reason a tree no longer refreshes
> when you open a file in the package it is already showing: that was a full
> re-validation per click, and the refresh was what broke the reveal.

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

A **greyed icon** and `from Machine` in the description mean the constraint is
inherited: it is declared on a
supertype and applies here because `sh:targetClass` reaches subclasses. `Filter`
shows `MachineShape`'s `hasState` for that reason — the constraint was never
missing from Filter, only from the tree. Right-click offers **Go to Definition** and **Declare on This Type**.

**Adding an attribute to a shape** is the **+** on one of the type's *own*
shape rows (an inherited shape has none — adding there would write into the
supertype's shape). It offers the attributes the knowledge gives that type,
and lists the ones it cannot add too, so the one you came for is never silently
missing:

```text
Add an attribute to iffBaseShacl:CartridgeShape
── Declared for this type ─────────────────────────────
  hasWasteclass   Property · iffFilterEntities:hasWasteclass
── Already constrained ────────────────────────────────
  isUsedFrom      already constrained by this shape — edit it there
  hasState        already constrained by iffBaseShacl:MachineShape
```

Then it asks two things: **Optional** (`sh:minCount 0`) or **Required**
(`sh:minCount 1`), and what the **value** must be — for a Relationship, which
entity type it points at; for a Property, a datatype (`xsd:double`, …) or a
vocabulary class whose individuals are the allowed values. The kind is never
asked: it is the attribute's `rdfs:range` in the knowledge. What is written is
the full two-layer encoding, inserted into the shape's own statement so every
comment around it survives:

```turtle
    sh:property [ sh:path iffFilterEntities:hasWasteclass ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:nodeKind sh:BlankNode ;
        sh:property [ sh:path ngsild:hasValue ;
            sh:minCount 1 ;
            sh:maxCount 1 ;
            sh:nodeKind sh:IRI ;
            sh:class iffFilterKnowledge:Wasteclass ] ]
```

**Which namespace a new attribute gets.** By default the namespace of the type
that carries it — an attribute of `iffBaseEntities:Cutter` is
`iffBaseEntities:…`. But a namespace is ownership, not location: the kms's
`hasWasteclass` is carried by a base type and owned by the filter extension,
`iffFilterEntities:`. So after the name, when the package has more than one
candidate, a picker shows each choice as the full name it would write
(`iffFilterEntities:hasPressure`), the default first, then the namespaces that
already hold attributes, then the rest — never a standard vocabulary (rdf, owl,
sh, ngsild) and never a namespace that holds only shapes. Typing the prefix
into the name (`iffFilterEntities:hasPressure`) skips the question. A prefix the
package does not know is refused, not dropped — define it in the Package view
first.

If the attribute does not exist yet, the last entry, **New attribute…**,
declares it in `knowledge.ttl` for the shape's type and carries straight on to
the two questions above. The same flow is **SemForge: New attribute…**, which
starts by asking for the type instead and is reachable without the tree: the
Command Palette, the SemForge item in the status bar, right-click on a `.ttl`
or `.jsonld` (editor or Explorer) → **SemForge**, and the **symbol** button in
the Constraints and Vocabulary view titles. VS Code gives an extension no menu of
its own beside *File* and *Edit*, so these are the places one can live. Started
that way it offers **Not now** too — declaring alone is a fine place to stop —
and a type with no shape of its own is declared and told so, rather than having
the attribute written into an inherited shape, where it would be demanded of
every sibling type.

It refuses, and writes nothing, for an attribute the knowledge does not
declare, one it gives to a different type (required here it would be demanded
of entities that never carry it), a sub-attribute, one this shape already
constrains, and one a supertype's shape constrains — that is an override, and
**Declare on This Type** is the command that says whether it would take effect.

**Sub-attributes.** In NGSI-LD an attribute can carry attributes of its own —
the kms's `hasTrust` hangs off `hasFilter`, `hasXXXWorkpiece` off `hasState`.
The **+** on an *attribute* row in the Types view adds one: it offers what
the knowledge allows inside that attribute (a sub-attribute's `rdfs:domain` is
the parent's kind of node, `ngsild:Relationship` or `ngsild:Property`), ends in
**New sub-attribute…** to declare one carried by that attribute, and writes the
same two layers an attribute gets, *inside* the parent's `sh:property [ … ]`:

```turtle
    sh:property [ sh:path iffBaseEntities:hasFilter ;
        …
        sh:property [ sh:path iffBaseEntities:hasConfidence ;
            sh:minCount 0 ;
            sh:maxCount 1 ;
            sh:nodeKind sh:BlankNode ;
            sh:property [ sh:path ngsild:hasValue ;
                sh:minCount 1 ;
                sh:maxCount 1 ;
                sh:datatype xsd:double ] ] ]
```

In the Tests view, right-click an attribute → **SemForge: Add Sub-attribute**
puts one into that attribute instance — the one the row shows, chosen by its
datasetId when the attribute has several. An entity attribute is refused
inside another attribute, a sub-attribute is refused inside a parent of the
wrong kind, and a duplicate is refused; none of them write anything.

**Deleting an attribute** is a right-click on its row in the Knowledge or
Types view (**SemForge: Delete attribute…**; from the palette it asks
which). An attribute is never in one place, so nothing is removed before you
have seen all of them:

```text
hasWidth is in use. Delete it and everything that depends on it?

the declaration (1)
   knowledge.ttl:75  the declaration of hasWidth
property shapes (1)
   shacl.ttl:296  iffBaseShacl:WorkpieceShape: the property shape on the entity
entities carrying it (4)
   model-instance.jsonld:252  urn:workpiece:1 carries it
   examples/subobjects/workpiece-steel.jsonld:15  urn:workpiece:1 carries it
   …
                                       [ Delete with 5 dependent(s) ]
```

One yes removes the declaration, every `sh:property` group whose path is the
attribute (nested ones too, with whatever is nested inside them), the key in
the model and every example, and each expectation assert naming one of those
constraints — computed and verified first, then written all at once, or not at
all. A case left expecting a violation it no longer asserts is called out.

The other button, **Delete declaration only**, removes the statement in
`knowledge.ttl` and nothing else — every shape, key, assert and query stays as
it is. Use it when the term is moving to another ontology, or when you would
rather rewrite its uses by hand. It is offered whenever the attribute is in
use, including when the full delete is blocked, since it touches none of the
blockers. What it leaves is not silent: each remaining use shows in the
Problems panel as naming an undeclared term, until it is declared again or the
use is removed.

Two kinds of use **block** the full delete: a SPARQL constraint or rule that reads
the attribute, and a shape or ontology statement that names it outside a
property shape (the kms's `CartridgeShape` uses `hasCartridge` inside a two-hop
inverse path). A query is not a list of parts — cutting the attribute out of it
changes what the rule means, and leaving it makes a rule that silently matches
nothing. The dialog lists them and opens the first, and deletes nothing.

**The package health page.** Is this package in good shape, and what needs
attention first? The first entry of the status bar's SemForge menu (also the
pulse button on the Package view, or **SemForge: Open package health**) opens
one page that puts side by side what `test`, `validate`, `check` and
`--coverage` each answer on their own:

- **figures**: test cases passing, violations in the model, constraints
  evaluated (the same count `semforge validate` prints), constraints no
  example makes fire, broken references, and the cache;
- **needs attention**: one list, errors first — a failing case, a reference
  that points at nothing, an undeclared attribute in a case — then warnings,
  where what is broken (a violation in the model) comes before what is merely
  untested (a constraint that never fired), then notes. Every item has the
  button that opens what it is about: the case page, the type page, or the
  line.

**Rescan** on the page rebuilds everything from scratch, ignoring the cache.

**New test case… — adding a test file.** The `+` in the Tests view title (also:
right-click a suite, the status bar menu) asks:

- **which suite** — an existing one, or a new one for a shape (`test_PumpShape`);
- **should it conform or violate** — `good/` with `expect: valid`, or `bad/`
  with `expect: invalid`;
- **where it starts** — a copy of a case (its includes written into the new
  file, so editing it never changes a shared subobject), an entity from the
  model, a new entity of a type (its required attributes given valid values),
  or an empty file;
- **its name** (suggested).

It is written, declared in that folder's `expectations.yaml`, run once, and
its case page opens. A bad case is declared without asserts: what fires shows
on the case page, where **Assert it** turns each firing into a claim; while
nothing fires the message says so. A `.jsonld` already under `examples/` that
no expectations file declares — a file nobody runs — is offered too
(**Declare a file under examples/ that nothing runs**) and is declared where
it is.

**New test… for an attribute.** A new attribute needs cases that prove its
constraints work. Right-click it in the Types view (**SemForge: New test for
this attribute…**), or use its row on the type page — the **Tested** cell
("New test…" while untested) or the row's `⋯` menu. It asks what the test
should prove:

- **valid** — the attribute present with a valid value; the case conforms;
- **fires: …** — one per constraint that can actually fire: *missing* (a
  required attribute left out), *no value*, *twice* (two instances, a
  `maxCount` exceeded), *wrong datatype* (a text where `xsd:double` is
  expected), *too high / too low* (one past `sh:maxInclusive` /
  `sh:minInclusive`), *wrong class* (an IRI that is not a MachineState),
  *wrong kind*, *not in the list*. An optional attribute is not offered
  *missing*: leaving it out cannot fire.

Then a name (suggested: `pressure-wrong-datatype`). The case lands in
`examples/test_<Shape>/good|bad/`, declared `expect: valid`, or `expect:
invalid` with an assert that this constraint fires on that entity. Its scene
is a valid case with an entity of the type (includes written into the file),
else the model's entity, else a new entity with every required attribute
given a valid value. If the entity already has the attribute it is changed,
not replaced — a sub-attribute nested in it stays. The case is run once, and
the message says whether it already passes; the few breaks that cannot be made
mechanically (a Relationship that is not an IRI) say what to edit instead.

**The test case page.** A case answers three questions — what it claims,
whether the claims hold, what data it uses — and the Model tree spread them
over up to nine levels. A click on a case in the Tests view, or on
any row inside it (or **SemForge: Open test case page**), opens a page that answers them in
that order:

- **the claim**: *expects invalid · passes*, with `semforge test`'s own failure
  messages when it does not — the page runs the case exactly as the test
  runner does, so the two cannot disagree;
- **claims**: each assert, *holds* or *does not hold*, in plain words
  ("hasCartridge is required but missing on urn:filter:9"); then everything
  that fired without being asserted, marked *also fired* — either a second
  problem the case found, or a sign the data is not what the case means it
  to be;
- **data**: the case's own file and each include as sections (an include
  says how many other cases share it, because an edit there changes them
  too), one card per entity with its attributes and sub-attributes. A
  violation sits on the attribute it is about — a missing sub-attribute on
  the attribute it belongs inside — with SHACL's raw message as the tooltip.

Ids, attributes and files link to their line; an entity's type opens the
type page.

**Assert it.** Each *also fired* line has two buttons. **Assert it** turns the
firing into a claim: the assert is added to that case in its
`expectations.yaml` (comments and layout kept) and the line moves to *holds*.
That matters because an unasserted firing is checked by nothing unless a
residue is pinned — if the constraint stopped firing, `semforge test` would
stay green. Asserted, the case fails the day it stops. **Open in .jsonld** is
the other answer: when the firing only happened because the case's data is
incomplete (the kms's `without-cartridge` filter has a `hasState` without the
`hasXXXWorkpiece` MachineShape requires), fix the data so the case fails for
exactly one reason, rather than pinning the accident as expected. The button's
tooltip says so. A duplicate assert, or one on a constraint no shape declares,
is refused; a case with a pinned residue is told to `semforge accept` again.

**Summary trees.** The trees are for finding things; the type page is where a
type is read and edited. So by default the trees show one row per meaningful
thing, said once (the `semforge.trees.detail` setting, `summary`):

| View | Summary | `full` |
|---|---|---|
| Types | the entity type hierarchy; under each type its OWN attributes (`hasCartridge — required · one · → FilterCartridge`, an inverse path as `inverse of hasCartridge`) and one **Rules** row, then its subtypes. Inherited attributes are on the type page, not repeated under every subtype | types → shapes → every SHACL parameter as a row, editable in place (192 rows for the kms) |
| Shapes | every shape, prefixes dropped where unique | every shape, full names |
| Tests | the suites and their cases at the top (`FilterShape — 1 case(s) · all ok`), the model document last as one **Model data** row (`8 entities · 3 violation(s)`), closed; an entity's type in its row, each value once (`hasStrength — 0.6`) | **Tests** and **Main** groups, a separate `type` row, `0.6 — 0.6 · Property` |
| Vocabulary | no Entity types group (that is the Types view); a vocabulary class counts its values (`MachineState — 7 values`); `3 shape(s)` instead of a list; an id in several files is one row | every group, every file's row |

Prefixes are dropped wherever the local name is unambiguous in that tree; the
two `CartridgeShape`s keep theirs. In summary mode **Override…** and right-click
→ **Open entity type page** on any Constraints row go to the type page, where
each parameter is. Switch with *Settings → SemForge → Trees: Detail*; all
trees redraw at once.

**Types and Shapes: read by type, written by shape.** A SHACL shape is not tied
to an entity type. It selects focus nodes by class (`sh:targetClass`), by named
node (`sh:targetNode`), by the subjects or objects of a predicate
(`sh:targetSubjectsOf`, `sh:targetObjectsOf`), by a SPARQL query (`sh:target`,
SHACL-AF), implicitly when the shape is itself a class — or it has no target
and is reached from another shape through `sh:node`. So constraints have two
views:

- **Types** (formerly Constraints) answers *what must a Filter carry*: the hierarchy, a click opening
  the type page. The page **collects every constraint that applies** to the
  type — its own shapes', the inherited ones (`· from Machine`), and those of
  shapes that reach it by another target, in the same tables, marked with the
  condition: a shape on `sh:targetSubjectsOf hasValve` puts its rows on the
  Pump page as `· only when it has hasValve`. That is decided from the
  knowledge where it can be (hasValve's `rdfs:domain` is Pump), so it shows
  before any data exists; a named node or a SPARQL target is found through the
  data. Such rows are edited on their shape's page (**Open shape**). SPARQL
  constraints and rules are listed under **Rules on the whole entity**.
- **Shapes** answers *what does this shape check and what does it reach*: one
  row per shape, its target in words (`targets Filter`, `targets subjects of
  hasValve`, `targets urn:valve:1`, `SPARQL target`, `no target · used by
  ValveNodeShape`). A click opens the **shape page**: the target (a SPARQL
  target's query included), the attributes and rules as the type page shows
  them, the nodes it reaches in the model with their verdicts, the types those
  are, and the test cases that reach it and whether it fires in them.

  The page is laid out as SHACL is: **Selects** — the node selector, every
  target with **Remove** (a SPARQL target, being a query, stays in the `.ttl`)
  and **+ Target** to add one (several targets add up; taking off the last
  one leaves a shape that runs only where another reaches it via `sh:node`)
  — then **Constraints**, in two parts: **on its attributes** (the table) and
  **on the whole node** (its SPARQL constraints and rules, with the query),
  then what it **Reaches** and the **Evidence**.

  Its attributes are **edited exactly as on the type page** — the same rows,
  the same actions: click the presence or the value, the `⋯` menu (edit a
  constraint, add a sub-attribute, remove from the shape, delete, New test…),
  the Tested cell, and **+ Attribute** — every write going into this shape. A
  shape without a class target offers every declared attribute (no type to
  scope them to); New test… there needs a type, so it says to start from the
  type page of an entity the shape reaches. A shape that is itself a class
  (`ex:Gauge a rdfs:Class, sh:NodeShape` — an implicit class target) counts
  as that type's own shape everywhere: in the Types tree, as the shape the
  type page edits and **+ Attribute** writes into, never as one that applies
  "under a condition".

**New shape….** The `+` in the Shapes view title (also: right-click a type in
Types, the status bar menu) asks what the shape selects — an entity type,
one entity, everything that has an attribute, or everything a Relationship
points at — then the target and a name (suggested: `PumpShape`), and writes
`ns:PumpShape a sh:NodeShape ; sh:targetClass ns:Pump .` into the shapes
file, in the namespace the other shapes use, checked by parsing before it is
kept. Its page opens; attributes and constraints are added there. A type with
no shape of its own shows **Create its shape** on its page, which then offers
**+ Attribute**.

**A rule's evidence, and New case….** For a shape with a SPARQL constraint
or rule the page says **what it checks** (its `sh:message` and severity — the
kms's own `base:severityWarning` reads as *warning*), the **evidence** (the
cases it fires in and on which entity, the cases it is evaluated in and
holds), and **the query**, read-only, with its prefixes. A SPARQL constraint
that fires in no case gets **New case…**: it writes
`examples/test_<Shape>/bad/<name>.jsonld`, copied from a case where the shape
is evaluated and holds (a valid one first, so no other shape's violation comes
along; its includes written into the file, so editing an entity does not
change a shared subobject), and declares it `expect: invalid` with an assert
that the shape fires on that entity. The case fails until you edit its data so
the rule is broken — it cannot pass by accident. With no case to start from it
copies the model's document for an entity the shape reaches. A `sh:rule`
derives data rather than firing, so it gets the query and no New case….

Validation runs every shape that has a target, of any kind. Until this release
it ran only `sh:targetClass` shapes — a shape written with `sh:targetNode` was
never checked, and nothing said so. `tests/corpus/targets` has one shape per
target kind and pins all of it.

**The vocabulary page: value lists and their care.** A vocabulary class —
MachineState, Wasteclass — is a closed list of named values, and a value is
never just a declaration: `sh:class base:MachineState` makes `hasState` hold
one of them, a SPARQL rule tests for `base:state_ON`, a case writes
`{"@id": "base:state_OFF"}`. A click on a vocabulary class in the Vocabulary
view (or on one of its values, which is then marked) opens its page:

- **Values**: each with its label, its other properties (`isValidFor Machine`,
  `higherHazardLevel WC0`) and where it is used, counted per kind — `7 in data
  · 6 in queries` for state_ON, the places in the tooltip. A value nothing
  names is **unused**; MachineState has four.
- **Drawn from by**: the constraints that take their values from the class
  (`MachineShape · hasState · sh:class`) or list some of them (`sh:in`), each
  opening its shape page. None is a warning: nothing checks that an attribute
  holds one of the values.
- **Relations** whose domain or range is the class, and its subclasses.

Managing it happens on the page, with visible buttons:

- **+ Value** asks a name and an optional label and appends
  `ns:name a owl:NamedIndividual, ns:Class ; rdfs:label "…"` in the class's
  namespace and file.
- **Label…** (click the label) changes it in place, adds one, or removes it
  when emptied — the rest of the statement untouched.
- **Delete…** removes exactly the value's statement. A value in use shows
  where first and needs **Delete anyway**; each use left behind then names an
  undeclared value, which the Problems panel reports. Adding and deleting an
  unused value leaves the file byte-identical.
- **New vocabulary class…** — in the Vocabulary view's `…` menu (its `+` is New
  attribute), on the *Vocabulary classes* row, in the status bar menu —
  declares `ns:Name a owl:Class`, on its own or under another vocabulary class,
  and opens its page.

**The entity type page.** The trees are for finding things; reading one type's
whole story in them took three views and, for Filter, 39 rows. A click
on a type or attribute in the Types view, or on an entity type in the
Vocabulary view (also: right-click an entity in the Tests view, or
**SemForge: Open entity type page** in the palette) opens one page in the
editor area — its tab reads `Filter · type` — with all of it:

- **where it sits**: a breadcrumb up the hierarchy (click to open a parent's
  page) and its subtypes;
- **its attributes, own and inherited**, one row each, in the model's words
  instead of SHACL — `required · one`, `number · 0 – 100`, `→ FilterCartridge`,
  `one of MachineState`. Inherited rows are dimmed and say where from;
  sub-attributes sit indented under their parent. Anything the vocabulary
  cannot say is shown verbatim, never hidden;
- **Tested**: whether any test case makes the attribute's constraints fire
  (*both ways* / *fires only* / *never fired* — a constraint that cannot fire
  looks exactly like one that is satisfied);
- **Model**: how many entities in the model violate it;
- **its rules** (SPARQL), with their message and whether they ever fired;
- **the cases that exercise it** and whether they pass, and **its instances in
  the model** with what is wrong with each.

Every name links to its line in the `.ttl` or `.jsonld`. It is one reused tab,
refreshes on save, and is served from the cache.

**Several shapes on one attribute.** A type has no single shape: every shape
that targets a Machine is evaluated against every Machine, and SHACL conjoins
them — an entity conforms only if it satisfies all. So an attribute two shapes
constrain is **one row**, saying what holds when both apply:

```text
hasPressure   required · one   number · ≥ 0 and < 100      2 shapes · all apply
  MachineShape    optional         number · ≥ 0 and < 100   sh:minCount 0: no effect
  MachineShape2   required · one   < 200                    sh:maxExclusive 200: no effect
```

The highest minimum and the lowest maximum count win, and so do the tightest
bounds (an exclusive one at an equal value); each shape's line marks what of
it the others outdo. Contradictions are said in red — two datatypes no literal
can have at once, bounds or counts that admit nothing. A shape that applies
only under a condition is listed beneath the row but not merged into it.
Clicking the presence or value of the combined row asks **which shape** to
change; each shape's own line has its own `⋯`. The Types tree shows the
attribute once (`2 shapes, all apply`).

**Editing on the page.** What is dashed-underlined is clickable, and every
action is a visible button rather than a hover icon:

| On | Click | Does |
|---|---|---|
| your own attribute | **Presence** | Required or Optional (`sh:minCount`) |
| your own attribute | **Value** | what the value must be — an entity type, a datatype, a vocabulary class, or any value; ranges and counts are kept. A value written with `sh:or`/`sh:in` is not rewritten by a picker; the tooltip says so |
| your own attribute | **⋯** | New test… · **Constraints…** · add a sub-attribute · remove it from this shape · delete the attribute everywhere · open in `.ttl` |
| your own attribute | **⋯ → Constraints…** | the constraints it carries — change or remove each — and every one it does not carry yet, to add: `sh:minInclusive` (≥), `sh:maxInclusive` (≤), `sh:minExclusive` (>), `sh:maxExclusive` (<), `sh:datatype`, `sh:class`, `sh:nodeKind` (picked from what fits), `sh:minLength`, `sh:maxLength`, `sh:pattern`, and `sh:minCount`/`sh:maxCount` on the attribute (instances) or on the value |
| an inherited attribute | **Override…** | a stricter constraint on this type's own shape — warns when the change could never take effect |
| the header | **+ Attribute** | the attribute picker, for this type's own shape |

Each edit is the same text-anchored, verified write as everywhere else, and
reads like a hand edit: swapping one class for another changes one line, and
nothing leaves a blank line behind. The page and the three trees refresh after
it.

An added constraint lands on its own line, indented like its neighbours; one
already there is replaced, not doubled. A datatype, range, length or pattern
goes on the **value** (on the attribute node it would constrain the blank node
itself and never hold — refused, with that reason); an attribute with no value
layer gets one (`sh:property [ sh:path ngsild:hasValue ; … ]`). Bounds that
together admit nothing (`> 100` and `≤ 16`) are written as asked and said in a
warning. The Value column words them: `> 0 and ≤ 16`, `at most 20 characters`,
`matching ^[A-Z]+$`.

**The cache: why reloading is fast, and how to distrust it.** What every view
and the Problems panel show is stored beside the package, in
`.semforge/cache/views/` (one JSON file per view, never committed — it carries
its own `.gitignore`). Each entry is stamped with a fingerprint of every file
of the package — path, size, modification time, symlinked folders included —
and of the SDK's own code; while that fingerprint holds, a reload serves the
stored result instead of rebuilding it. Any edit, checkout or SDK update
changes it, and the next request recomputes, so nothing stale is served by
design. Measured on the kms: a cold start takes about 4.6 s to have all four
views ready, a reload with nothing changed about 1.6 s (most of it starting
Python).

The other half of the old wait was the network: every JSON-LD document names
the NGSI-LD core `@context` by URL, and rdflib downloaded it again on every
parse — 44 times for one Knowledge-view build. It is now fetched once per
machine and kept in `~/.cache/semforge/contexts/`, which also makes scanning
work offline.

The Package view's last row, **Cache**, says how many views are stored and
whether they are current. Its 🔄 **Rescan** ignores the cache and analyses from
scratch; its 🗑 **Delete cache…** removes it after saying what and where —
optionally with the downloaded contexts, which every package on the machine
shares. Both are also in the status bar menu, and Rescan in the SemForge
right-click submenu.

**Sanity: references that point at nothing.** Every artifact names terms the
others are supposed to define, and each link can break without anything
failing — a `sh:path` to an attribute the knowledge no longer declares still
parses and still validates; a SPARQL body reading a removed attribute matches
nothing, which looks exactly like a rule that is satisfied. So the Problems
panel reports each broken link on the line that holds it:

| Finding | Where | Level | Quick fix (💡) |
|---|---|---|---|
| `sh:path` names an undeclared attribute | the `sh:path` line in `shacl.ttl` | error | Declare it · Remove this property shape |
| a data key no knowledge file declares | the key's line in the `.jsonld` | error in a case, info in the scratchpad | Declare it · Remove it from this entity |
| a SPARQL body names an undeclared term of the package's own namespaces | the line inside the query | warning — a query is checked by token, not meaning | Declare it |
| `sh:class` / `sh:targetClass` names an undeclared class | the shape line | error | — |
| an expectation asserts a constraint no shape declares | the `constraint:` line in `expectations.yaml` | error | Remove this assert |
| a declared attribute nothing uses | its declaration in `knowledge.ttl` | info | Delete it… |

**Declare it** opens the New attribute flow with the name and namespace the use
already wrote, so only the type and the kind are asked. **Remove this…** takes
exactly the marked thing and refuses if the file has changed since it was
checked. A file whose last problem is fixed is told so, rather than keeping a
stale squiggle. `semforge test` now says *"a constraint no shape declares"* for
a stale assert instead of *"did not fire"*, and **`semforge check`** reports
the same findings in a terminal — exit 1 on an error (`--strict`: on a warning
too), so a broken link cannot reach CI unnoticed.

**Go to Definition navigates both views**: it reveals and expands the declaring
shape in the tree *and* moves the `.ttl` to the line. Jumping only the editor
would leave you to find the declaring shape in the tree by hand, which is the
work the command exists to remove.

> **There is no override in SHACL.** A constraint declared on `Filter` is
> *conjoined* with the one on `Machine`, not substituted for it — adding
> `hasState minCount 0` to `FilterShape` leaves `MachineShape`'s `minCount 1`
> firing exactly as before. So the action can only tighten, and when the value
> you give would be weaker or identical it says so and offers to open the
> inherited shape instead. To genuinely relax, edit the shape that declares it.

`sh:nodeKind sh:BlankNode` is **not shown on an attribute**. In NGSI-LD an
attribute *is* a blank node carrying `hasValue`/`hasObject`, so stating it
decides nothing — `semforge export` adds it to every forward attribute path,
because a SHACL consumer knows nothing of that convention. Two places it stays
visible, because there it is a real decision: on a **value** (`sh:IRI` for a
relationship target, `sh:Literal` for a plain value), and wherever an attribute
declares something *other* than `BlankNode`, which is a modelling error rather
than boilerplate.

A padlock means shown but not editable here. Connectives (`sh:or`, `sh:node`)
are structure rather than a parameter, and a SPARQL body is not a form. They
appear so the tree does not lie about what the shape contains; edit them in the
`.ttl`.

**The Tests view** (formerly Model) — the second tree in the SemForge container. It shows the
data the constraints judge, in two sections, because they are judged by
different rules:

```
🧪 Tests   6 case(s) · all ok
   ├── test_CartridgeShape          1 case(s) · all ok
   └── test_StateOnCutterShape      2 case(s) · all ok
✎ Main    the scratchpad — violations here are information, not failures
   └── main.jsonld                  the model as shipped
```

**Tests** are the declared cases: each says what it is for, and `semforge test`
passes or fails on it. **Main** is the scratchpad — where you try a violation to
see what a constraint does. It declares nothing and cannot fail a run.

The scratchpad's file is `main.jsonld` (`model-instance.jsonld` still loads —
the kms uses that name), and it may be a directory of documents like any other
role.

The tree shows two different things, and they are not interchangeable. The
cases under `examples/` are the **suite**: each says what it is for and
`semforge test` passes or fails on it. `model-instance` is the **scratchpad** —
where you try a violation to see what a constraint does. It carries no
expectation and cannot fail a run, and each of its documents gets its own root
marked *a scratchpad, not a declared example*.

```
🧪 cutter-processing-with-filter-on.jsonld   good · valid · ok · 3 include(s)
   ├── urn:plasmacutter:1                    Plasmacutter
   └── 🔗 filter-on.jsonld                   included — edit it where it is declared
🧪 cutter-processing-with-filter-off.jsonld  bad · invalid · ok · 3 include(s)
   └── urn:plasmacutter:1                    Plasmacutter · 1 violation(s)   ⛔
🧪 model-instance.jsonld                     the model as shipped — not a declared example
```

A **bad** example that violates is `ok` — violating is its pass condition. One
that stops violating is the failure, which is the regression a negative example
exists to catch.

Entities arriving through `include` are editable where they appear, and the
write goes to the subobject. The tree says how many cases include that file and
the edit asks before changing more than one of them — a decision worth taking
deliberately, but not one worth forbidding.

Under each entity is the data itself, starting with its **type**:

```
model-instance.jsonld            8 entities
├── urn:cutter:1                 Machine · 1 violation(s)     ⛔
│   ├── type                     iffBaseEntities:Machine
│   └── hasState                 base:state_ON · Property     ✎
└── urn:filter:1                 Filter · 1 violation(s)      ⛔
    ├── type                     iffBaseEntities:Filter
    ├── hasCartridge             "urn:cartridge:1" · Relationship  ✎
    └── hasStrength              0.6 · Property · 4 observations   📈
        ├── 0.9   2024-02-28T13:52:32.000Z · superseded
        ├── 0.8   2024-02-28T13:52:33.000Z · superseded
        ├── 0.7   2024-02-28T13:52:34.000Z · superseded
        └── 0.6   2024-02-28T13:52:35.000Z · current
```

The type is also the entity row's description, but a description is grey and
truncated in a narrow panel — and the type is the most load-bearing field an
NGSI-LD entity has, since it decides which shapes judge it at all. So it gets a
row. It is read-only here: changing a type is not an edit to one value, because
every shape that targeted the old type stops applying.

**An id is not an address; the file is the rest of it.** The same
`urn:filter:1` appears in four files — "the filter, switched off" is written as a
second one, and each case is validated on its own — so every row that names an
entity shows its path, and nothing is flagged for the reuse. Hover an entity row
to see which file it was read from.

Three things *are* errors, reported on the `.jsonld` file and line and failing
`semforge test`:

| Case | Why |
|---|---|
| the same id twice in one file | one entity carrying the attributes of both, and no path can tell them apart |
| the same id in a case *and* one of its includes | the files are parsed into one graph, so the definitions **merge** — an include saying `hasState ON` and a case saying `OFF` produce an entity with both. There is no override; vary an entity by including a different subobject |
| an entity with no `@context` | `id` and `type` are ordinary keys until a context maps them, so it expands to a blank node, no `sh:targetClass` matches, and the case passes having validated nothing |
| a relationship pointing at an entity the case does not define | in a case the composition is the whole world, so nothing about the target gets checked and the case passes having tested less than it says. This is what a half-finished rename leaves behind: change an id in a subobject and the filters pointing at it go nowhere, while the verdict moves somewhere unrelated |

Those are the only diagnostics this extension puts anywhere but `shacl.ttl`.

**Instances are grouped by `datasetId`.** That is not cosmetic: an NGSI-LD
attribute is identified by `(entity, name, datasetId)`, so several instances
sharing one are the *same* attribute observed repeatedly, while different
`datasetId`s are *different* attributes that happen to share a name. The dedup
resolves within a `datasetId` and never across, and a flat list hides that.

With one `datasetId` the series hangs straight off the attribute. With several,
each gets its own row showing its own current value:

```
hasStrength                       2 datasets
├── 0.6    @none · Property · 4 observations        📈
└── 1.5    urn:sensor:B · Property · 2 observations 📈
```

**Anything carrying a value carries the pencil** — including the value of an
attribute with sub-attributes, which does not fold onto the attribute row: the
row beneath it is where the value lives. **Add Observation** appears only on a
row that stands for a `datasetId`, since that is what a series belongs to. The
only rows without a pencil are rows with no value of their own, and they say so
on hover.

**Rows from an included subobject are editable too.** They are ordinary JSON-LD
files and the edit lands in the file the row came from. What is worth knowing is
the reach: `workpiece-steel.jsonld` is included by three cases, so changing its
height moves three verdicts. Those rows say `shared by 3 cases` and the edit
asks once, listing them, before writing. A file only one case includes asks
nothing.

A row with the 📈 icon takes **Add Observation** (right-click). It asks for the
value and an `observedAt`, joins the series for *its* `datasetId`, and copies
the `type` from what is already there — a Property whose new instance arrived
as a Relationship would be a different attribute, not a new observation of the
same one. A `datasetId` of `@none` is not written out: that *is* the default
instance, and stating it would mean something else.

**Building NGSI-LD, legally.** Right-click an example for **Add Entity**, or an
entity for **Add Attribute**. An attribute is not free-form JSON — its `type`
decides which key carries the payload:

| type | key | payload |
|---|---|---|
| `Property` | `value` | a literal, or `{"@id": …}` for a vocabulary term |
| `Relationship` | `object` | an entity IRI, never a literal |
| `GeoProperty` | `value` | GeoJSON |
| `JsonProperty` | `json` | arbitrary JSON, opaque to the graph |
| `ListProperty` | `valueList` | an ordered list |

The type is read **from the shapes** by default — a value shape on
`ngsild:hasObject` means Relationship, one on `hasValue` means Property — so you
are not asked something the model already knows. A pairing that cannot mean
anything is refused rather than written: this repo has already lost time to
`{"object": …}` where the model said Property, which made a SPARQL rule's join
predicate refuse the row silently while every test stayed green.

Each attribute row carries a **⚖ icon: the SHACL rule for this attribute**. It
opens `shacl.ttl` at the `sh:property` block that judges this datum — including
when that block is on a supertype, which is where it is hardest to find by hand
(`hasState` on a `Filter` is `MachineShape`'s, and the status bar says so).
**If nothing constrains the attribute it offers to write an empty
`sh:property`** for it, so there is somewhere to add constraints. That stub
deliberately constrains nothing yet, and the capability check reports it as
compiling to nothing until you add a parameter — a property shape that asserts
nothing is a visible TODO, not a finished shape.

Editing a value **offers what the shape allows**. Where the value's shape
declares `sh:class`, the picker lists the individuals of that class — and for a
relationship, the entity ids of that type — spelled the way the file needs them
(`{"@id": "base:state_ON"}` for a Property with an IRI value, a bare IRI for a
Relationship). This is a different question from the `sh:class` picker in the
Types view: that one asks what the *constraint* may say, this one what the
*datum* may be. **Enter a different value…** stays at the bottom.

Otherwise the input parses JSON, so `42` is a number and
`{"@id": "…"}` a node reference — typing an IRI into a Property should not
quietly produce the string form. The file is rewritten with a one-line diff and
both trees re-validate, which is the reason to edit here rather than in the
JSON: you see the verdict move.

**`current` and `superseded` are worth knowing about.** An attribute resolves to
its latest `observedAt` per `datasetId` before validation, so editing a
superseded observation changes the file and nothing else. Without the marker
that reads as the editor being broken.

An entity that violates something is marked, and carries the message on hover —
a `minCount` violation is about an attribute that is *not there*, so there is no
attribute node to hang it on.

**The Vocabulary view** — the third tree, and the third ingredient. Shapes say
what must hold, examples are what holds; neither says what the model *is*.

```
📚 Entity types                        9 type(s) under Entity
└── iffBaseEntities:Entity
    ├── iffBaseEntities:Consumable
    │   ├── iffBaseEntities:FilterCartridge  CartridgeShape + 4 more · 3 instance(s)
    │   └── iffBaseEntities:Workpiece        WorkpieceShape · 4 instance(s)
    └── iffBaseEntities:Machine              MachineShape · 1 instance(s)
        ├── iffBaseEntities:Cutter           CutterShape · 1 instance(s)
        │   ├── iffBaseEntities:Plasmacutter 3 instance(s) · checked by an inherited shape
        │   └── iffBaseEntities:Lasercutter  checked by an inherited shape
        └── iffBaseEntities:Filter           FilterShape + 2 more · 7 instance(s)
📚 Vocabulary classes                  14 class(es)
└── base:MachineState                  7 member(s) · used by 1 constraint(s)
    ├── state_ON          ON · used in 7 place(s)
    ├── state_OFF         OFF · used in 1 place(s)
    └── ⚠ state_CLEANING  CLEANING · unused
```

What it adds over reading `knowledge.ttl` is the **joins** — the places where
the three ingredients meet, which is where authoring goes wrong and where
nothing reports today:

| Row says | Meaning |
|---|---|
| `FilterShape + 2 more` | which shapes judge instances of this class. The ⚖ icon opens the shape |
| `checked by an inherited shape` | no shape of its own, but `sh:targetClass` reaches subclasses — `CutterShape` judges a `Plasmacutter` |
| ⚠ `no shape` | nothing targets this type or anything above it, so nothing about it is ever checked |
| `7 instance(s)` | how many examples instantiate it, counted across every suite — not only `model-instance.jsonld`. **Clicking one opens it and shows it in the Model tree** |
| `used in 7 place(s)` | an example gives this term as a value. Expand for which entity, attribute and file — **clicking one opens that file at that attribute and shows the entity in the Model tree** |
| ⚠ `unused` | no case gives this value, so nothing exercises the constraint that allows it |
| ⚠ `no members` | a shape uses this class as `sh:class` and it has no individuals: no value can ever satisfy it |

The flags are narrow on purpose. `unused` is shown only for a vocabulary some
shape actually draws values from — a `Binding` or a `ChemicalElement` is not
something an NGSI-LD example is meant to mention, and colouring those would
turn the tree yellow and bury the real gap. `no members` is likewise only for a
vocabulary class: an entity class under `sh:class` is the *range of a
relationship*, and its instances live in the data rather than in
`knowledge.ttl`. An abstract root — subclasses, no instances — is not expected
to have a shape of its own and is not flagged.

Selecting a class or a member moves `knowledge.ttl` to its declaration.

Selecting a row that names an entity — an **instance** ("this class is
instantiated here") or a **usage** ("this term is given as a value there") —
does both halves of showing it: the `.jsonld` opens at the entity, or at the
attribute that gives the term, and the entity's row is revealed in the Examples
tree, where its verdicts and its other attributes are. The same entity id appears in a good
case and a bad one, so each file gets its own row rather than one row guessing
which you meant.

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
`model-instance.jsonld` — or one holding `semforge.yaml`, which declares itself
one. Opening any file inside one activates the service, which walks up to find
the root — an editor hands you a file, not a project. The command line walks up
by the same rule, in the same code (`semforge.package.discover`), so the editor
and CI cannot disagree about which package a file belongs to.

Analysis runs on open and on save, over the whole package, because a constraint
in `shacl.ttl` is meaningless without the ontology and the examples.

---

## Commands

| Command | What it does |
|---|---|
| `SemForge: Restart Language Server` | after changing `semforge.pythonPath`, or if the server dies |
| `SemForge: Revalidate Package` | saves the active file, which re-runs analysis |
| `SemForge: New project…` | creates a project folder and scaffolds it, then offers to open it |
| `SemForge: Create a package in this folder` | scaffolds a directory you already have |
| `SemForge: Menu` | everything below, from the status bar item |
| `SemForge: Select Package` | which package the views show; pins your choice |
| `SemForge: Change this setting` | the ✎ on a Project row; writes one line of semforge.yaml |
| `SemForge: Define a namespace prefix` | the ➕ on the Package view's namespaces row |
| `SemForge: Remove this namespace prefix` | the 🗑 on a name; refused while anything uses it |
| `SemForge: Doctor` | what it sees: folder, interpreter, active package, every other package in the window, whether `semforge` imports |
| `SemForge: Go to the SHACL rule for this attribute` | the ⚖ icon on an example attribute; creates an empty `sh:property` when none exists |
| `SemForge: Go to the shape for this class` | the ⚖ icon on a knowledge class |
| `SemForge: Add an entity` | the + on a case or file; the type is picked from the knowledge, never typed |
| `SemForge: Add an attribute` | the + on an entity; the attribute is picked from the knowledge, filtered by `rdfs:domain` |
| `SemForge: New attribute…` | declares an attribute in the knowledge, then (optionally) constrains it on its type's own shape — one flow, from the palette, the status bar menu, the SemForge submenu on a `.ttl`/`.jsonld`, or the Constraints/Vocabulary view title |
| `SemForge: Rescan (ignore the cache)` | throws away everything known about the package and analyses it from scratch; also the 🔄 on the Package view's Cache row |
| `SemForge: Delete cache…` | removes the package's cache (optionally the downloaded JSON-LD contexts too), after saying what and where; also the 🗑 on the Cache row |
| `SemForge: Delete attribute…` | right-click an attribute in the Knowledge or Types view (or the palette, status bar menu, SemForge submenu); shows every dependent first and removes them all, or names what must be edited by hand |
| `SemForge: Add Attribute to Shape` | the + on a shape in the Types view; writes both NGSI-LD layers, optional or required, with the value's class or datatype |

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `semforge.pythonPath` | `""` | Interpreter with `semforge` importable. Empty means look for `venv/bin/python`, then `python3`. |
| `semforge.trace.server` | `off` | LSP message tracing, for debugging the extension itself. |

---

## Limits worth knowing

- **Violations are attributed to the shape, not to the entity.** They land on
  `shacl.ttl`, against the constraint you are editing. Entity-identity findings
  are the exception and land on the `.jsonld` line, now that a JSON position
  index exists; mapping every violation back to its entity is still not done.
- **Cooked editing covers Core parameters only** — cardinality, datatype,
  class, nodeKind, ranges, lengths, pattern. That is deliberate rather than
  partial: those are the constraints that honestly fit one name and one scalar
  value. Connectives and SPARQL bodies are shown and locked.
- **Adding constraints is half-wired.** You can change and remove what a shape
  declares, and the ⚖ icon on an example attribute will create an *empty*
  `sh:property` for an unconstrained attribute — but filling it in is still a
  `.ttl` edit. There is no "add a parameter" command yet.
- **The Vocabulary view is read-only.** It shows the ontology and the joins; a
  new class or member is a `knowledge.ttl` edit.
- **`instance(s)` and `used in` count the examples, not the world.** They say
  what the suite exercises. A term no case uses may still be perfectly valid —
  that is why those rows are flagged as warnings and only where a shape draws
  from them.
- **Analysis is whole-package on every save.** Fine at KMS scale (about a second);
  the incremental path exists in the plan and is not wired up.
