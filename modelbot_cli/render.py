"""Plain-text rendering of submissions, results and leaderboards."""

from __future__ import annotations

TERMINAL = ("succeeded", "failed", "error", "cancelled")

STATUS_TEXT = {
    "queued": "waiting for a GPU",
    "dispatching": "starting on a runner",
    "running": "running (build, accuracy, performance)",
    "succeeded": "evaluated",
    "failed": "failed",
    "error": "infrastructure error (does not count against you; please resubmit)",
    "cancelled": "cancelled",
}


def status_line(sub: dict) -> str:
    text = STATUS_TEXT.get(sub["status"], sub["status"])
    if sub["status"] == "queued" and sub.get("queue_position"):
        text += f" (position {sub['queue_position']})"
    if sub.get("status") == "queued" and sub.get("attempts"):
        text += f", retry after: {sub.get('reason')}"
    return f"submission {sub['id']} [{sub['mode']}] {text}"


def _fmt(v, nd=4):
    return "-" if v is None else f"{v:.{nd}f}" if isinstance(v, float) else str(v)


def result_report(sub: dict) -> str:
    res = sub.get("result")
    lines = [f"submission {sub['id']}  {sub['problem']}@{sub['version']}  mode={sub['mode']}  status={sub['status']}"
             f"  reason={sub.get('reason')}"]
    if res is None:
        if sub.get("message"):
            lines.append(f"  message: {sub['message']}")
        return "\n".join(lines)
    for gate in res.get("gates", []):
        state = {True: "passed", False: "FAILED", None: "not run"}[gate.get("passed")]
        if gate["name"] == "performance" and gate.get("passed") is False and res.get("outcome") == "succeeded":
            state = "measured, not faster than Vulkan on every item"
        dur = f"  {gate['duration_s']:.0f} s" if gate.get("duration_s") else ""
        lines.append(f"  {gate['name']:<12} {state}{dur}")
        for item in gate.get("items", []):
            if gate["name"] == "accuracy":
                lines.append(f"      {item['name']:<20} ppl {_fmt(item.get('value'))}  ref {_fmt(item.get('baseline'))}"
                             f"  ratio {_fmt(item.get('ratio'))}  {'ok' if item.get('passed') else 'OUT OF TOLERANCE'}")
            elif gate["name"] == "performance":
                lines.append(f"      {item['name']:<20} {_fmt(item.get('value'), 2):>8} t/s  vulkan {_fmt(item.get('baseline'), 2):>7}"
                             f"  x{_fmt(item.get('ratio'), 3)}  {'faster' if item.get('passed') else 'slower'}"
                             f"  (cv {_fmt(item.get('cv'), 4)})")
        if gate.get("not_run"):
            lines.append(f"      not run: {', '.join(gate['not_run'])}")
    score = res.get("score")
    if score:
        lines.append(f"  score {score['value']:.4f}  (geometric mean of ROCm / Vulkan over all items, higher is better)"
                     f"  qualified={res.get('qualified')}")
    if res.get("message"):
        lines.append(f"  message: {res['message']}")
    env = res.get("environment", {})
    if env.get("gpu_name"):
        arch = f" ({env['gpu_arch']})" if env.get("gpu_arch") else ""
        lines.append(f"  ran on {env['gpu_name']}{arch}")
    return "\n".join(lines)


def leaderboard_report(board: dict) -> str:
    names = [b["name"] for b in board.get("benchmarks", [])]
    lines = [f"{board['problem']}@{board['version']}"]
    for key, title in (("qualified", "Qualified (faster than Vulkan on every item)"),
                       ("accuracy_passed", "Accuracy passed, not yet faster than Vulkan on every item")):
        rows = board.get(key, [])
        lines.append(f"\n{title}")
        if not rows:
            lines.append("  (none)")
            continue
        lines.append("  " + f"{'#':>3} {'user':<16} {'score':>8} {'cv':>7} " + " ".join(f"{n[:16]:>16}" for n in names))
        for r in rows:
            items = {i["name"]: i for i in r.get("items", [])}
            cells = " ".join(f"{_fmt(items[n]['value'], 2) if n in items else '-':>16}" for n in names)
            lines.append(f"  {r['rank']:>3} {r['user']:<16} {r['score']:>8.4f} {_fmt(r.get('cv')):>7} {cells}")
    return "\n".join(lines)
