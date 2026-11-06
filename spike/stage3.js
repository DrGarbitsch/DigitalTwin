// The bridge's real mapper, fed with the messages the dataservice really sent.
const fs = require('fs');
const path = require('path');
const mapper = require(path.resolve('KafkaBridge/mqttBridge/spb_ngsild_mapper.js'));

const OUT = process.env.OUT;
const FN = {
  Property: mapper.mapSpbPropertyToKafka,
  LiteralProperty: mapper.mapSpbPropertyToKafka,
  IriProperty: mapper.mapSpbPropertyIriToKafka,
  JsonProperty: mapper.mapSpbPropertyJsonToKafka,
  Relationship: mapper.mapSpbRelationshipToKafka
};
const ingestion = fs.readFileSync('KafkaBridge/mqttBridge/sparkplug_data_ingestion.js', 'utf8');
const last = new Map();
for (const line of fs.readFileSync(`${OUT}/messages.jsonl`, 'utf8').split('\n').filter(Boolean)) {
  const m = JSON.parse(line);
  last.set(`${m.i} ${m.n}`, m);
}
const out = [];
for (const m of last.values()) {
  if (!FN[m.t]) throw new Error(`The bridge has no mapping for label ${m.t}`);
  if (!ingestion.includes(`metricType === '${m.t}'`)) throw new Error(`The ingestion drops label ${m.t}`);
  out.push(FN[m.t](m.i, { name: `${m.t}/${m.n}`, value: m.v, timestamp: Date.now() }));
}
for (const [t, nodeType] of [['Property', '@value'], ['IriProperty', '@id'], ['JsonProperty', '@json']]) {
  const found = out.find(a => a.nodeType === nodeType);
  if (!found) throw new Error(`No attribute of ${t}`);
  console.log(`ok   ${t} -> nodeType ${nodeType}, type ${found.type}`);
}
fs.writeFileSync(`${OUT}/attributes.jsonl`, out.map(a => JSON.stringify(a)).join('\n') + '\n');
console.log(`ok   ${out.length} attributes mapped`);
