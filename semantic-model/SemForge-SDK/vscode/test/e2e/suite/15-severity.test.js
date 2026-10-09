// Severity… on an attribute constraint in a real VS Code: SHACL's own level,
// then a new level made from the same picker -- an individual of sh:Severity
// written into the knowledge -- and set on the constraint.

const assert = require('assert');
const vscode = require('vscode');
const { PACKAGE_URI, semforge, until, answering, read } = require('./helpers');

const ENT = 'https://industryfusion.github.io/contexts/example/v0/base_entities/';

async function workpiecePage(api) {
  await vscode.commands.executeCommand('semforge.openTypePage',
    { raw: { kind: 'type', targetClass: `${ENT}Workpiece`, label: 'Workpiece', children: [] },
      packageUri: PACKAGE_URI });
  return until(() => api.pages.type.page && api.pages.type.page.label === 'Workpiece' &&
    api.pages.type.page, 'the Workpiece page');
}

/** hasHeight's property shape: from its sh:path to the next attribute's. */
function heightStatement(shacl) {
  const shape = shacl.slice(shacl.indexOf('iffBaseShacl:WorkpieceShape a'));
  const at = shape.indexOf('sh:path iffBaseEntities:hasHeight');
  const next = shape.indexOf('sh:path iffBaseEntities:', at + 1);
  return shape.slice(at, next > 0 ? next : at + 800);
}

describe('Severity… on a constraint', () => {
  it('SHACL\'s warning, then a new level of sh:Severity', async () => {
    const api = await semforge();
    let page = await workpiecePage(api);
    let row = page.attributes.findIndex((a) => a.label === 'hasHeight');
    let session = answering([{ kind: 'pick', label: '$(warning) Severity…' },
      { kind: 'pick', label: 'warning' }]);
    try {
      await api.pages.type.receive({ command: 'menu', row });
    } finally {
      session.restore();
    }
    await until(() => heightStatement(read('shacl.ttl')).includes('sh:severity sh:Warning'),
      'sh:severity sh:Warning on hasHeight');

    page = await until(() => api.pages.type.page && api.pages.type.page.attributes
      .find((a) => a.label === 'hasHeight' && a.severityDeclared) && api.pages.type.page,
    'the page to say it');
    row = page.attributes.findIndex((a) => a.label === 'hasHeight');
    session = answering([{ kind: 'pick', label: '$(warning) Severity…' },
      { kind: 'pick', label: '$(add) New severity level…' },
      { kind: 'input', value: 'severityMajor' }, { kind: 'input', value: 'major' }]);
    try {
      await api.pages.type.receive({ command: 'menu', row });
    } finally {
      session.restore();
    }
    const knowledge = read('knowledge.ttl');
    assert.ok(/severityMajor a owl:NamedIndividual, sh:Severity ;\s+rdfs:label "major"/.test(knowledge) ||
      /severityMajor a owl:NamedIndividual,\s*<http:\/\/www\.w3\.org\/ns\/shacl#Severity>/.test(knowledge),
    knowledge.slice(-400));
    await until(() => /sh:severity \S*severityMajor/.test(heightStatement(read('shacl.ttl'))),
      'the new level on hasHeight');
    await vscode.commands.executeCommand('workbench.action.closeAllEditors');
  });
});
