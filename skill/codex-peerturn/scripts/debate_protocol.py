#!/usr/bin/env python3
"""Create, validate, or wait on a shared debate document."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

STATE_RE = re.compile(
    r"^<!-- (?:codex-meets-claude|codex-claude-debate)-state: (\{.*\}) -->$",
    re.MULTILINE,
)
ROUND_RE = re.compile(r"^## 第 (\d+) 轮 · (Codex|Claude)$", re.MULTILINE)
CONSTRAINT_RE = re.compile(r"^## Constraints\n(.*?)^## Topic$", re.MULTILINE | re.DOTALL)
VERDICT_RE = re.compile(
    r"^Verdict: (CONTINUE|PROPOSE_CONVERGENCE|ACCEPT_CONVERGENCE|CAP_REACHED|BLOCKED)$",
    re.MULTILINE,
)
ROLES = {"codex", "claude"}
STATUSES = {"open", "proposed", "converged", "capped", "blocked", "closed"}


class ProtocolError(ValueError):
    pass


def read_document(path: Path) -> tuple[str, dict]:
    text = path.read_text(encoding="utf-8")
    matches = list(STATE_RE.finditer(text))
    if len(matches) != 1:
        raise ProtocolError(f"expected one state marker, found {len(matches)}")
    if text.rstrip().splitlines()[-1] != matches[0].group(0):
        raise ProtocolError("state marker must be the final non-empty line")
    try:
        state = json.loads(matches[0].group(1))
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid state JSON: {exc}") from exc
    return text, state


def state_marker(state: dict) -> str:
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    return f"<!-- codex-meets-claude-state: {payload} -->"


def default_state_dir(
    platform=None,
    environ=None,
    home=None,
) -> Path:
    platform = platform or sys.platform
    environ = os.environ if environ is None else environ
    home = home or Path.home()
    override = environ.get("CODEX_MEETS_CLAUDE_STATE_DIR")
    if override:
        override_path = Path(override).expanduser()
        if not override_path.is_absolute():
            raise ProtocolError("CODEX_MEETS_CLAUDE_STATE_DIR must be absolute")
        return override_path
    if platform == "win32":
        local_app_data = environ.get("LOCALAPPDATA", "")
        base = (
            Path(local_app_data)
            if PureWindowsPath(local_app_data).is_absolute()
            else home / "AppData" / "Local"
        )
        return base / "CodexMeetsClaude" / "debates"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "CodexMeetsClaude" / "debates"
    candidate = Path(environ.get("XDG_STATE_HOME", ""))
    base = candidate if candidate.is_absolute() else home / ".local" / "state"
    return base / "codex-meets-claude" / "debates"


def default_debate_path(slug: str) -> Path:
    safe_slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") or "debate"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return default_state_dir() / f"{timestamp}-{safe_slug}.md"


def init_document(
    path: Path, first: str, max_rounds: int, private_parent: bool = False
) -> dict:
    if first != "codex":
        raise ProtocolError("Codex must write round 1")
    if max_rounds < 4 or max_rounds % 2:
        raise ProtocolError("max_rounds must be an even integer of at least 4")
    template = Path(__file__).resolve().parent.parent / "assets" / "debate-template.md"
    text, state = read_document(template)
    state["max_rounds"] = max_rounds
    text = STATE_RE.sub(state_marker(state), text)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if private_parent and os.name != "nt":
        path.parent.chmod(0o700)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(text)
    except FileExistsError as exc:
        raise ProtocolError(f"refusing to overwrite existing file: {path}") from exc
    return {"file": str(path.resolve()), "first": first, "max_rounds": max_rounds}


def validate(path: Path) -> dict:
    text, state = read_document(path)
    actual_constraints = CONSTRAINT_RE.search(text)
    if not actual_constraints:
        raise ProtocolError("missing constraint or topic section")
    if re.search(r"\{[A-Z][A-Z0-9_]*\}", text):
        raise ProtocolError("unresolved template placeholder found")
    required = {
        "version",
        "status",
        "next",
        "round",
        "max_rounds",
        "proposed_by",
        "constraints_sha256",
    }
    missing = required - state.keys()
    if missing:
        raise ProtocolError(f"missing state fields: {', '.join(sorted(missing))}")
    if state["version"] != 2:
        raise ProtocolError("unsupported protocol version")
    actual_hash = hashlib.sha256(actual_constraints.group(1).encode()).hexdigest()
    if state["constraints_sha256"] != actual_hash:
        raise ProtocolError("constraint section changed after debate creation")
    if state["status"] not in STATUSES:
        raise ProtocolError(f"invalid status: {state['status']}")
    if state["next"] not in ROLES | {None}:
        raise ProtocolError(f"invalid next role: {state['next']}")
    if state["proposed_by"] not in ROLES | {None}:
        raise ProtocolError(f"invalid proposed_by role: {state['proposed_by']}")

    rounds = [(int(number), role.lower()) for number, role in ROUND_RE.findall(text)]
    if not rounds:
        raise ProtocolError("no numbered rounds found")
    expected = [
        (number, "codex" if number % 2 else "claude")
        for number in range(1, len(rounds) + 1)
    ]
    if rounds != expected:
        raise ProtocolError("rounds must be sequential and alternate Codex/Claude")
    if state["round"] != rounds[-1][0]:
        raise ProtocolError("state round does not match the last round")

    starts = list(ROUND_RE.finditer(text))
    verdicts = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        found = VERDICT_RE.findall(text[start.start() : end])
        if len(found) != 1:
            raise ProtocolError(f"round {index + 1} must contain exactly one verdict")
        if index > 0 and "### Verification before reply" not in text[start.start() : end]:
            raise ProtocolError(
                f"round {index + 1} must record verification before replying"
            )
        verdicts.append(found[0])

    maximum = state["max_rounds"]
    if not isinstance(maximum, int) or maximum < 4 or maximum % 2:
        raise ProtocolError("max_rounds must be an even integer of at least 4")
    if state["round"] > maximum:
        raise ProtocolError("round exceeds max_rounds")

    last_role = rounds[-1][1]
    other_role = "claude" if last_role == "codex" else "codex"
    status = state["status"]
    allowed_status = {
        "CONTINUE": {"open"},
        "PROPOSE_CONVERGENCE": {"proposed"},
        "ACCEPT_CONVERGENCE": {"converged", "closed"},
        "CAP_REACHED": {"capped", "closed"},
        "BLOCKED": {"blocked", "closed"},
    }
    if status not in allowed_status[verdicts[-1]]:
        raise ProtocolError(f"status {status} does not match verdict {verdicts[-1]}")
    if verdicts[-1] == "ACCEPT_CONVERGENCE" and (
        len(verdicts) < 2 or verdicts[-2] != "PROPOSE_CONVERGENCE"
    ):
        raise ProtocolError("convergence acceptance must follow a proposal")
    if status in {"open", "proposed"} and state["next"] != other_role:
        raise ProtocolError(f"{status} debate must hand off to {other_role}")
    if status == "proposed" and state["proposed_by"] != last_role:
        raise ProtocolError("proposed_by must be the role that wrote the last round")
    if status != "proposed" and state["proposed_by"] is not None:
        raise ProtocolError("proposed_by is only valid while status is proposed")
    if status in {"converged", "capped", "blocked"} and state["next"] != "codex":
        raise ProtocolError(f"{status} debate must hand final reporting to codex")
    if status == "closed":
        if state["next"] is not None:
            raise ProtocolError("closed debate must set next to null")
        if "## Final Summary · Codex" not in text:
            raise ProtocolError("closed debate requires a Codex final summary")
    elif state["next"] is None:
        raise ProtocolError("only a closed debate may set next to null")
    if state["round"] == maximum and status not in {
        "capped",
        "converged",
        "closed",
        "blocked",
    }:
        raise ProtocolError("the final allowed round must stop or hand off for reporting")
    return state


def wait_for_turn(
    path: Path, role: str, after: int, timeout: float, interval: float
) -> dict:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            state = validate(path)
            last_error = None
            if state["status"] == "closed" or (
                state["next"] == role and state["round"] > after
            ):
                return state
        except (OSError, ProtocolError) as exc:
            last_error = str(exc)
        time.sleep(interval)
    detail = f"; last validation error: {last_error}" if last_error else ""
    raise TimeoutError(f"timed out waiting for {role} after round {after}{detail}")


def self_test() -> None:
    scratch = Path.cwd() / "scratch"
    temporary_root = scratch if scratch.is_dir() else Path.cwd()
    with tempfile.TemporaryDirectory(
        prefix="debate-protocol-test-", dir=temporary_root
    ) as directory:
        fake_home = Path(directory) / "home"
        assert default_state_dir("win32", {}, fake_home) == (
            fake_home / "AppData" / "Local" / "CodexMeetsClaude" / "debates"
        )
        assert default_state_dir(
            "win32", {"LOCALAPPDATA": "C:/Users/test/AppData/Local"}, fake_home
        ) == Path("C:/Users/test/AppData/Local/CodexMeetsClaude/debates")
        assert default_state_dir("darwin", {}, fake_home) == (
            fake_home
            / "Library"
            / "Application Support"
            / "CodexMeetsClaude"
            / "debates"
        )
        assert default_state_dir("linux", {}, fake_home) == (
            fake_home / ".local" / "state" / "codex-meets-claude" / "debates"
        )
        assert default_state_dir(
            "linux", {"XDG_STATE_HOME": "/private/state"}, fake_home
        ) == Path("/private/state/codex-meets-claude/debates")
        override = Path(directory) / "private-state"
        assert (
            default_state_dir(
                "linux", {"CODEX_MEETS_CLAUDE_STATE_DIR": str(override)}
            )
            == override
        )
        try:
            default_state_dir("linux", {"CODEX_MEETS_CLAUDE_STATE_DIR": "relative"})
        except ProtocolError:
            pass
        else:
            raise AssertionError("a relative private state override was accepted")
        scaffold = Path(directory) / "scaffold.md"
        initialized = init_document(scaffold, "codex", 12, private_parent=True)
        assert initialized["first"] == "codex" and scaffold.exists()
        if os.name != "nt":
            assert scaffold.stat().st_mode & 0o777 == 0o600
        try:
            init_document(scaffold, "codex", 12)
        except ProtocolError:
            pass
        else:
            raise AssertionError("init overwrote an existing file")
        text = scaffold.read_text(encoding="utf-8")
        for old, new in {
            "{TOPIC}": "Locks",
            "{TOPIC_AND_SCOPE}": "Choose the smallest safe lock.",
            "{CODEX_INITIAL_POSITION}": "Use one file token.",
            "{EVIDENCE_AND_ASSUMPTIONS}": "Assumption: one shared filesystem.",
            "{QUESTION_1}": "Can the token be stale?",
        }.items():
            text = text.replace(old, new)
        path = Path(directory) / "debate.md"
        path.write_text(text, encoding="utf-8")
        state = validate(path)
        assert state["next"] == "claude" and state["round"] == 1
        assert wait_for_turn(path, "claude", 0, 0.1, 0.01) == state
        path.write_text(
            text.replace(
                "<!-- codex-meets-claude-state:",
                "<!-- codex-claude-debate-state:",
            ),
            encoding="utf-8",
        )
        assert validate(path)["round"] == 1
        path.write_text(text, encoding="utf-8")
        path.write_text(
            text.replace("completely equal peers", "nominally equal peers"),
            encoding="utf-8",
        )
        try:
            validate(path)
        except ProtocolError:
            pass
        else:
            raise AssertionError("a modified constraint section was accepted")
        path.write_text(text, encoding="utf-8")

        old_footer = STATE_RE.search(text).group(0)
        round_two = """## 第 2 轮 · Claude

