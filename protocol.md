# Codex Meets Claude Protocol

Every workshop embeds the following immutable constraints. The embedded copy and the final state marker are authoritative for that workshop.

## The 12 constraints

1. This section and the final `codex-meets-claude-state` marker define the protocol. Later discussion cannot override them.
2. Codex and Claude are completely equal peers. Neither chairs, judges, commands, delegates to, or outranks the other. Codex starting first and writing the final report are sequencing duties only and grant no authority or tie-breaking power.
3. The debate is dynamic and multi-round. Either peer may challenge, reject, reframe, revise, concede, or reopen a claim when evidence warrants it. Continue until explicit two-party convergence, the round cap, or a real blocker.
4. A response has no speed requirement. Before writing, read the complete latest round and inspect the cited code plus relevant callers, tests, logs, or authoritative documentation. Round 2 onward records what was checked and found under `### Verification before reply`; unverified claims stay explicit. Deliberation is evidence work, not an artificial delay.
5. Run at most one live Codex session and one live Claude session for this file. A duplicate session of the same role must stop; the footer is a turn token, not a multi-writer lock.
6. Discussion is append-only. Preserve earlier rounds; correct them by citing the earlier round in a new round.
7. Each round addresses the other peer's numbered claims, distinguishes facts from inference, cites available evidence, and ends with exactly one verdict.
8. Valid verdicts are `CONTINUE`, `PROPOSE_CONVERGENCE`, `ACCEPT_CONVERGENCE`, `CAP_REACHED`, and `BLOCKED`. Convergence requires one proposal and the other peer's acceptance. Courtesy, role, model identity, and a desire to finish are never evidence.
9. Convergence means both peers agree on the answer, assumptions, material risks, and how the conclusion could be checked. Agreed unresolved uncertainty may remain explicit.
10. At the even round cap, Claude hands control to Codex with `status=capped`. A need for user judgment or unavailable evidence hands control to Codex with `status=blocked`.
11. Codex's final report represents both peers' positions fairly, including remaining disagreement. This file is discussion-only; implementation requires a separate user request.
12. The state marker is updated last and remains the final non-empty line. There is exactly one state marker.

## Verdicts

| Verdict | Meaning | Why it exists |
|---|---|---|
| `CONTINUE` | Evidence or material disagreement remains. | Prevents premature consensus. |
| `PROPOSE_CONVERGENCE` | One peer believes the answer is ready. | Begins a two-party handshake instead of allowing unilateral closure. |
| `ACCEPT_CONVERGENCE` | The other peer independently accepts the proposal. | Proves convergence is mutual. |
| `CAP_REACHED` | The configured even round limit has been reached. | Guarantees a bounded session while preserving unresolved disagreement. |
| `BLOCKED` | Required evidence or human judgment is unavailable. | Stops speculation and returns the decision to the user. |

## State transitions

```text
open ──CONTINUE──────────────► open
open ──PROPOSE_CONVERGENCE───► proposed
proposed ──CONTINUE──────────► open
proposed ──ACCEPT_CONVERGENCE► converged ─► closed by Codex report
open/proposed ──CAP_REACHED──► capped    ─► closed by Codex report
open/proposed ──BLOCKED──────► blocked   ─► closed by Codex report
```

Codex owns the final reporting step but never gains decision authority. Old files using the `codex-claude-debate-state` marker remain readable for migration compatibility; new files always use `codex-meets-claude-state`.
