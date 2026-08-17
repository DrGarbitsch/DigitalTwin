#!/usr/bin/env python3
#
# Copyright (c) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Load the rule catalogs as one RDF graph and query them.

There is nothing to generate. Each specification's spec.jsonld is JSON-LD, so
the manifest the runner reads and the graph a SPARQL engine reads are the same
bytes -- this tool only collects them.

    rules_graph.py                     summary per specification
    rules_graph.py --dump              the merged graph as Turtle, on stdout
    rules_graph.py --query FILE.rq     run a SPARQL query and print the rows

Example, every rule blocked on an Attribute the translation drops, anywhere in
a specification that transitively builds on Part 3:

    PREFIX opcv: <urn:opcua:validation:vocab:>
    SELECT ?id WHERE {
      ?spec opcv:buildsOn+ <urn:opcua:validation:spec:10000-3> .
      ?rule opcv:definedBy ?spec ; opcv:ruleId ?id ; opcv:status "blocked" .
    }
"""

import argparse
import sys
from pathlib import Path

from rdflib import Graph

HERE = Path(__file__).resolve().parent
VALIDATION_DIR = HERE.parent
SPECS_DIR = VALIDATION_DIR / 'specs'
VOCABULARY = VALIDATION_DIR / 'vocabulary.ttl'

SUMMARY = """
PREFIX opcv: <urn:opcua:validation:vocab:>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?doc ?status (COUNT(?rule) AS ?count) WHERE {
  ?rule a opcv:ValidationRule ;
        opcv:status ?status ;
        opcv:definedBy ?spec .
  ?spec opcv:documentNumber ?doc .
} GROUP BY ?doc ?status ORDER BY ?doc ?status
"""


def load(include_vocabulary=True):
    """Parse every spec.jsonld, and the vocabulary, into one graph."""
    graph = Graph()
    manifests = sorted(SPECS_DIR.glob('*/spec.jsonld'))
    if not manifests:
        print(f'No spec.jsonld found under {SPECS_DIR}', file=sys.stderr)
        return None
    for manifest in manifests:
        # The @context is a relative reference to validation/context.jsonld;
        # rdflib resolves it against the file, so this stays offline.
        graph.parse(manifest, format='json-ld')
    if include_vocabulary and VOCABULARY.is_file():
        graph.parse(VOCABULARY, format='turtle')
    return graph


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--dump', action='store_true',
                        help='Print the merged graph as Turtle')
    parser.add_argument('--query', metavar='FILE',
                        help='Run a SPARQL query from FILE against the merged graph')
    parser.add_argument('--no-vocabulary', action='store_true',
                        help='Load only the manifests, without vocabulary.ttl')
    args = parser.parse_args()

    graph = load(include_vocabulary=not args.no_vocabulary)
    if graph is None:
        return 1

    if args.dump:
        print(graph.serialize(format='turtle'))
        return 0

    query = Path(args.query).read_text() if args.query else SUMMARY
    rows = list(graph.query(query))
    if not rows:
        print('(no rows)')
        return 0
    for row in rows:
        print('  ' + '  '.join(str(value) for value in row))
    return 0


if __name__ == '__main__':
    sys.exit(main())
