---
description: Monitor a DigitalTwin PR through CI — checks Build (deterministic) and K8s tests (flakiness analysis), auto-retries failed runs, stops on success or confirmed deterministic failure.
---

# /watch-pr

Monitor a pull request in the IndustryFusion/DigitalTwin repository through CI until it either passes or has a confirmed deterministic failure.

## Usage

```
/watch-pr <PR number>
```

## Procedure

### 1. Identify the branch

```
gh pr view <PR> --repo IndustryFusion/DigitalTwin --json headRefName,title,state
```

### 2. Check the Build workflow (always deterministic)

```
gh run list --repo IndustryFusion/DigitalTwin --branch <branch> --workflow "Build" --limit 1 --json databaseId,conclusion,status,url
```

- If **failed**: fetch the logs (`gh run view <id> --repo IndustryFusion/DigitalTwin --log-failed`), identify the root cause, and report it. Do not proceed to K8s monitoring until the build is green — build failures must be fixed.
- If **in_progress** or **queued**: report that the build is still running and wait for it before analysing K8s.
- If **success**: proceed to step 3.

### 3. Analyse the K8s tests workflow for determinism

Fetch the last two completed K8s test runs:

```
gh run list --repo IndustryFusion/DigitalTwin --branch <branch> --workflow "K8s tests" --limit 5 --json databaseId,conclusion,status,createdAt
```

**Decision rules (applied strictly):**

| Observation | Verdict | Action |
|---|---|---|
| Fewer than 2 completed runs | Not enough data | Trigger a run if none in progress; wait and re-check |
| 2+ completed runs with **different** failing steps/assertions | Flaky | Re-trigger the latest run; keep monitoring |
| 2+ completed runs with the **same** failing step and assertion | **Deterministic failure** | Fetch logs, identify root cause, report and stop monitoring |
| Latest run succeeded | **Success** | Report and stop monitoring |

To compare failures, fetch the log of each failed run:

```
gh run view <id> --repo IndustryFusion/DigitalTwin --log-failed 2>&1 | tail -60
```

Look for the specific assertion or step name that failed. If the same BATS test name and the same assertion string appear in both runs, the failure is deterministic.

### 4. Monitor loop

Set up a recurring check every 30 minutes:

```
/loop 30m Check K8s tests for PR <PR> ...
```

On each iteration:
- If **in_progress / queued**: report still running, keep looping.
- If **success**: report success, stop looping (omit ScheduleWakeup / CronDelete the job).
- If **failure**: compare with the previous failed run (step 3). If flaky: re-trigger with `gh run rerun <id> --repo IndustryFusion/DigitalTwin` and keep looping. If deterministic: report root cause and stop looping.

### 5. Reporting

At each check, output a one-line status:

```
PR #<N> K8s tests — <status> (<run id>) [<verdict if completed>]
```

On stopping, summarise:
- Final verdict (success / deterministic failure / stopped by user)
- Run IDs compared (if determinism was assessed)
- Suggested next step (fix and push / merge-ready)

## Key rules

- **Build workflow failures are always deterministic.** Never ignore them.
- **K8s test failures require two consecutive runs with the same error** before being treated as deterministic. A single failure is presumed flaky.
- Re-trigger failed K8s runs with `gh run rerun <id> --repo IndustryFusion/DigitalTwin` (not `--failed`).
- Never push fixes to `origin` (IndustryFusion/DigitalTwin) directly. All fixes go to `drgarbitsch` (the fork) and come in via a new PR that notes it supersedes the original and asks for the original to be closed on merge.
