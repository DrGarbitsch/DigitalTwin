/**
* Copyright (c) 2026 IndustryFusion Foundation
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*    http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/

/**
 * The expression editor's list of parts, for one expression as the server
 * sends it. Prints one JSON line: [{label, description, address}].
 *
 *   node expression.js <vscode/src directory>
 */
const Module = require('module');
const path = require('path');

const original = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'vscode') {
    return { QuickPickItemKind: { Separator: -1 } };
  }
  return original(request, parent, isMain);
};

const { lines } = require(path.resolve(process.argv[2], 'expression.js'));

const leaf = (words, conditions) => ({ kind: 'leaf', words, conditions: conditions || [{}] });
const expression = {
  kind: 'op', op: 'and', words: 'all of', children: [
    leaf('0 – 100'),
    { kind: 'op', op: 'or', words: 'any of', children: [
      leaf('number (double)'),
      { kind: 'op', op: 'not', words: 'not', children: [leaf('number (integer)')] },
      { kind: 'raw', words: '[ sh:node ex:Other ]' }] }]
};
const empty = { kind: 'op', op: 'and', words: 'all of', children: [
  leaf('any value', []),
  { kind: 'op', op: 'xone', words: 'exactly one of', children: [leaf('text'), leaf('URL')] }] };

console.log(JSON.stringify([expression, empty].map((tree) => lines(tree, [], 0, []).map(
  (item) => ({ label: item.label, description: item.description || '', address: item.address })))));
