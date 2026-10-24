#!/usr/bin/env python3
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
"""Assemble a SemForge package from the output of nodeset2owl.py and owl2instances.py, e.g.

    python3 owl2semforge.py instanceexample.owl.ttl entities.ttl -s shacl.ttl \\
        -m instances.jsonld -c context.jsonld -o ../kms/opcua-pumps

The knowledge becomes a directory holding the owl:imports closure of the given
files, one file per ontology, so the type system travels with the package.
"""

import argparse
import sys

from lib.semforge_package import EXCLUDED, build_package

DEFAULT_CONTEXT_URL = 'https://industryfusion.github.io/contexts/staging/opcua/v0.2/context.jsonld'


def parse_args(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('knowledge', nargs='+',
                        help='Knowledge files: the instance ontology (nodeset2owl.py) and entities.ttl '
                             '(owl2instances.py). Their owl:imports are followed.')
    parser.add_argument('-s', '--shacl', required=True, help='shacl.ttl from owl2instances.py.')
    parser.add_argument('-m', '--model', required=True, help='instances.jsonld from owl2instances.py.')
    parser.add_argument('-c', '--context', required=True, help='context.jsonld from owl2instances.py.')
    parser.add_argument('-xc', '--context-url', default=DEFAULT_CONTEXT_URL,
                        help='The context url the entities name (owl2instances.py -xc).')
    parser.add_argument('-n', '--name', help='Package name; defaults to the output directory name.')
    parser.add_argument('--ngsild', help='The NGSI-LD vocabulary: a path relative to the package, or a url.')
    parser.add_argument('-x', '--exclude', nargs='*', default=list(EXCLUDED),
                        help='Imports neither copied nor followed: url/path prefixes, or *suffix. '
                             'Default: the W3C vocabularies and */ngsild.ttl.')
    parser.add_argument('-o', '--output', required=True, help='The package directory to create.')
    return parser.parse_args(args)


if __name__ == '__main__':
    args = parse_args()
    written = build_package(args.output, args.knowledge, args.shacl, args.model, args.context,
                            args.context_url, name=args.name, ngsild=args.ngsild,
                            exclude=tuple(args.exclude))
    print(f'Wrote {len(written)} file(s) into {args.output}')
