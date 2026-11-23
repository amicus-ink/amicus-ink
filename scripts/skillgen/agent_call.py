#!/usr/bin/env python3
"""One seam for every coder/router call: Claude Code (`claude --print`) or Codex (`codex exec`).

Model and agent defaults live here and nowhere else. Calls run with cwd = a scratch
directory (the audit's out_dir), so a paper carrying injected instructions cannot write
into the repo: Claude gets a Write rule scoped to `write_dir`, Codex runs in the
`workspace-write` sandbox rooted at `cwd`.

Rate limits: a call that fails with a usage-limit / rate-limit signature is not a coder
failure. `run_agent` sleeps (AMICUS_RATE_LIMIT_SLEEP seconds, default 900) and retries the
same call, up to RATE_LIMIT_CAP_S of total waiting per call, and logs each wait to stderr.
The result carries `.rate_limit_waits` (count) and `.rate_limit_wait_s` (seconds).
"""
import os, re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AGENT = "claude"
DEFAULT_MODELS = {"claude": "claude-opus-5-5", "codex": "gpt-6.1-sol"}
DEFAULT_EFFORT = {"claude": None, "codex": "high"}
AGENTS = tuple(DEFAULT_MODELS)

RATE_LIMIT_SLEEP_S = 900           # override with env AMICUS_RATE_LIMIT_SLEEP (seconds)
RATE_LIMIT_CAP_S = 10 * 3600       # total waiting allowed per call

# Usage-limit signatures seen from the two CLIs ("You've hit your limit", "5-hour limit
# reached", "You've hit your usage limit ... try again at 3:15 PM", HTTP 429 bodies).
# Matched only against the tail of a failed (or near-empty) reply, never a normal coder reply.
RATE_LIMIT_RX = re.compile(
    r"usage[ _-]?limit|rate[ _-]?limit|too many requests|\b429\b|limit reached|"
    r"hit your (usage |session |5-hour |weekly |daily )?limit|reached (your|the) (usage |session |5-hour |weekly |daily )?limit|"
    r"session limit|limit will reset|resets? (at |in )?\d|try again (at|in|later)|quota (exceeded|exhausted)|"
    r"exceeded your (current )?quota|insufficient_quota|credit balance is too low|overloaded_error|\b529\b",
    re.I)


def default_model(agent):
    return DEFAULT_MODELS[agent]


def default_effort(agent):
    return DEFAULT_EFFORT[agent]


def is_rate_limited(r):
    """True when a finished call looks like a usage/rate-limit stop rather than a coder failure."""
    if r.returncode == -9:  # our own timeout kill
        return False
    out, err = (r.stdout or ""), (r.stderr or "")
    if r.returncode == 0 and len(out.strip()) >= 600:  # a real reply, not a limit notice
        return False
    return bool(RATE_LIMIT_RX.search((err[-1500:] + "\n" + out[-1500:])))


def build_command(agent, model, cwd, write_dir, effort):
    cwd, write_dir = str(Path(cwd).resolve()), str(Path(write_dir).resolve())
    if agent == "claude":
        cmd = ["claude", "--print", "--model", model, "--permission-mode", "acceptEdits",
               # No --add-dir: an added directory is writable under acceptEdits. Repo reads are
               # granted by a Read rule instead. `//` marks an absolute path in rule syntax, and
               # only Edit(path) rules are path-matched (they cover Write as well).
               "--allowedTools", f"Read(/{ROOT}/**),Read(/{write_dir}/**),Edit(/{write_dir}/**)"]
        if effort:
            cmd += ["--effort", effort]
        return cmd
    if agent == "codex":
        cmd = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-m", model,
               "--sandbox", "workspace-write", "-C", cwd]
        if effort:
            cmd += ["-c", f"model_reasoning_effort={effort}"]
        return cmd + ["-"]
    raise ValueError(f"unknown agent {agent!r}; expected one of {AGENTS}")


def _sleep(s):
    time.sleep(s)


def _log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _once(cmd, prompt, cwd, timeout):
    try:
        return subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        dec = lambda b: b.decode(errors="replace") if isinstance(b, bytes) else (b or "")
        return subprocess.CompletedProcess(e.cmd, -9, stdout=dec(e.stdout), stderr=f"timeout after {timeout}s")
    except FileNotFoundError as e:
        return subprocess.CompletedProcess(cmd, 127, stdout="", stderr=f"{cmd[0]} not found: {e}")


def run_agent(prompt, *, agent=DEFAULT_AGENT, model=None, cwd, write_dir=None, effort=None, timeout=1800):
    """One agent call with cwd = `cwd` and writes confined to `write_dir` (default `cwd`).
    A call that exceeds `timeout` is killed and reported as exit -9 so the caller's retry
    loop treats it like a call that wrote no output. Rate-limit stops wait and retry here."""
    model = model or default_model(agent)
    cwd = Path(cwd).resolve()
    cmd = build_command(agent, model, cwd, write_dir or cwd, effort)
    per_wait = float(os.environ.get("AMICUS_RATE_LIMIT_SLEEP", RATE_LIMIT_SLEEP_S))
    waited, n_waits = 0.0, 0
    while True:
        r = _once(cmd, prompt, cwd, timeout)
        if not is_rate_limited(r):
            break
        if waited + per_wait > RATE_LIMIT_CAP_S:
            _log(f"rate limit ({agent}/{model}): {waited/3600:.1f} h waited, cap {RATE_LIMIT_CAP_S/3600:.0f} h reached; giving up")
            break
        n_waits += 1
        _log(f"rate limit ({agent}/{model}): wait {n_waits}, sleeping {per_wait/60:.0f} min "
             f"({waited/60:.0f} min so far); reply tail: {((r.stderr or '') + (r.stdout or ''))[-160:].strip()!r}")
        _sleep(per_wait)
        waited += per_wait
    r.rate_limit_waits, r.rate_limit_wait_s = n_waits, waited
    return r


def sh_claude(prompt, model, timeout=1800):
    """Backward-compatible wrapper for scripts that predate run_agent (naive_*.py, flag_severity.py).
    Keeps their behavior: Claude, cwd = repo root."""
    return run_agent(prompt, agent="claude", model=model, cwd=ROOT, write_dir=ROOT, timeout=timeout)
