"""modelbot: submit llama.cpp patches and follow their evaluation.

  modelbot register github [--api URL] [--no-browser]
  modelbot reregister github [--api URL] [--no-browser]
  modelbot whoami
  modelbot problems [NAME]
  modelbot submit PATCH --problem NAME [--no-wait] [--base DIR]
  modelbot status ID [--wait]
  modelbot list [--problem NAME]
  modelbot patch ID [-o FILE]
  modelbot cancel ID
  modelbot leaderboard [NAME]
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import re
import sys
import time
import webbrowser
from pathlib import Path

from modelbot_cli import __version__
from modelbot_cli.client import ApiError, Client, config_path, load_config, save_config
from modelbot_cli.precheck import check_local
from modelbot_cli.render import TERMINAL, leaderboard_report, result_report, status_line

POLL_S = 10
SIGNIN_POLL_S = 2


def _default_problem(client: Client, name: str | None, how: str = "pass --problem NAME") -> str:
    if name:
        return name
    probs = client.get("/problems")
    if len(probs) == 1:
        return probs[0]["name"]
    if not probs:
        raise SystemExit("no problem is open")
    raise SystemExit(f"several problems are open ({', '.join(p['name'] for p in probs)}); {how}")


def _open_browser(url: str) -> bool:
    # Without a display, webbrowser falls back to console browsers that take over the terminal.
    if not (sys.platform in ("darwin", "win32") or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False
    try:
        return webbrowser.open(url, new=2)
    except webbrowser.Error:
        return False


def cmd_register(args, reset: bool = False) -> int:
    """popcorn-cli's register / reregister: the token is saved right away and becomes valid once
    the GitHub sign-in in the browser completes; waiting here only reports how it ended."""
    client = Client(api_url=args.api, token="")
    init = client.get("/auth/init", params={"provider": args.provider, "reset": str(reset).lower()})
    previous = load_config()
    cfg = {**previous, "api_url": client.api, "token": init["token"]}
    cfg.pop("name", None)
    save_config(cfg)
    print(f"Open this URL to sign in with GitHub:\n\n  {init['authorize_url']}\n")
    if not args.no_browser and _open_browser(init["authorize_url"]):
        print("Opened it in your browser; finish the sign-in there.")
    print(f"waiting for the sign-in (the link is valid for {init['expires_in'] // 60} minutes) ...")
    status = Client(api_url=client.api, token=init["token"])
    try:
        while True:
            res = status.get("/auth/status")
            if res["status"] == "ok":
                cfg["name"] = res["name"]
                save_config(cfg)
                done = "signed in again as" if reset else "registered as"
                note = "; the previous token of this account no longer works" if reset else ""
                print(f"{done} {res['name']} (GitHub {res['github_login']}); token saved to {config_path()}{note}")
                return 0
            if res["status"] == "failed":
                save_config(previous)
                print(f"sign-in failed: {res['detail']}")
                return 1
            time.sleep(SIGNIN_POLL_S)
    except KeyboardInterrupt:
        print(f"\nstopped waiting; the token in {config_path()} starts working once you finish the sign-in")
        return 130


def cmd_whoami(args) -> int:
    me = Client().get("/me")
    github = f" (GitHub {me['github_login']})" if me.get("github_login") else ""
    print(f"{me['name']}{github}, registered {me['created_at'][:19]}")
    return 0


def cmd_problems(args) -> int:
    client = Client()
    if args.name:
        p = client.get(f"/problems/{args.name}")
        if args.json:
            print(json.dumps(p, indent=2))
            return 0
        print(f"{p['ref']}  deadline {p['deadline']}  GPU {p['gpu_type']}")
        print(f"base {p['base']['repo']} @ {p['base']['commit']}")
        print(f"image {p['image']}")
        print(f"allowed paths: {', '.join(p['allowed_paths'])}  (max {p['max_patch_bytes']} bytes)")
        print(f"accuracy: perplexity within {p['accuracy']['tolerance']:.0%} ({p['accuracy']['mode']}) of the unmodified build")
        t = p["timeouts"]
        print(f"time budgets: build {t['build']} s, accuracy {t['accuracy']} s, performance {t['performance']} s")
        for t in p["tests"]:
            print(f"  ppl {t['name']:<12} ref {t['ref_ppl']}  chunks {t['chunks']}  args {' '.join(t['args'])}")
        for b in p["benchmarks"]:
            print(f"  bench {b['name']:<18} vulkan {b['vulkan_avg_ts']} t/s  (case {b['case']})")
        print("\n" + p["description"])
        return 0
    for p in client.get("/problems"):
        print(f"{p['ref']:<40} deadline {p['deadline']}  {len(p['benchmarks'])} benchmark items")
    return 0


def _wait(client: Client, sid: int) -> dict:
    last = None
    while True:
        sub = client.get(f"/user/submissions/{sid}")
        line = status_line(sub)
        if line != last:
            print(f"[{time.strftime('%H:%M:%S')}] {line}")
            last = line
        if sub["status"] in TERMINAL:
            return sub
        time.sleep(POLL_S)


def _exit_code(sub: dict) -> int:
    if sub["status"] != "succeeded":
        return 1
    res = sub.get("result") or {}
    return 0 if res.get("passed") else 1


def cmd_submit(args) -> int:
    client = Client()
    problem = _default_problem(client, args.problem)
    info = client.get(f"/problems/{problem}")
    patch = Path(args.patch)
    check = check_local(patch, info["allowed_paths"], info["max_patch_bytes"], Path(args.base) if args.base else None)
    if not check.ok:
        print("local pre-check failed:")
        for p in check.problems:
            print(f"  - {p}")
        return 2
    with patch.open("rb") as f:
        sub = client.post(f"/submissions/{problem}/leaderboard", files={"file": (patch.name, f, "text/x-diff")})
    print(f"submitted {patch.name} to {problem}@{sub['version']} as submission {sub['id']}")
    if args.no_wait:
        print(status_line(sub))
        return 0
    sub = _wait(client, sub["id"])
    print(result_report(sub))
    return _exit_code(sub)


def cmd_status(args) -> int:
    client = Client()
    sub = _wait(client, args.id) if args.wait else client.get(f"/user/submissions/{args.id}")
    print(json.dumps(sub, indent=2) if args.json else result_report(sub) if sub["status"] in TERMINAL
          else status_line(sub))
    return _exit_code(sub) if sub["status"] in TERMINAL else 0


def cmd_list(args) -> int:
    client = Client()
    params = {"limit": args.limit}
    if args.problem:
        params["problem"] = args.problem
    for s in client.get("/user/submissions", params=params):
        score = f"{s['score']:.4f}" if s.get("score") is not None else "-"
        mark = "  disqualified" if s.get("disqualified_at") else ""
        print(f"{s['id']:>6}  {s['created_at'][:19]}  {s['mode']:<11} {s['status']:<10} {str(s.get('reason')):<20}"
              f" score {score:<8} qualified={s.get('qualified')}{mark}")
    return 0


def cmd_patch(args) -> int:
    """Download the archived patch for one of your submissions."""
    client = Client()
    data, headers = client.bytes(f"/user/submissions/{args.id}/patch")
    sha = headers.get("X-Patch-Sha256") or headers.get("x-patch-sha256")
    if args.output:
        out = Path(args.output)
    else:
        name = headers.get("Content-Disposition") or headers.get("content-disposition") or ""
        # attachment; filename="foo.patch"
        m = re.search(r'filename="([^"]+)"', name) or re.search(r"filename=([^;]+)", name)
        base = (m.group(1).strip() if m else "submission.patch")
        out = Path(base)
        if out.exists():
            out = Path(f"{args.id}-{base}")
    out.write_bytes(data)
    check = f"  sha256={sha}" if sha else ""
    print(f"wrote {out} ({len(data)} bytes){check}")
    return 0


def cmd_cancel(args) -> int:
    sub = Client().post(f"/user/submissions/{args.id}/cancel")
    print(status_line(sub) + ("  (cancel requested)" if sub.get("cancel_requested") else ""))
    return 0


def cmd_leaderboard(args) -> int:
    client = Client()
    board = client.get(f"/leaderboard/{_default_problem(client, args.name, 'name one: modelbot leaderboard NAME')}")
    print(json.dumps(board, indent=2) if args.json else leaderboard_report(board))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="modelbot", description="Submit llama.cpp patches to modelbot.")
    parser.add_argument("--version", action="version", version=f"modelbot {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name, reset, text in (("register", False, "register with your GitHub account and store the token"),
                              ("reregister", True, "sign in again with GitHub: a new token for your account")):
        p = sub.add_parser(name, help=text)
        p.add_argument("provider", choices=["github"])
        p.add_argument("--api", help="API URL (default: $MODELBOT_API_URL, saved config, "
                                     "or https://rocm-challenge.amddev.ai)")
        p.add_argument("--no-browser", action="store_true", help="only print the sign-in link, do not open a browser")
        p.set_defaults(func=functools.partial(cmd_register, reset=reset))

    p = sub.add_parser("whoami", help="show the account of the saved token")
    p.set_defaults(func=cmd_whoami)

    p = sub.add_parser("problems", help="list open problems or show one")
    p.add_argument("name", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_problems)

    p = sub.add_parser("submit", help="submit a patch")
    p.add_argument("patch")
    p.add_argument("--problem")
    p.add_argument("--no-wait", action="store_true")
    p.add_argument("--base", help="llama.cpp checkout at the base commit, to run `git apply --check` locally")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("status", help="show a submission")
    p.add_argument("id", type=int)
    p.add_argument("--wait", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("list", help="list your submissions")
    p.add_argument("--problem")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("patch", help="download the archived patch of a submission")
    p.add_argument("id", type=int)
    p.add_argument("-o", "--output", help="output path (default: the original file name)")
    p.set_defaults(func=cmd_patch)

    p = sub.add_parser("cancel", help="cancel a submission")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_cancel)

    p = sub.add_parser("leaderboard", help="show the leaderboard")
    p.add_argument("name", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_leaderboard)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ApiError as e:
        print(f"error: {e.detail}" + (f" ({e.reason})" if e.reason else ""), file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
