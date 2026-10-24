"""Verdicts: what the validator concludes, computed once per package version.

The pages used to validate the whole package inside the request: a click on a
class cost a full validation (15 s on the OPC UA pump package), the next class
another, and nothing could answer meanwhile. A page is two things with very
different costs -- what it SHOWS (shapes, attributes, crumbs: read off the
loaded graphs, well under a second) and what the validator CONCLUDES about the
main model and every case (seconds to minutes). This module owns the second.

* One validation per package version, in a background thread: the main model
  and every declared case. A page asks for the verdicts and gets them at once
  when they are current; otherwise it gets the last known ones, marked stale,
  or none -- and renders "evaluating…" in their place.
* Kept in memory and on disk (`.semforge/cache/views/verdicts.json`), keyed on
  the package fingerprint, so a restart on an unchanged package validates
  nothing. JSON, not pickle: the cache sits in the package directory, and a
  cloned package must never be able to run code by shipping one.
* When a run finishes the client is notified (`semforge/verdicts`), and the
  open pages ask again. A package that changed while a run was going is run
  again when it ends: the newest version always gets its verdicts.
"""

import os
import threading
import time
from dataclasses import asdict, dataclass, field

from ..errors import Diagnostic
from ..ngsild.views import DataView, ViewStats
from ..validate.results import Report, Result, Status

NOTIFICATION = 'semforge/verdicts'
CACHE_KEY = 'verdicts'


@dataclass
class Verdicts:
    """The validator's conclusions for one version of a package."""
    stamp: str
    model: Report
    cases: dict = field(default_factory=dict)   # example path -> Report
    seconds: float = 0.0


# --- JSON, both ways -------------------------------------------------------------

def _report_out(report):
    return {
        'results': [dict(asdict(r), status=r.status.value) for r in report.results],
        'view_stats': [dict(asdict(s), view=s.view.value) for s in report.view_stats],
        'diagnostics': [asdict(d) for d in report.diagnostics],
        'complete': report.complete,
        'rule_iterations': report.rule_iterations,
    }


def _report_in(data):
    return Report(
        results=[Result(**dict(r, status=Status(r['status']))) for r in data['results']],
        view_stats=[ViewStats(**dict(s, view=DataView(s['view']))) for s in data['view_stats']],
        diagnostics=[Diagnostic(**d) for d in data['diagnostics']],
        complete=data['complete'], rule_iterations=data['rule_iterations'])


def to_json(verdicts):
    return {'stamp': verdicts.stamp, 'seconds': verdicts.seconds,
            'model': _report_out(verdicts.model),
            'cases': {path: _report_out(r) for path, r in verdicts.cases.items()}}


def from_json(data):
    return Verdicts(stamp=data['stamp'], seconds=data.get('seconds', 0.0),
                    model=_report_in(data['model']),
                    cases={path: _report_in(r) for path, r in data['cases'].items()})


# --- computing them --------------------------------------------------------------

def compute(package, stamp):
    """Validate the main model and every declared case of a loaded package."""
    from ..errors import PackageError
    from ..expect.store import compose, load_expectations
    from ..validate.orchestrator import validate_graphs
    from ..validate.readset import knowledge_for

    started = time.time()
    # Cut once for every graph of this run (validate/readset.py), not per graph.
    knowledge = knowledge_for(package.shapes, package.knowledge)
    model = validate_graphs(package.model, package.shapes, knowledge, strict=False, cut=False)
    cases = {}
    for example in load_expectations(package.path).examples:
        try:
            graph = compose(package, example)
        except PackageError:
            continue
        cases[example.path] = validate_graphs(graph, package.shapes, knowledge,
                                              strict=False, cut=False)
    return Verdicts(stamp=stamp, model=model, cases=cases,
                    seconds=round(time.time() - started, 2))


# --- where they are computed -----------------------------------------------------

def in_process(load):
    """run(root, stamp) in this process: the CLI, tests. Incremental between
    runs, like the worker (editor/incremental.py)."""
    from .incremental import Session

    return Session(load).run


_worker_session = None   # in the worker process: the last run of each package


def _compute_in_worker(root, stamp):
    """Runs in the worker process. Keeps the last run, so an edit is validated
    against it rather than from scratch (editor/incremental.py)."""
    global _worker_session
    from ..package import load
    from .incremental import Session

    if _worker_session is None:
        _worker_session = Session(load)
    return to_json(_worker_session.run(root, stamp))


