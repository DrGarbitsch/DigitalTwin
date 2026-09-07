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

**M0, M1 and M2 are implemented** (see `implementation-plan.md` section 5).
A package loads, is projected to RDF, is normalised into the data view its
shapes declare, and is validated with pyshacl. Every applicable constraint gets
a status, residue is pinned by digest, and coverage reports which constraints
are actually exercised.

On the real KMS: 89 constraints evaluated, 86 conformant, 3 violated — all
three known and documented.

```bash
venv/bin/python -m semforge validate tests/corpus/kms
venv/bin/python -m semforge test tests/corpus/kms --coverage
venv/bin/python -m semforge accept tests/corpus/kms
```

What is **not** yet true, stated rather than implied:

- Constraints are referenced structurally (`shape/attribute/Component`), not by
  a declared frozen `semforge:id`. A structural reference changes when the path
  changes, which is the rename a regression report exists to explain
  (`architecture.md` section 5.4). Declared IDs land with the write layer.
- No provenance, rules fixpoint, export, diff or editor service. M3–M6.

## Scope

SemForge validates offline. It does not model Flink, Kafka, streaming state or
the alert projection, and making pyshacl agree with the compiled SQL is not its
job — see `architecture.md` section 7.4.
