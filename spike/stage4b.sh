#!/bin/bash
set -euxo pipefail
node spike/stage4b.js 2>&1 | tee "$OUT/stage4b.log"
: "the bridge logs what Scorpio refuses and carries on, so a refused update has to fail the test"
if grep -E '^error:' "$OUT/stage4b.log"; then exit 1; fi
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' lt-pg lt-kafka lt-scorpio
