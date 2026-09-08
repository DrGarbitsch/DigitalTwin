# Knowledge, Models, Shapes (KMS)

The default knowledge base of the platform: `knowledge.ttl` (ontology facts),
`shacl.ttl` (constraints and SPARQL rules), and `model-instance.jsonld`
(example entities; `model-instance.scorpio.jsonld` is the variant with one
attribute instance per datasetId that Scorpio's batch upsert accepts).

## Conventions

### Timestamps

Every timestamp carried as a **property value** uses ISO 8601 UTC with
millisecond precision and the `Z` suffix:

```
YYYY-MM-DDTHH:mm:ss.SSSZ        e.g. 2024-02-27T13:54:55.400Z
```

This is the same representation NGSI-LD prescribes for `observedAt`, so one
format flows from model to TSDB to writeback. The form is fixed-width, which
makes lexical order equal chronological order — SPARQL rules may compare two
timestamps directly (`FILTER(?ts1 > ?ts2)`), and `xsd:dateTime(?v)`
normalizes a value into this canonical form for such comparisons. Rules that
copy an attribute's `ngsild:observedAt` into a property value emit this form
as well.

Do not write epoch numbers into time-valued properties: they are ambiguous
(seconds vs milliseconds), untyped, and the two SQL dialects the pipeline
compiles to do not even share an epoch for their internal conversions.
Millisecond arithmetic remains available inside rule expressions — arithmetic
on time variables converts to milliseconds automatically.


## Prefixes

Every namespace has exactly one name, and `context.jsonld` is where the name is
agreed. `semforge prefixes .` checks it; `--fix` aligns the Turtle artifacts.

This was not always so. `:` denoted `base_shacl/` in `shacl.ttl` and
`base_entities/` in `knowledge.ttl`, and `default1:` denoted `filter_shacl/` and
`base_knowledge/` respectively -- so a term copied between the two files changed
meaning silently. The `default1..5` names came from `make ontology2kms` merging
modules with `rdfpipe`, which invents a name when the source supplies none.

`semforge.yaml` declares the four namespaces the context does not: the two
shapes namespaces, the test bindings, and NGSI-LD itself.

### One decision is still open, and it is not the one it looked like

`shacl.ttl` calls `base_knowledge/` **`iffBaseKnowledge`**; the context calls it
**`base`**, and `model-instance.jsonld` writes `base:state_ON` through it.

The obvious fix -- declare `iffBaseKnowledge` in the context *alongside* `base`,
two names for one namespace, nothing written against `base` breaks -- **does not
work, and was tried.** Two things stop it:

* rdflib binds **one prefix per namespace**. The second name evicts the first,
  so adding `iffBaseKnowledge` removes `base` from every rdflib consumer.
* `shacl2flink/create_sql_checks_from_shacl.py` reads the context through rdflib
  and requires the surviving name to be literally `base`:
  *"No prefix 'base:' is found in your given context. This is needed!"*

Publishing that addition would therefore have stopped the compiler for
everyone. `context.jsonld` here is byte-identical to what is published, and
`test_two_names_for_one_namespace_do_not_survive_rdflib` pins the mechanism.

So the real choice is between two single names:

* **keep `base`** -- align `shacl.ttl` to it (`semforge prefixes --fix` after
  dropping the override in `semforge.yaml`). Costs nothing, and leaves the
  Turtle prefix saying `base:` while the SPARQL bodies inside it say
  `iffBaseKnowledge:`, since those declare their own and are a separate scope.
* **move to `iffBaseKnowledge`** -- publish it *instead of* `base`, update the
  model's five values, and remove the hardcoded prefix name from
  `create_sql_checks_from_shacl.py`. More work, and it removes a real wart: a
  compiler that requires one specific prefix spelling is fragile whatever the
  spelling is.

`semforge prefixes` reports the divergence until it is settled.

The gate was tested against the real model: switching the five values to
`iffBaseKnowledge:` while the published context lacked the term left
`create_ngsild_models.py` emitting `'iffBaseKnowledge:state_ON'` as a plain
string, with no IRI anywhere in the output -- so `sh:class` would match nothing
and the SPARQL rules comparing `?v = iffBaseKnowledge:state_ON` would silently
never fire. `semforge export` refuses to write in that state (`SF-CTX-002`).

### The local/published split

`semforge.yaml` declares both:

```yaml
context:
  local: context.jsonld
  published: https://industryfusion.github.io/contexts/staging/example/v0.2/context.jsonld
```

The model on disk keeps naming the **published** url -- it must, or it is
useless to anyone who resolves that url themselves. Loading substitutes the
**local** file's content in memory, so work here never depends on the network
and a term is usable as soon as it is agreed locally.

`semforge export` points the exported model back at the published url, and
checks first: any term the model uses that the published context does not
declare is an **error**, and nothing is written. That is the moment the split
has to be paid for, and the only moment anybody can act on it.

`semforge retarget --to local` is the other direction, for a model imported from
somewhere else.
