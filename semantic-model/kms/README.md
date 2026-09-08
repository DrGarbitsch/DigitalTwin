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

### One step is still outstanding, and it is upstream

`context.jsonld` here now declares **`iffBaseKnowledge`** alongside `base` --
same namespace, two names, `base` kept so nothing written against it breaks.

**That change has to be published** at
`https://industryfusion.github.io/contexts/staging/example/v0.2/context.jsonld`,
which lives in the `industryfusion.github.io` repository, not this one. The file
in this directory is the proposed content: publishing it is a four-line
addition.

Only afterwards should `model-instance.jsonld` switch its five `base:state_ON`
values to `iffBaseKnowledge:state_ON`. The model resolves prefixes through the
context it names -- the *remote* one -- so renaming the data first leaves those
values unexpanded: a plain string where an IRI was meant, which `sh:class` then
correctly refuses. `semforge prefixes` reports the pending rename (`SF-PFX-004`)
until both halves are done.
