# Concept: BGP templates for SHACL-SPARQL constraints

## 1. The problem, measured

`sh:sparql` constraints are compiled one SQL statement per constraint
(`lib/shacl_sparql_to_sql.py`), while SHACL core constraints are *interpreted*: a
fixed set of statements joined against `constraint_table`, whose rows carry the
shape parameters (`lib/shacl_properties_to_sql.py`). The first is linear in the
number of constraints, the second is constant.

The following numbers are Flink physical operator counts from the real planner
(Flink 1.17.2) over the actually generated `output/shacl-validation-maps.yaml`,
with source tables swapped for `datagen`/`blackhole` so the plan can be built
without a cluster, and `STATE_TTL` hints stripped (a 1.18+ hint that affects
state retention, not graph shape). Counts exclude `Reused(...)` references, so
sub-plan reuse across statements is already accounted for.

Numbers below are for `semantic-model/kms/shacl.ttl` at commit `a2e784f`,
reproducible with `python debug/count_flink_operators.py --marginal`.

| statement set | operators |
| --- | --- |
| whole validation job (11 statements) | **542** |
| core SHACL only (7 statements, 43 `constraint_table` rows) | **427** |
| the 4 `sh:sparql` constraints | **115** |

Marginal cost of each compiled SPARQL constraint (removed from the full set):

| constraint | operators |
| --- | --- |
| `FilterStrengthShape` (nested `IF`/`BIND`) | 36 |
| `StateValueShape` (`FILTER NOT EXISTS`) | 27 |
| `StateOnCutterShape` (one relationship hop) | 24 |
| `StateOnFilterShape` (one reverse hop) | 22 |

Two numbers matter here. The interpreter delivers **43 constraints in 427
operators** — about 10 per constraint and falling, because the statement count
is fixed. Compilation delivers **4 constraints in 115 operators** — about 29
per constraint, and that figure does not fall. Had those 43 core constraints
been compiled individually at the same rate, the job would be roughly 1250
operators instead of 427.

## 2. What the template approach buys

A *template* is one SQL statement whose join graph is fixed and whose constants
are joined in from a parameter table. It is exactly the mechanism
`constraint_table` already uses — `B.name = D.propertyPath` in
`sql_check_relationship_base` (`lib/shacl_properties_to_sql.py:144`) is a
runtime-bound predicate, running in production today — applied to the join
shapes that SPARQL constraints use.

Measured, against the same core baseline of 427:

| variant | operators added |
| --- | --- |
| 2 compiled state-mismatch constraints | **+52** |
| 1 template, one forward hop | +23 |
| 1 template, one reverse hop | +23 |
| 2 templates (forward + reverse), same coverage | **+33** |
| 1 template, no hop (flat attribute test) | +12 |
| 1 template, two hops | +29 |
| 1 template, parameters read from the `rdf` triple table | **+47** |

Three conclusions:

1. **The template is already cheaper at N = 2** (33 vs 52), and it is *flat*:
   constraint number three of the same shape costs zero operators, because it
   is a row, not a statement.
2. **Templates share.** Two templates cost 33, not 46, because the planner
   reuses the parameter-table scan and the entity/attribute scans between them.
3. **The parameter store must be a wide, flat table.** Reading the same
   parameters out of the generic `rdf` triple table costs one self-join per
   parameter slot and lands at +47 — almost exactly the cost of just compiling
   both queries. This kills the otherwise attractive idea of storing template
   parameters as plain RDF and letting them be picked up from the existing
   `rdf` table.

### Scaling

With compiled cost ≈ 26 operators per one-hop constraint and a fixed 33 for the
two templates that cover the same shapes:

| constraints of that shape | compiled | templated | saved |
| --- | --- | --- | --- |
| 2 | 52 | 33 | 19 (37%) |
| 5 | 130 | 33 | 97 (75%) |
| 10 | 260 | 33 | 227 (87%) |
| 20 | 520 | 33 | 487 (94%) |
| 50 | 1300 | 33 | 1267 (97%) |

