# Digital Twin Shacl to Flink Transformation

This directory contains the translation mechanism from SHACL basee constraints and rules to SQL/Flink.
There are always three ingredients to such a translation, called KMS (Knowledge, Model-instance, SHACL)

- **K**nowledge contains OWL/RDF data, preferable serialized in Turtle
- **M**odel-instance describes the actual instances/objects of the setup. These are described in JSON-LD/NGSI-LD.
- **S**HACL is the W3C standard describing the constraints and rules for the model with respect to the Knowledge.

A first [overview](../datamodel/README.md) and [tutorial](../datamodel/Tutorial.md) can be found in the [datamodel](../datamodel/) directory.

# Table of Contents

1. [Quick Setup](#quick-setup)
2. [KMS Examples & Tutorial](./docs/examples.md)
3. [Supported SHACL Features](./docs/supported-features.md)
4. User Defined Functions
3. [Build and test KMS](#build-and-test-kms)
4. [Deploy Flink-Jobs](#deploy-flink-jobs)
5. [References](#references)

# Quick Setup

## Requirements

- You need to have Python > 3.8
- Virtualenv needs to be installed
- `sqlite3` and `sqlite3-pcre` need to be installed

  ```bash
  sudo  apt install sqlite3 libsqlite3-dev libpcre2-dev
  ```

## Installation

If miniconda installed with python3.10 environment (using prepare-platform.sh), move to step 2 else use below script to install and create python env
### Step 1 :
```bash
bash pyenv_setup.sh
source ./miniconda3/bin/activate
conda create -n py310 python=3.10 -y
```
### Step 2 :
Everytime you are starting a new shell you need to enable the miniconda Virtual Environment which runs python 3.10 sourcing miniconda installation path:

```bash
source ./miniconda3/bin/activate
conda activate py310
make setup
```

## VS Code

Normally VS Code should recognize the virtual environment and ask you if you want to use the virtual environment as you Python interpreter.
If not you can do it manually.
Press `Ctrl + Shift + p` and type `Python: Select Interpreter` and select the virtual environment in the _venv/_ folder.

## Development

Install the development dependencies:

```bash
source ./miniconda3/bin/activate
conda activate py310
pip install -r requirements-dev.txt
```

### Unittests

Run with

```bash
make test
```
## Linting

Run with

```bash
make lint
```


# Build and Test KMS
## Build KMS directory

There are three files expected in the `../kms` directory:

- shacl.ttl
- knowledge.ttl
- model-instance.ttl

To build:

```bash
make build
```

As a result, there must be a new directory `output` with the following files included:

- **core.yaml** - SQL-Tables for Flink (Core tables are used independent of concrete SHACL rules)
- **core.sqlite** - SQL-Tables for SQLite (Core tables are used independent of concrete SHACL rules)
- **shacl-validation.yaml** - From SHACL compiled SQL scripts for Flink
- **shacl-validation.sqlite** - From SHACL compiled SQL scripts for SQLite
- **shacl-validation-maps.yaml** - Additional SQL scripts when result is too large to store in  **shacl-validation.sqlite** directly
- **rdf.sqlite** - Knowledge translated to RDF triples for SQLite
- **rdf.yaml** - Knowledge translated to RDF triples for Flink
- **ngsild-kafka.yaml** - Kafka topics used by Flink
- **ngsild-models.sqlite** - translated model-instance.ttl for SQLite (only for SQLite needed)
- **ngsild.sqlite** - SQL tables for the concrete SHACL rules generated for SQLite
- **ngsild.yaml** - SQL tables for the concrete SHACL rules generated for Flink
- **rdf-kafka.yaml** - Kafka topic for rdf data
- **rdf-maps.yaml** - RDF data add-on when data is too much to fit into **rdf.yaml**
- **udf.yaml** - User Defined Functions (UDF) for Flink SQL


## Test locally with SQLite

```bash
make test-sqlite
```

# Deploy Flink Jobs

## Deploy SHACL rules to Flink

```bash
make flink-deploy
```

## Undeploy SHACL rules to Flink

```bash
make flink-undeploy
```

## A deleted entity only clears its alert inside the state ttl window

Deleting an entity retracts its alerts only while the state that produced the
verdict still exists. Once `table.exec.state.ttl` has expired it, the operator
no longer knows it ever reported a violation, so the deletion produces no
retraction: `constraint_trigger_table` keeps the stale verdict, nothing
recomputes a verdict for an entity that is no longer there, and the alert stays
open in Alerta for good. Nothing in the logs marks this, and a stale alert
looks exactly like a live one.

Measured against the deployed 3600 s ttl: an entity deleted immediately clears
in about five seconds; the same entity deleted after 70 minutes does not clear
at all. The boundary follows the setting rather than the elapsed time -- at
`table.exec.state.ttl = 300 s` a 60 s soak clears and a 420 s soak does not,
and with the ttl disabled entirely that same 420 s soak clears again.

To see it on a running cluster in about a quarter of an hour:

```bash
tools/ttl_retraction_repro.sh [namespace]
```

It shrinks the ttl, runs one cycle on each side of it, and restores the
original setting on the way out. Raising the ttl moves the boundary but does
not remove it: alerta remembers alerts indefinitely while flink's state does
not, so any finite ttl eventually drops a retraction.

# References

[RDF] RDF
[RDFS] RDFS
[TURTLE] TURTLE
[OWL] OWL
[SHACL] SHACL
[JSONLD] JSON-LD
[XSD] XSD
[SPARQL]
