#
# Copyright (c) 2026 IndustryFusion Foundation
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

"""What is derived from a loaded graph, kept on the graph.

A package reloaded after an edit reuses the graphs of every file that did not
change (package/graphcache.py), so what was derived from them still holds:
after a test case was edited, the editor's analysis recomputed every declared
attribute of the 217,582-triple OPC UA knowledge, a second each time.

The key says what else the value depends on; graphs in it are compared by
identity (weakly held, so a key never keeps a graph alive). A loaded graph is
never edited in place, and its size is in every key all the same.
"""

import weakref

from rdflib import Graph


def _part(value):
    return weakref.ref(value) if isinstance(value, Graph) else value


def on_graph(graph, name, key, compute):
    """compute(), kept on `graph` under `name` while `key` is unchanged."""
    key = (len(graph),) + tuple(_part(part) for part in key)
    slot = '_semforge_memo_' + name
    kept = graph.__dict__.get(slot)
    if kept is not None and kept[0] == key:
        return kept[1]
    value = compute()
    graph.__dict__[slot] = (key, value)
    return value
