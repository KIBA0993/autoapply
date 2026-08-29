#!/usr/bin/env python3
"""PreToolUse budget enforcer for AutoApply Mode B — the ENFORCEMENT layer.

Three runs proved that prose limits ("max 2 screenshots", "don't retry a broken site",
"every turn carries a tool call") are read and ignored: 55/58 workers loaded the contract
and still averaged ~16 screenshots/form and 200-275-turn tails. Nothing counted or rejected
the offending call. This hook does. It fires on every tool call (confirmed live: PreToolUse
reaches subagents, carries `agent_id`, and a `deny` blocks the call), counts calls in a
per-run state dir, and DENIES past budget so the model cannot exceed it no matter what the
prose says.

TWO ENFORCEMENT DOMAINS:

  A) WORKER (subagent, `agent_id` present) — per-form browser budgets. A subagent is marked a
     "browser worker" the first time it calls a claude-in-chrome tool; a non-browser
     research/screen subagent is never marked and never governed.
       screenshots   2    computer{action:screenshot} + screenshot sub-actions in browser_batch
       navigations   6    navigate calls — can't reach a form in 6 hops ⇒ dead site
       browser turns 140  total governed tool calls — a generous runaway backstop only

  B) CONDUCTOR / MAIN SESSION (`agent_id` absent) — two structural guards that the
     2026-08-28 top-30 run proved prose can't hold (972 turns, 564K-peak prefix, ~$107,
     because the conductor filled ~40 forms inline in ONE growing context):
       1. SEGMENT CEILING — > MAIN_BROWSER_MAX claude-in-chrome calls in a segment are DENIED,
          forcing a stop-and-re-kick before the prefix runs away. The counter RESETS on every
          UserPromptSubmit — a fresh in-chat prompt is a fresh segment (and authorization comes
          from the user in chat, never a disk-resumed checkpoint). Non-browser tools (Bash /
          Read / Write) are never counted or denied, so the conductor can always checkpoint.
       2. BLOCKING DISPATCH — a Mode B worker (Agent/Task whose prompt names mode_b_worker)
          launched with run_in_background:true is DENIED. That same run fired 4 workers
          fire-and-forget, skipping the dry-run gate and defaulting the conductor into the
          unbounded inline path. Blocking dispatch (run_in_background:false) makes the gate
          gate and keeps a single tab in flight.

FAIL-CLOSED: a denial can only make a worker/conductor STOP and return a NON-submit outcome
(couldnt_confirm / skip / segment-stop). It can never cause a submit — a submit is itself a
governed click that the ceiling denies. Worker messages steer to deterministic DOM reads
(aa.options / aa.describe / aa.verify / aa.identity) that replace the screenshot.

Registered from .claude/settings.json for BOTH PreToolUse (matcher "*") and UserPromptSubmit.
State lives under $TMPDIR/autoapply_budget/<session>/{<agent>|main}/ — unique agent ids mean
no cross-run bleed; the main counter is reset per user prompt.
"""
import json
import os
import shutil
import sys
import tempfile

SS_MAX = 2            # screenshots per worker (per form; a worker fills one form)
NAV_MAX = 6           # navigations per worker before we call the site dead
TURN_MAX = 140        # total governed tool calls per worker — runaway backstop, generous
MAIN_BROWSER_MAX = 120  # conductor browser calls per segment (~10 forms) before forced re-kick
BROWSER_PREFIX = "mcp__claude-in-chrome__"


def _allow():
    sys.exit(0)  # no output + exit 0 => the call proceeds untouched


def _deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def _browser_units(tool, tinp):
    """Context-growth units a single browser call adds, for the conductor ceiling. A
    browser_batch of N actions returns N results into context, so it counts as N (min 1) —
    otherwise the conductor could dilute the ceiling by packing actions into fat batches."""
    if tool == BROWSER_PREFIX + "browser_batch" and isinstance(tinp, dict):
        acts = tinp.get("actions")
        if isinstance(acts, list):
            return max(1, len(acts))
    return 1


