// The real updates bridge code against real Scorpio. Keycloak is the only thing replaced.
// The step from bridge attributes to update records is Core Services' Flink SQL. It is NOT run here:
// toUpdate() is a hand-written copy of its output format, and the known gap of this approach.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const Module = require('module');

const OUT = process.env.OUT;
const A = 'http://127.0.0.1:19090/ngsi-ld/v1';
const P = 'http://opcfoundation.org/UA/Pumps/';
const b64 = b => Buffer.from(b).toString('base64url');
const now = Math.floor(Date.now() / 1000);
const claims = { sub: 't', preferred_username: 'bridge', iat: now, exp: now + 3600, azp: 'ngsild-updates', aud: ['account'], realm_access: { roles: ['Factory-Admin', 'Factory-Writer'] } };
const unsigned = `${b64(JSON.stringify({ alg: 'RS256', typ: 'JWT' }))}.${b64(JSON.stringify(claims))}`;
const signature = crypto.sign('RSA-SHA256', Buffer.from(unsigned), fs.readFileSync(`${OUT}/key.pem`));
const TOKEN = `${unsigned}.${b64(signature)}`;

const load = Module._load;
Module._load = function (request, ...rest) {
  if (request === 'keycloak-connect') {
    return function () { this.grantManager = { obtainFromClientCredentials: async () => ({ access_token: { token: TOKEN } }) }; };
  }
  return load.call(this, request, ...rest);
};
const NgsildUpdates = require(path.resolve('KafkaBridge/lib/ngsildUpdates.js'));
const config = {
  ngsildServer: { hostname: '127.0.0.1', port: '19090', protocol: 'http:' },
  logger: { loglevel: 'error' },
  ngsildUpdates: { clientSecretVariable: 'NONE', refreshIntervalInSeconds: 200 },
  bridgeCommon: { kafkaSyncOnAttribute: 'https://industry-fusion.com/types/v0.9/metadata/kafkaSyncOn', hashLength: 24 },
  keycloak: { ngsildUpdatesAuthService: {} }
};

const headers = { Authorization: `Bearer ${TOKEN}` };
const get = async id => (await fetch(`${A}/entities/${encodeURIComponent(id)}`, { headers: { ...headers, Accept: 'application/json' } })).json();
function check (ok, text) { console.log(`${ok ? 'ok  ' : 'FAIL'} ${text}`); if (!ok) { throw new Error(text); } }

function toUpdate (a) {
  const attr = { observedAt: new Date().toISOString(), type: a.type, datasetId: '@none' };
  if (a.nodeType === '@json') attr.json = JSON.parse(a.attributeValue);
  else if (a.nodeType === '@id') attr.value = { '@id': a.attributeValue };
  else if (/^-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?$/.test(a.attributeValue) || ['true', 'false', 'null'].includes(a.attributeValue)) attr.value = JSON.parse(a.attributeValue);
  else attr.value = a.attributeValue;
  return { op: 'update', overwriteOrReplace: true, noForward: true, entities: JSON.stringify([{ id: a.entityId, [a.name]: [attr] }]) };
}

(async () => {
  const none = await fetch(`${A}/types`);
  check(none.status === 401, 'without a token: 401');
  const instances = fs.readFileSync('semantic-model/opcua/instances.jsonld');
  const load = await fetch(`${A}/entityOperations/upsert`, { method: 'POST', headers: { ...headers, 'Content-Type': 'application/ld+json' }, body: instances });
  check(load.status === 201, `20 entities loaded: ${load.status}`);
  await new Promise(resolve => setTimeout(resolve, 2000));

  const bridge = new NgsildUpdates(config);
  await new Promise(resolve => setTimeout(resolve, 300));
  const attrs = fs.readFileSync(`${OUT}/attributes.jsonl`, 'utf8').split('\n').filter(Boolean).map(JSON.parse);
  const s = Date.now();
  for (const a of attrs) await bridge.ngsildUpdates(toUpdate(a), Date.now());
  console.log(`${attrs.length} updates through the real bridge in ${Date.now() - s} ms`);
  await new Promise(resolve => setTimeout(resolve, 2000));

  const by = {};
  for (const a of attrs) by[a.name.replace(P, '')] = a.entityId;
  const read = async n => (await get(by[n]))[P + n];
  const value = async n => (await read(n)).value;
  check(await value('hasMotorTemperature') === 42.5, 'number after the recovery');
  check(await value('hasNumberOfStarts') === 17, 'UInt32');
  check(await value('hasRotorBlocked') === true, 'real boolean');
  check(await value('hasTechnicalDataLink') !== undefined, 'string');
  check(JSON.stringify(await value('hasInstallationDate')).includes('2025-07-14T08:30:00'), 'ISO timestamp');
  const cls = await value('hasPumpClass');
  check(JSON.stringify(cls).includes('PositiveDisplacementPump') && !JSON.stringify(cls).includes('@value'), 'enum is the IRI, with no leftover number');
  const modes = await read('hasOfferedControlModes');
  check(modes.type === 'JsonProperty' && JSON.stringify(modes.json).includes('AQA='), 'structure is a JsonProperty');
  check((await read('hasMotorTemperature')).observedAt !== undefined, 'observedAt is set');

  console.log('--- behaviours a fake would have to know');
  const merge = async (id, attr) => fetch(`${A}/entityOperations/merge`, { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json', Link: '<https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld>; rel="http://www.w3.org/ns/json-ld#context"' }, body: JSON.stringify([{ id, ...attr }]) });
  const m1 = await merge(by.hasOfferedControlModes, { [P + 'hasOfferedControlModes']: [{ type: 'Property', value: 'x' }] });
  check(m1.status === 400 && (await m1.text()).includes('SB001'), 'Property onto JsonProperty: 400 SB001');
  const m2 = await merge(by.hasPumpClass, { [P + 'hasPumpClass']: [{ type: 'Property', value: { '@id': P + 'LiquidPump' } }] });
  check(m2.status === 400 && (await m2.text()).includes('22023'), 'IRI value in a batch merge: 400 22023');
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
