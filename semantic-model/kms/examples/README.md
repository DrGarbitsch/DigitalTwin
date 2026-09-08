# Examples

Executable specifications for the shapes in `../shacl.ttl`. `semforge test ..`
runs them; `expectations/validation.yaml` says what each one is for.

```
subobjects/   the pieces cases are assembled from
good/         expected to conform
bad/          expected to violate, and which constraint
```

## Why subobjects

"A cutter running while its filter is off" needs a filter, a cartridge and a
workpiece before it is a well-formed entity at all. Repeating those in every
case makes the difference between two cases hard to see and easy to get wrong —
`good/cutter-processing-with-filter-on` and
`bad/cutter-processing-with-filter-off` differ in exactly one included file, and
that is the whole point of the pair.

Includes are merged **before** the example, so the example wins where both
describe the same entity. That is what lets the bad case swap in a filter that
is OFF over the one the good case includes.

## Folders group, they do not decide

A file under `bad/` that asserts nothing is an unfinished test, not a passing
one. What an example means comes from `expect` and `asserts` in
`expectations/validation.yaml`, never from where it sits — which is the
manifest's §4.7 requirement, and the reason the runner reads the yaml rather
than the directory.

## What these cover

Before they existed, `semforge test --coverage` reported every constraint as
`no-firing-example`: nothing proved any of them could fire, and a constraint
that cannot fire looks exactly like one that is satisfied. Five are now
two-sided — proven able to fire *and* proven not to fire spuriously:

| constraint | fired by |
|---|---|
| `StateOnCutterShape` | `bad/cutter-processing-with-filter-off` |
| `CartridgeShape/hasCartridge` maxCount | `bad/cartridge-shared-by-two-filters` |
| `FilterShape/hasCartridge` minCount | `bad/filter-without-cartridge` |
| `WorkpieceShape/hasHeight` maxInclusive | `bad/workpiece-too-high` |
| `MachineShape/hasXXXWorkpiece` minCount | the shipped model |

The cartridge one is worth singling out: the exclusivity rule was added with
the inverse-path work and **nothing exercised it** until
`bad/cartridge-shared-by-two-filters` existed.

The other 67 constraints are still `no-firing-example`. That is honest rather
than complete, and `semforge test --coverage` lists them.