# Every claude-in-chrome computer action that returns an IMAGE into context — not just
# "screenshot". `zoom` ("screenshot of a specific region") is an image too, so it must count,
# or a worker evades the cap by zooming instead of screenshotting.
IMAGE_ACTIONS = ("screenshot", "zoom")


def _screenshots_in(tool, tinp):
    """How many image-returning actions this single call would take (a batch may hold several)."""
    if not isinstance(tinp, dict):
        return 0
    if tool == BROWSER_PREFIX + "computer":
        return 1 if tinp.get("action") in IMAGE_ACTIONS else 0
    if tool == BROWSER_PREFIX + "browser_batch":
        n = 0
        acts = tinp.get("actions")
        for a in (acts if isinstance(acts, list) else []):
            if ((a or {}).get("input") or {}).get("action") in IMAGE_ACTIONS:
                n += 1
        return n
    return 0


def _bump(path, inc=1):
    try:
        with open(path) as f:
            v = int((f.read().strip() or "0"))
    except (OSError, ValueError):
        v = 0
    v += inc
    try:
        with open(path, "w") as f:
            f.write(str(v))
    except OSError:
        pass
    return v


def _safe(part):
    """Neutralize path separators / traversal in a harness-supplied id before it becomes a
    directory name. Ids are UUIDs in practice; this is belt-and-suspenders against '../' or '/'
    escaping the budget root or colliding two runs."""
    s = str(part).replace("/", "_").replace(os.sep, "_").replace("..", "_").strip()
    return s or "x"


def _run_dir(session_id, who):
    return os.path.join(tempfile.gettempdir(), "autoapply_budget", _safe(session_id), _safe(who))


def _is_mode_b_worker_dispatch(tool, tinp):
    """A conductor call that spawns a browser-driving Mode B worker subagent.

    Case-insensitive so 'Mode B Worker' / 'MODE B WORKER' can't evade. Detection is
    CONVENTION-BACKED: SKILL rule 7 mandates that every worker dispatch names the contract file
    `mode_b_worker.md` (the worker reads it), so a real dispatch always carries the marker. A
    dispatch that deliberately omits every marker below would evade this — that is out of scope
    (we govern our own skill's dispatches, and rule 7 keeps the marker present); it is not an
    adversarial control."""
    if tool not in ("Agent", "Task") or not isinstance(tinp, dict):
        return False
    blob = "{0}\n{1}".format(tinp.get("prompt") or "", tinp.get("description") or "").lower()
    return any(m in blob for m in ("mode_b_worker", "mode b worker", "mode-b worker"))