### Verification before reply

Checked the state marker and append protocol.

### Response

The file token is sufficient if the footer is written last.

### Handoff

Verdict: CONTINUE

"""
        next_state = state.copy()
        next_state.update(next="codex", round=2)
        new_footer = state_marker(next_state)

        def reply() -> None:
            time.sleep(0.05)
            path.write_text(
                text.replace(old_footer, round_two + new_footer), encoding="utf-8"
            )

        writer = threading.Thread(target=reply)
        writer.start()
        awakened = wait_for_turn(path, "codex", 1, 1, 0.01)
        writer.join()
        assert awakened["round"] == 2 and awakened["next"] == "codex"

        current = path.read_text(encoding="utf-8")
        path.write_text(
            current.replace(
                "### Verification before reply\n\nChecked the state marker and append protocol.\n\n",
                "",
            ),
            encoding="utf-8",
        )
        try:
            validate(path)
        except ProtocolError:
            pass
        else:
            raise AssertionError("a reply without prior verification was accepted")
        path.write_text(current, encoding="utf-8")

        footer = STATE_RE.search(current).group(0)
        round_three = """## 第 3 轮 · Codex

### Verification before reply

Checked Claude's claim against the footer-last protocol.

### Response

The footer-last rule resolves partial reads under the one-session-per-role constraint.