In whole-job terms: at 20 SPARQL constraints the validation job is ~950
operators compiled versus ~460 templated. The job roughly halves, and the
configmap-splitting pressure (`configs.max_sql_configmap_size`) falls with it.

## 3. Architecture

Four pieces.

### 3.1 Template catalogue

A template is declared as a SPARQL query with two parts: a *parameter BGP* that
binds the slots, and an *instance BGP* over NGSI-LD data that uses them.

```sparql
SELECT ?this ?constraintId ?severity ?message
WHERE {
  # parameter BGP - one solution per constraint using this template
  ?constraintId  tpl:targetClass ?tc ;
                 tpl:selfAttr    ?selfAttr ;
                 tpl:selfValue   ?selfValue ;
                 tpl:relPath     ?rel ;
                 tpl:otherAttr   ?otherAttr ;
                 tpl:otherValue  ?otherValue ;
                 tpl:severity    ?severity ;
                 tpl:message     ?message .

  # instance BGP - fixed join graph, parameterised constants
  ?this a ?tc .
  ?this ?selfAttr  [ ngsild:hasValue  ?v1 ] .
  ?this ?rel       [ ngsild:hasObject ?other ] .
  ?other ?otherAttr [ ngsild:hasValue ?v2 ] .
  FILTER(?v1 = ?selfValue && ?v2 != ?otherValue)
}
```

This compiles through the existing `translate_sparql` path, so the template
library is written in the same language the shapes are written in and stays
testable in rdflib against the same fixtures the SQLite harness uses.

### 3.2 Parameter table

One wide table per template (or one shared wide table with nullable slots),
Kafka-backed like `constraint_table`, populated at build time. Per §2 this must
*not* be the `rdf` triple table.

The subclass closure is expanded into rows at build time, exactly as
`sparql_get_all_properties` already does with `?inheritedTargetclass`. This
removes the runtime `rdf` join for `rdfs:subClassOf` that every compiled SPARQL
constraint currently carries.

### 3.3 Classifier

At build time, parse each `sh:sparql` constraint (already done), canonicalise
its algebra tree, and test it against each template's instance BGP modulo
constants. On a match, emit a parameter row. On no match, fall back to today's
per-query compilation.

The fallback is what makes this safe: an unrecognised query produces a larger
job, never a wrong or missing answer. Note this is strictly better than the
current `MAX_SUBPROPERTY_DEPTH` behaviour, which prints a warning and *skips*
the constraint (`lib/shacl_properties_to_sql.py:1127` and `:1166`).

### 3.4 Circuit integration

Templates emit into `constraint_trigger_table` with a `constraint_id`, not into
`alerts_bulk`. The existing `PUBLISH` step then does alerting, and SPARQL
constraints become composable with `sh:and`/`sh:or`/`sh:not` for free. This is
worth doing on its own, before any template work: it also removes the redundant
per-query `LEFT JOIN` against `<targetclass>_view` that
`lib/shacl_sparql_to_sql.py:68` performs, since the circuit already joins the
focus-node universe once for everybody.

## 4. What may and may not be a parameter

This is the load-bearing rule, and it follows directly from §2.

**May be a parameter** (does not change the join graph):

- attribute and relationship IRIs appearing in equi-join conditions
- target class
- literal operands of filters
- severity, message, constraint id

**May not be a parameter** (changes the join graph — make it a new template):

- hop direction. Forward and reverse hops are different join graphs; measured
  as two templates at +33 together. Expressing direction as a parameter would
  require a disjunctive join condition, which Flink can only execute as a
  cross-product.
- number of hops
- optionality (`OPTIONAL`, `NOT EXISTS`)
- the comparison operator — SPARQL has no variable operator in `FILTER`, so
  the operator is part of template identity

## 5. Compiler work required