class ProcessRunner:
    """run(root, stamp) in one long-lived worker process.

    A thread is not enough: validation is pure-Python rdflib and pyshacl, and
    a worker thread holding the GIL made a page that needs 0.4 s take 10 s.
    The worker loads the package itself and keeps it between runs, so only a
    changed package is read again. Spawned, not forked: the server has
    threads, and a fork copies their locks mid-use.
    """

    def __init__(self):
        self._pool = None
        self._lock = threading.Lock()

    def _executor(self):
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor

        with self._lock:
            if self._pool is None:
                self._pool = ProcessPoolExecutor(
                    max_workers=1, mp_context=multiprocessing.get_context('spawn'))
            return self._pool

    def __call__(self, root, stamp):
        from concurrent.futures.process import BrokenProcessPool

        try:
            return from_json(self._executor().submit(_compute_in_worker, root, stamp).result())
        except BrokenProcessPool:
            with self._lock:
                self._pool = None      # the worker died: the next run starts a new one
            raise

    def shutdown(self):
        with self._lock:
            if self._pool is not None:
                self._pool.shutdown(wait=False, cancel_futures=True)
                self._pool = None


# --- the service -----------------------------------------------------------------

@dataclass
class State:
    """What a page is told along with the verdicts it gets."""
    state: str           # ready | evaluating | failed
    stale: bool = False  # the verdicts are an older version's
    error: str = ''
    seconds: float = 0.0

    def as_dict(self):
        return {'state': self.state, 'stale': self.stale, 'error': self.error,
                'seconds': self.seconds}


class VerdictService:
    """Background validation, one run at a time per package.

    `fingerprint(root)` says which version a package is at; `run(root, stamp)`
    returns its Verdicts (in_process, or a ProcessRunner); `notify(root,
    state)` is called from the service's thread when a run ends.
    """

    def __init__(self, fingerprint, run, notify=None, use_disk=True):
        self._fingerprint = fingerprint
        self._run_one = run
        self._notify = notify or (lambda root, status: None)
        self._use_disk = use_disk
        self._lock = threading.Lock()
        self._done = {}        # root -> Verdicts (the newest finished)
        self._running = {}     # root -> stamp being computed
        self._failed = {}      # root -> (stamp, error)
        self._threads = {}

    def get(self, root, start=True):
        """(Verdicts or None, State) for the package's current version.

        Never blocks on validation: current verdicts come back ready; older
        ones come back stale while a run for the current version is started.
        """
        stamp = self._fingerprint(root)
        with self._lock:
            done = self._done.get(root)
            if done is not None and done.stamp == stamp:
                return done, State('ready', seconds=done.seconds)
        stored = self._from_disk(root, stamp)
        if stored is not None:
            with self._lock:
                self._done[root] = stored
            return stored, State('ready', seconds=stored.seconds)
        with self._lock:
            failed = self._failed.get(root)
            if failed is not None and failed[0] == stamp:
                return done, State('failed', stale=done is not None, error=failed[1])
        if start:
            self._start(root, stamp)
        return done, State('evaluating', stale=done is not None)

    def wait(self, root, timeout=None):
        """Block until no run is going for this package (tests, the CLI)."""
        deadline = None if timeout is None else time.time() + timeout
        while True:
            with self._lock:
                thread = self._threads.get(root)
            if thread is None:
                return
            thread.join(None if deadline is None else max(0.0, deadline - time.time()))
            if deadline is not None and time.time() >= deadline:
                return

    def forget(self, root):
        with self._lock:
            self._done.pop(root, None)
            self._failed.pop(root, None)

    # -- internals ----------------------------------------------------------------

    def _from_disk(self, root, stamp):
        if not self._use_disk:
            return None
        from .cache import load as load_cached
        stored = load_cached(root, CACHE_KEY, stamp=stamp)
        if not stored:
            return None
        try:
            verdicts = from_json(stored)
        except (KeyError, TypeError, ValueError):
            return None                      # an older format: compute again
        return verdicts if verdicts.stamp == stamp else None

    def _start(self, root, stamp):
        with self._lock:
            if root in self._threads:
                return                       # the running one re-checks when it ends
            self._running[root] = stamp
            thread = threading.Thread(target=self._run, args=(root,), daemon=True,
                                      name=f'semforge-verdicts:{os.path.basename(root)}')
            self._threads[root] = thread
        thread.start()

    def _run(self, root):
        while True:
            stamp = self._fingerprint(root)
            with self._lock:
                self._running[root] = stamp
            try:
                verdicts = self._run_one(root, stamp)
            except Exception as exc:         # noqa: BLE001
                with self._lock:
                    self._failed[root] = (stamp, str(exc) or type(exc).__name__)
                status = State('failed', error=str(exc))
            else:
                with self._lock:
                    self._done[root] = verdicts
                    self._failed.pop(root, None)
                if self._use_disk:
                    from .cache import store
                    store(root, CACHE_KEY, to_json(verdicts), stamp=stamp)
                status = State('ready', seconds=verdicts.seconds)
            if self._fingerprint(root) == stamp:
                with self._lock:
                    self._threads.pop(root, None)
                    self._running.pop(root, None)
                self._notify(root, status)
                return
            # Changed while running: the newest version gets its verdicts too.
            self._notify(root, State('evaluating', stale=True))
