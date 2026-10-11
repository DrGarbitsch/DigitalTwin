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
"""Build the full (static + dynamic) nodeset2owl exports of all nodesets of translate_default_nodesets.make.

The nodeset2owl commands (inputs, dependencies, options) are taken from the Makefile; every command gets
--serverUri so that dynamic nodes are exported as well. The exports are the input of analyze.py.

usage: build_exports.py <output directory> [--server-uri urn:analysis:server]
"""
import argparse
import os
import shlex
import subprocess
import sys
import time

OPCUA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def make_commands():
    out = subprocess.run(['make', '-n', '-B', '-f', 'translate_default_nodesets.make', 'nodeset2owl'],
                         cwd=OPCUA_DIR, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if 'nodeset2owl.py' in line]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('outdir')
    parser.add_argument('--server-uri', default='urn:analysis:server')
    args = parser.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    for cmd in make_commands():
        argv = shlex.split(cmd)
        argv[0:2] = [sys.executable, os.path.join(OPCUA_DIR, 'nodeset2owl.py')]
        if '--serverUri' in argv:
            argv[argv.index('--serverUri') + 1] = args.server_uri
        else:
            argv += ['--serverUri', args.server_uri]
        output = argv[argv.index('-o') + 1]
        log = os.path.join(args.outdir, output.replace('.owl.ttl', '.log'))
        if os.path.exists(os.path.join(args.outdir, output)):
            print(f'{output}: exists, skipped')
            continue
        start = time.time()
        with open(log, 'w') as logfile:
            result = subprocess.run(argv, cwd=args.outdir, stdout=logfile, stderr=subprocess.STDOUT)
        print(f'{output}: {"ok" if result.returncode == 0 else "FAILED"} ({time.time() - start:.0f}s)', flush=True)
        if result.returncode != 0:
            sys.exit(1)


if __name__ == '__main__':
    main()
