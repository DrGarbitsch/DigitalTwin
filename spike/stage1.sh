#!/bin/bash
set -euxo pipefail
python3 -m venv .venv-model
.venv-model/bin/pip install -q -r semantic-model/opcua/requirements.txt -r semantic-model/opcua/requirements-dev.txt
mkdir -p nodesets
BASE=https://raw.githubusercontent.com/OPCFoundation/UA-Nodeset/UA-1.05.03-2023-12-15
for f in DI/Opc.Ua.Di.NodeSet2.xml Machinery/Opc.Ua.Machinery.NodeSet2.xml Pumps/Opc.Ua.Pumps.NodeSet2.xml Pumps/instanceexample.xml; do
  curl -fsS --retry 3 -o "nodesets/$(basename "$f")" "$BASE/$f"
done
cd semantic-model/opcua
PATH=$PWD/../../.venv-model/bin:$PATH make -f translate_default_nodesets.make pumps.owl.ttl > "$OUT/deps.log" 2>&1
../../.venv-model/bin/python nodeset2owl.py ../../nodesets/instanceexample.xml \
    -i core.owl.ttl machinery.owl.ttl di.owl.ttl pumps.owl.ttl -p instanceexample \
    -n http://yourorganisation.org/InstanceExample/ --serverUri urn:example:opcua-server \
    -o instanceexample.owl.ttl > "$OUT/model.log" 2>&1
../../.venv-model/bin/python owl2instances.py -t http://opcfoundation.org/UA/Pumps/PumpType -sb \
    -n http://demo.machine/ instanceexample.owl.ttl >> "$OUT/model.log" 2>&1
test "$(jq length instances.jsonld)" = 20
test "$(grep -c 'base:boundBy' bindings.ttl)" = 46
jq -r '.[].id' instances.jsonld | { ! grep -q '/'; }
