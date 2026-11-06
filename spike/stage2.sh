#!/bin/bash
set -euxo pipefail
python3 -m venv .venv-dataservice
.venv-dataservice/bin/pip install -q -r semantic-model/dataservice/requirements.txt asyncua
PY=$PWD/.venv-dataservice/bin/python
M="$OUT/messages.jsonl"
: > "$M"
start_server() {
  ( cd semantic-model/dataservice
    nohup "$PY" -u tests/server/nodeset_server.py -e opc.tcp://127.0.0.1:4840/ \
      -x ../../nodesets/Opc.Ua.Di.NodeSet2.xml -x ../../nodesets/Opc.Ua.Machinery.NodeSet2.xml \
      -x ../../nodesets/Opc.Ua.Pumps.NodeSet2.xml -x ../../nodesets/instanceexample.xml \
      -w "$(cd ../opcua && pwd)/bindings.ttl" >> "$OUT/server.log" 2>&1 & echo $! > "$OUT/server.pid" )
  : "wait for the server"
  for i in $(seq 1 120); do [ "$(grep -c 'Server running' "$OUT/server.log")" -ge "$1" ] && return 0; sleep 1; done
  return 1
}
nohup "$PY" spike/fake_agent.py "$M" > "$OUT/agent.log" 2>&1 &
s=$SECONDS; start_server 1; echo "server start: $((SECONDS-s))s"
MODEL=$(cd semantic-model/opcua && pwd)
( cd semantic-model/dataservice
  OPCUA_TCP_CONNECT=opc.tcp://127.0.0.1:4840/ nohup "$PY" startDataservice.py "$MODEL" "$MODEL/bindings.ttl" > "$OUT/dataservice.log" 2>&1 &
  echo $! > "$OUT/dataservice.pid" )
sleep 12
"$PY" spike/write_values.py all
sleep 12
python3 spike/check_messages.py "$M"

: "outage: nothing is sent, the dataservice survives"
kill "$(cat "$OUT/server.pid")"; sleep 7
n=$(wc -l < "$M"); sleep 15
test "$(wc -l < "$M")" = "$n"
kill -0 "$(cat "$OUT/dataservice.pid")"

: "recovery without restarting the dataservice"
start_server 2
"$PY" spike/write_values.py after
for i in $(seq 1 30); do tail -n 60 "$M" | grep -q '"v": "42.5"' && break; sleep 1; done
tail -n 60 "$M" | grep -q '"v": "42.5"'
echo "recovered after the outage"
test "$(grep -c '"None"' "$M" || true)" = 0
top -b -n1 -p "$(cat "$OUT/dataservice.pid")" | tail -1 | awk '{print "dataservice CPU%", $9}'
kill "$(cat "$OUT/dataservice.pid")" "$(cat "$OUT/server.pid")"