def _run():
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        _allow()
    if not isinstance(data, dict):
        _allow()

    event = data.get("hook_event_name") or ""
    session_id = data.get("session_id") or "nosess"

    # UserPromptSubmit: a fresh in-chat prompt starts a fresh conductor segment — reset the
    # main browser counter so the next kickoff/continue gets a full segment budget. (This is
    # the ONLY reset; it can't be triggered by the conductor itself, only by the user in chat.)
    if event == "UserPromptSubmit":
        try:
            shutil.rmtree(_run_dir(session_id, "main"), ignore_errors=True)
        except OSError:
            pass
        _allow()

    tool = data.get("tool_name") or ""
    tinp = data.get("tool_input") or {}
    is_browser_tool = tool.startswith(BROWSER_PREFIX)

    agent_id = data.get("agent_id")
    if not agent_id:
        # ---- CONDUCTOR / MAIN SESSION (domain B) ----
        # (2) Blocking dispatch: a Mode B worker must run one-at-a-time, not fire-and-forget.
        # The Agent tool runs background BY DEFAULT, so an omitted flag is still async — deny
        # unless run_in_background is EXPLICITLY false.
        if _is_mode_b_worker_dispatch(tool, tinp) and tinp.get("run_in_background") is not False:
            _deny("Dispatch Mode B workers BLOCKING and one at a time: call Agent with "
                  "run_in_background:false, wait for the worker's receipt, then record its "
                  "outcome AND dispatch the next worker in the SAME turn. Fire-and-forget async "
                  "workers skip the 3-job dry-run gate and let the conductor fall into an "
                  "unbounded inline context (the 564K-prefix / ~$107 run). Re-dispatch this "
                  "worker with run_in_background:false.")
        # (1) Segment ceiling: cap conductor browser calls so the prefix can't run away.
        if is_browser_tool:
            base = _run_dir(session_id, "main")
            try:
                os.makedirs(base, exist_ok=True)
            except OSError:
                _allow()
            n = _bump(os.path.join(base, "browser_calls"), _browser_units(tool, tinp))
            if n > MAIN_BROWSER_MAX:
                _deny("Segment browser budget ({0} claude-in-chrome calls) reached. STOP filling "
                      "now — do not open or submit another form this segment. Post a checkpoint "
                      "(submitted / parked / remaining frozen rows) and tell the user: to keep "
                      "cost linear, reply `/clear` then re-kick `/apply-auto` for the remaining "
                      "rows — the frozen snapshot preserves membership, and a fresh in-chat "
                      "kickoff re-authorizes the next segment. (Non-browser tools still work, so "
                      "you can finish logging and write the summary.)".format(MAIN_BROWSER_MAX))
        _allow()

    # ---- WORKER / SUBAGENT (domain A) ----

    base = _run_dir(session_id, str(agent_id))
    marker = os.path.join(base, "browser")

    # Govern only agents that have driven the browser at least once.
    if not is_browser_tool and not os.path.exists(marker):
        _allow()
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        _allow()                          # can't keep state → fail open, never block real work
    if is_browser_tool and not os.path.exists(marker):
        try:
            open(marker, "w").close()
        except OSError:
            pass

    # 1) runaway backstop — total governed tool calls
    turns = _bump(os.path.join(base, "turns"))
    if turns > TURN_MAX:
        _deny("Turn budget ({0}) exhausted for this worker. Stop now: record your current state "
              "and RETURN couldnt_confirm (or skip). Do NOT keep filling and do NOT click submit — "
              "the conductor will backfill this slot.".format(TURN_MAX))

    # 2) dead-site fast-fail — navigations
    if tool == BROWSER_PREFIX + "navigate":
        navs = _bump(os.path.join(base, "navs"))
        if navs > NAV_MAX:
            _deny("Navigation budget ({0}) exhausted — this site is not rendering a usable "
                  "application form (repeated redirects / broken page). RETURN skip with reason "
                  "'site-not-rendering'. Do not navigate again.".format(NAV_MAX))

    # 3) screenshot cap — computer + browser_batch
    ss = _screenshots_in(tool, tinp)
    if ss:
        total = _bump(os.path.join(base, "ss"), ss)
        if total > SS_MAX:
            _deny("Screenshot budget ({0}/form) exhausted. Get the same facts from the DOM with no "
                  "image: aa.verify() (field state + banners), aa.inventory() (fields), "
                  "aa.options(ref)/aa.openMenu(ref) (dropdown choices), aa.describe(ref) (an "
                  "unlabeled/image control), aa.blockers() (captcha/login/autofill), aa.identity() "
                  "(which job this page is). If you truly cannot confirm via DOM, return "
                  "couldnt_confirm. Do not screenshot again.".format(SS_MAX))

    _allow()


def main():
    """Top-level fail-open guard: no input shape may produce a traceback. _allow()/_deny() raise
    SystemExit (which must propagate); any other exception fails open to allow."""
    try:
        _run()
    except SystemExit:
        raise
    except Exception:
        _allow()


if __name__ == "__main__":
    main()