The one genuine blocker: variable predicates in NGSI-LD position are not
supported. `lib/bgp_translation_utils.py:396` bakes the predicate in twice —
once into the SQL alias, once into the join literal (the latter at `:403`,
`:422` and `:445`, for the property, relationship-forward and
relationship-reverse cases):

```python
attribute_sqltable = utils.camelcase_to_snake_case(utils.strip_class(p))
attribute_tablename = f'{subject_varname.upper()}{attribute_sqltable.upper()}TABLE'
...
join_condition = f"{attribute_tablename}.name = '{p}' and ..."
```

`p` becomes both the literal in the join and the SQL table alias, so
`?this ?rel [ngsild:hasValue ?v]` cannot compile. Required changes:

1. derive the alias from the triple's position rather than the predicate name;
2. emit `name = <paramtable>.<slot>` instead of a literal;
3. give `sort_triples` and `create_ngsild_mappings` a path for the unbound
   case — both currently branch on the predicate constant to decide property
   vs. relationship. Simplest fix: require the template to declare which,
   rather than infer it from the shapes graph.

Optional but valuable: inject a build-time `name IN (...)` list alongside the
variable join. The parameter values are known when the SQL is generated, so
this restores source-level pushdown without giving up the shared plan. It costs
the ability to add constraints without regenerating, which is not a property
the system has today anyway.

Watch `sort_triples`: it orders joins by boundness to keep intermediate results
small, and a variable predicate gives the heuristic less to work with. If the
generic query plans badly, pin the order in the template.

## 6. Extensibility

Yes — the catalogue should be user-extensible, with three guard rails that the
numbers above make non-negotiable.

**Pay per use.** Every declared template costs 12–33 operators *whether or not
any constraint uses it*. Emit a template's SQL only when at least one parameter
row exists. Without this, a shipped catalogue of 20 community patterns costs
~500 operators on a deployment that uses three of them.

**Validate on registration.** The build must reject or warn on a template whose
declared parameter slots appear anywhere that changes the join graph (§4). This
is a syntactic check on the parsed algebra, not a judgement call. Without it,
the first contributed pattern that parameterises hop direction silently
reintroduces a cross-product.

**Report coverage.** The build should print how many constraints matched each
template and how many fell back to compilation, with the operator cost of each.
That is the number that tells a user whether their own pattern earned its
place, and it turns "should we add this template?" into an arithmetic question.

A template descriptor then needs: a name, the SPARQL text, the parameter slot
list with types, and the target `constraint_trigger_table` projection. Nothing
about it needs to be built into `shacl2flink` itself — it can live in a
directory scanned at build time, alongside the shapes.

## 7. Recommended order

1. Route `sh:sparql` output into `constraint_trigger_table` as circuit leaves.
   Independent of everything else, removes N universe joins, gains circuit
   composability. Measure the job before and after.
2. Prototype variable-predicate support in `process_ngsild_spo`. Success
   criterion: hand-write the forward-hop template, parameterise it, and
   reproduce `StateOnCutterShape`'s results in the SQLite harness.
3. Build the classifier and run it over `kms/shacl.ttl`, the opcua validation
   shapes and `tests/sql-tests/` to get a real coverage number before
   committing to the catalogue.
4. Only then generalise the catalogue and open it up.

## 8. Caveats on the measurements

- Operator counts come from Flink 1.17.2 with `datagen`/`blackhole` connectors
  substituted for `upsert-kafka`. Absolute counts on the deployed version will
  differ (changelog normalisation on upsert sources adds per-source operators);
  the *differences* between designs, which is what the argument rests on, are
  unaffected because the substitution is identical across variants.
- The template SQL in §2 was written to measure cost, not to be correct. It has
  not been validated for semantic equivalence with the compiled queries; that
  is step 2 above.
- Operator count is a proxy for job-graph size, slot pressure and checkpoint
  surface. It is not a throughput measurement, and it does not capture the
  pushdown loss discussed in §5 — which pushes in the opposite direction and is
  why the `name IN (...)` mitigation is worth doing.