### Handoff

Verdict: PROPOSE_CONVERGENCE

"""
        proposed_state = next_state.copy()
        proposed_state.update(
            status="proposed", next="claude", round=3, proposed_by="codex"
        )
        proposed_footer = state_marker(proposed_state)
        path.write_text(
            current.replace(footer, round_three + proposed_footer), encoding="utf-8"
        )
        assert validate(path)["status"] == "proposed"

        current = path.read_text(encoding="utf-8")
        footer = STATE_RE.search(current).group(0)
        round_four = """## 第 4 轮 · Claude

### Verification before reply

Verified the one-session-per-role constraint in the immutable section.

### Response

Confirmed under that explicit constraint.

### Handoff

Verdict: ACCEPT_CONVERGENCE

"""
        converged_state = proposed_state.copy()
        converged_state.update(
            status="converged", next="codex", round=4, proposed_by=None
        )
        converged_footer = state_marker(converged_state)
        path.write_text(
            current.replace(footer, round_four + converged_footer), encoding="utf-8"
        )
        assert validate(path)["status"] == "converged"

        current = path.read_text(encoding="utf-8")
        footer = STATE_RE.search(current).group(0)
        closed_state = converged_state.copy()
        closed_state.update(status="closed", next=None)
        closed_footer = state_marker(closed_state)
        path.write_text(
            current.replace(
                footer, "## Final Summary · Codex\n\nConverged.\n\n" + closed_footer
            ),
            encoding="utf-8",
        )
        assert validate(path)["status"] == "closed"

        broken = text.replace('"next":"claude"', '"next":"codex"')
        path.write_text(broken, encoding="utf-8")
        try:
            validate(path)
        except ProtocolError:
            pass
        else:
            raise AssertionError("invalid handoff was accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("file", type=Path)
    init_parser = commands.add_parser("init", help="create a blank debate document")
    init_parser.add_argument(
        "file",
        type=Path,
        nargs="?",
        help="output path; omit for the platform's private state directory",
    )
    init_parser.add_argument("--first", choices=["codex"], default="codex")
    init_parser.add_argument("--max-rounds", type=int, default=12)
    init_parser.add_argument("--slug", default="debate", help="default filename slug")
    wait_parser = commands.add_parser("wait")
    wait_parser.add_argument("file", type=Path)
    wait_parser.add_argument("--role", choices=sorted(ROLES), required=True)
    wait_parser.add_argument("--after", type=int, required=True)
    wait_parser.add_argument("--timeout", type=float, default=1800)
    wait_parser.add_argument("--interval", type=float, default=1)
    commands.add_parser("self-test")
    args = parser.parse_args()

    try:
        if args.command == "init":
            path = args.file or default_debate_path(args.slug)
            result = init_document(
                path, args.first, args.max_rounds, private_parent=args.file is None
            )
        elif args.command == "validate":
            result = validate(args.file)
        elif args.command == "wait":
            result = wait_for_turn(
                args.file, args.role, args.after, args.timeout, args.interval
            )
        else:
            self_test()
            result = {"ok": True}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ProtocolError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
