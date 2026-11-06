#!/bin/bash
set -euxo pipefail
( cd KafkaBridge && npm ci --silent --ignore-scripts )
node spike/stage3.js
