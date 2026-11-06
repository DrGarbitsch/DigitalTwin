#!/bin/bash
set -euxo pipefail
node spike/stage4b.js
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' lt-pg lt-kafka lt-scorpio
