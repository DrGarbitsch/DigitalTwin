#!/bin/bash
# Puts one bug back which this chain really had.
set -euo pipefail
sub() {
  python3 - "$1" "$2" "$3" <<'P'
import sys
f, old, new = sys.argv[1:]
s = open(f).read()
assert old in s, f'{old!r} not in {f}'
open(f, 'w').write(s.replace(old, new))
P
}
DS=semantic-model/dataservice
case "$1" in
  iri-label)          sub $DS/startDataservice.py 'prefix = "IriProperty"' 'prefix = "PropertyIri"' ;;
  python-boolean)     sub $DS/startDataservice.py '"v": str(value)' '"v": str(value.toPython())' ;;
  none-on-outage)     sub $DS/external_services/opcuaConnector.py 'await manager.handle_read_failure()' 'await manager.handle_read_failure(); publish(map, "None")' ;;
  enum-without-logic) sub semantic-model/opcua/owl2instances.py 'logic = bindingsg.enum_logic(shacl_rule['"'"'contentclass'"'"'])' 'logic = None' ;;
  bridge-drops-iri)   sub KafkaBridge/mqttBridge/sparkplug_data_ingestion.js "metricType === 'IriProperty'" "metricType === 'NoSuchProperty'" ;;
  bridge-batches-iri) sub KafkaBridge/lib/ngsildUpdates.js 'entities.filter(entity => !hasIriValue(entity))' 'entities' ;;
  bridge-batches-all) sub KafkaBridge/lib/ngsildUpdates.js 'entities.filter(entity => !hasIriValue(entity))' 'entities'
                      sub KafkaBridge/lib/ngsildUpdates.js 'entities.filter(hasIriValue)' '[]' ;;
  no-bug|no-bug-again) ;;
  *) echo "unknown bug $1"; exit 2 ;;
esac
