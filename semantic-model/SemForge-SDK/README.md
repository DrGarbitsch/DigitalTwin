# SemForge SDK

Offline authoring and validation of semantic packages: NGSI-LD examples, OWL
ontology, SHACL constraints and SHACL-SPARQL rules, developed and tested
together as one versioned unit.

- [`manifest.md`](./manifest.md) — what SemForge must be, and why
- [`architecture.md`](./architecture.md) — how it is built
- [`implementation-plan.md`](./implementation-plan.md) — how it gets built, in what order

## Quick start

```bash
make setup                          # venv + pinned dependencies
make test                           # pytest, 80% coverage gate
make lint                           # flake8
venv/bin/python -m semforge validate tests/corpus/kms
```

## Status

**M0 and M1 are implemented** (see `implementation-plan.md` section 5): a
package loads, is projected to RDF, is normalised into the data view its shapes
declare, and is validated with pyshacl. `semforge validate` runs against the
real KMS.

What is **not** yet true, and is stated rather than implied:

- A report carries **violations only**. Establishing which constraints were
  evaluated and *conformed* needs the applicable-set enumerator (H1), which is
  M2 — a SHACL engine reports only violations, so conformance is the absence of
  a result. `Report.complete` is `False` and the CLI says so, because a list of
  three violations would otherwise read as "everything else passed", which is
  the silence invariant V1 exists to forbid.
- No expectations, residue, coverage, provenance, rules fixpoint, export or
  diff. Those are M2–M5.

## Scope

SemForge validates offline. It does not model Flink, Kafka, streaming state or
the alert projection, and making pyshacl agree with the compiled SQL is not its
job — see `architecture.md` section 7.4.
