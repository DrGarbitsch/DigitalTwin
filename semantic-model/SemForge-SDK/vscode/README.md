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

### 3. Check it is alive

Open any `.ttl` in a directory that also holds `knowledge.ttl` and
`model-instance.jsonld`. Within a second or two the Problems panel should fill.
On the shipped KMS you should see roughly:

```
shacl.ttl:160  warning  3 violation(s) here: MinCountConstraintComponent(hasXXXWorkpiece) …
shacl.ttl:14   info     7 constraint(s) here have no example that makes them fire …
```

If nothing appears, open **Output → SemForge** in the dropdown for the server
log. The usual causes:

| Symptom | Cause |
|---|---|
| F5 offers a debugger list | the open folder is not `vscode/`; see method A |
| Output says `No module named semforge` | the interpreter has no SDK — run `make setup`, or set `semforge.pythonPath` |
| No Problems at all, no output channel | the file is not inside a package: its directory needs `knowledge.ttl`, `shacl.ttl` and `model-instance.jsonld` alongside |

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
- **Editing is raw.** This is raw mode in the sense of `manifest.md` §2.2. The
  cooked view — navigating entity types and editing constraints through a
  structured UI — is not built; the SDK has the write layer it needs
  (`semforge.rdfio`), but no UI uses it yet.
- **Analysis is whole-package on every save.** Fine at KMS scale (about a second);
  the incremental path exists in the plan and is not wired up.
