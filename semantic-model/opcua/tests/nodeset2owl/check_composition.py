#
# Copyright (c) 2026 Intel Corporation
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
"""Check that the static export (without --serverUri) and the dynamic export (--serverUri --dynamic-only)
compose the full export (--serverUri): static + dynamic must be isomorphic to full, and the static export
must not contain any dynamic node."""

import argparse
import sys
from rdflib import Graph, Namespace
from rdflib.namespace import OWL, RDF
from rdflib.compare import to_isomorphic, graph_diff

UARDF = Namespace('http://opcfoundation.org/rdf/uacore#')


def main(full_file, static_file, dynamic_file):
    full, static, dynamic = Graph().parse(full_file), Graph().parse(static_file), Graph().parse(dynamic_file)
    ok = True
    # the dynamic export has its own ontology header (<ontology> + base64url(svu=<server>)), which is not part
    # of the full export
    own_headers = set(dynamic.subjects(RDF.type, OWL.Ontology)) - set(full.subjects(RDF.type, OWL.Ontology))
    if len(own_headers) != 1:
        print(f'Dynamic export must have exactly one own ontology header, found {own_headers}')
        ok = False
    for header in own_headers:
        dynamic.remove((header, None, None))
    union = static + dynamic
    if list(static.triples((None, UARDF.serverUri, None))):
        print('Static export contains dynamic nodes (uardf:serverUri)')
        ok = False
    if not list(dynamic.triples((None, UARDF.serverUri, None))):
        print('Dynamic export contains no dynamic node')
        ok = False
    if to_isomorphic(full) != to_isomorphic(union):
        _, only_full, only_union = graph_diff(to_isomorphic(full), to_isomorphic(union))
        print(f'static + dynamic != full: {len(only_full)} triples only in full, {len(only_union)} only in union')
        for triple in list(only_full)[:10]:
            print('  full: ', triple)
        for triple in list(only_union)[:10]:
            print('  union:', triple)
        ok = False
    if ok:
        print(f'OK: static ({len(static)}) + dynamic ({len(dynamic)}) == full ({len(full)})')
    return 0 if ok else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('full')
    parser.add_argument('static')
    parser.add_argument('dynamic')
    args = parser.parse_args()
    sys.exit(main(args.full, args.static, args.dynamic))
