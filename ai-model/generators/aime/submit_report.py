#!/usr/bin/env python3
"""
Submit or update an AIMe report on the registry and STORE its key.

`generate_aime_entry.py` builds the answers tree; this script is the only one that writes to
the registry. It POSTs (or PUTs) the report and persists the credentials the registry
returns — crucially the **password**, which is shown only once and is needed for every update.

Pipeline:  model description YAML  ->  build answers  ->  POST/PUT /report  ->  store {id, password}

Usage:
    python submit_report.py                        # submit ../../model-description.yaml, NOT public
    python submit_report.py path/to/model.yaml     # a specific model description file
    python submit_report.py update <id>            # new revision of an existing report, same visibility
    python submit_report.py update <id> --public   # ...and make it appear in the registry search
    python submit_report.py update <id> --private  # ...and hide it from the search again
    python submit_report.py list                   # show stored report credentials

  --base-url  registry API (default https://aime-registry.org/api, the live registry)
  --store     credentials file (default output/reports.json)
  --email     contact email (default: provenance.contacts[0].email)
  --password  (update only) report password, if it is not in the credentials file

A submitted report cannot be deleted — submit once, then always `update` the same id.

Credentials are saved to output/reports.json. That file contains report PASSWORDS — keep it
private (it is local-only; do not commit it).

Visibility: the registry's "Appear in search" answer (MD.8) is set to match isPublic, so the
record and its questionnaire answer never disagree.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml  # noqa: F401  (ensures a clear error if deps missing; used via generate module)
except ImportError:
    sys.exit("Missing dep. Run:  pip install -r requirements.txt")

import generate_aime_entry as gen  # same folder: reuse build_answers + HTTP transport

SCRIPT_DIR = Path(__file__).parent
DEFAULT_STORE = SCRIPT_DIR / "output" / "reports.json"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_store(path):
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            sys.exit(f"Store {p} exists but is not valid JSON — refusing to overwrite.")
    return []


def save_store(path, records):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(records, indent=2))


def build(args, is_public):
    answers, name = gen.load_and_build(args.input)
    answers.setdefault("MD", {})["8"] = bool(is_public)   # "Appear in search" mirrors isPublic
    return answers, name


def round_trip(base, rid, answers):
    status, got = gen._request("GET", f"{base}/report/{rid}")
    return status == 200 and isinstance(got, dict) and got.get("answers") == answers


def cmd_submit(args):
    base = args.base_url.rstrip("/")
    if args.public:
        print("Note: submitting straight to public. The usual flow is to submit not public, "
              "review, then `update <id> --public`.")
    answers, name = build(args, args.public)
    email = gen.contact_email(args.input, args.email)
    payload = {"answers": answers, "email": email,
               "isPublic": bool(args.public), "attachReport": False}
    status, resp = gen._request("POST", f"{base}/report", payload)
    if status != 200 or not isinstance(resp, dict) or "id" not in resp:
        sys.exit(f"POST /report failed: HTTP {status}: {resp}")

    rid, pw = resp["id"], resp["password"]
    # store FIRST — the password is never shown again
    record = {
        "name": name, "id": rid, "password": pw, "version": resp.get("version"),
        "is_public": bool(args.public), "base_url": base,
        "report_url": gen.report_page(base, rid), "input": str(args.input), "email": email,
        "submitted_at": _now(),
    }
    records = load_store(args.store)
    records.append(record)
    save_store(args.store, records)

    match = round_trip(base, rid, answers)
    record["round_trip"] = "match" if match else "MISMATCH"
    save_store(args.store, records)

    print(f"✓ Submitted '{name}'  ({'public' if args.public else 'NOT public'})")
    print(f"    id       : {rid}")
    print(f"    password : {pw}      <- needed for every update; stored, keep private")
    print(f"    review   : {record['report_url']}")
    print(f"    round-trip: {'MATCH' if match else 'MISMATCH'}")
    print(f"  -> credentials saved to {args.store}")
    if not args.public:
        print(f"\nWhen the record looks right:  python submit_report.py update {rid} --public")
    if not match:
        sys.exit(1)


def cmd_update(args):
    base = args.base_url.rstrip("/")
    records = load_store(args.store)
    stored = next((r for r in reversed(records) if r.get("id") == args.report_id), None)
    password = args.password or (stored or {}).get("password")
    if not password:
        sys.exit(f"No password for report {args.report_id} in {args.store}; pass --password.")

    # keep the current visibility unless --public / --private says otherwise
    if args.visibility is not None:
        is_public = args.visibility
    else:
        status, cur = gen._request("GET", f"{base}/report/{args.report_id}")
        if status != 200 or not isinstance(cur, dict):
            sys.exit(f"GET /report/{args.report_id} failed: HTTP {status}: {cur}\n"
                     "Pass --public or --private to set visibility explicitly.")
        is_public = bool(cur.get("isPublic", cur.get("public", False)))

    answers, name = build(args, is_public)
    email = gen.contact_email(args.input, args.email)
    payload = {"answers": answers, "email": email, "password": password,
               "isPublic": is_public, "attachReport": False}
    status, resp = gen._request("PUT", f"{base}/report/{args.report_id}", payload)
    if status != 200 or not isinstance(resp, dict):
        sys.exit(f"PUT /report/{args.report_id} failed: HTTP {status}: {resp}")

    # if the registry hands back a password, keep it (it may differ from the old one)
    new_pw = resp.get("password") or password
    if stored is None:
        stored = {"name": name, "id": args.report_id, "base_url": base,
                  "report_url": gen.report_page(base, args.report_id),
                  "input": str(args.input), "email": email, "submitted_at": None}
        records.append(stored)
    stored.update({"password": new_pw, "version": resp.get("version"), "is_public": is_public,
                   "updated_at": _now()})
    save_store(args.store, records)

    match = round_trip(base, args.report_id, answers)
    print(f"✓ Updated '{name}'  ({'public' if is_public else 'NOT public'})")
    print(f"    id       : {args.report_id}")
    if new_pw != password:
        print(f"    password : {new_pw}      <- CHANGED by the registry; stored, keep private")
    print(f"    view     : {gen.report_page(base, args.report_id)}")
    print(f"    round-trip: {'MATCH' if match else 'MISMATCH'}")
    print(f"  -> credentials saved to {args.store}")
    if not match:
        sys.exit(1)


def cmd_list(args):
    records = load_store(args.store)
    if not records:
        print(f"No stored reports in {args.store}.")
        return
    print(f"{len(records)} stored report(s) in {args.store}:\n")
    for r in records:
        when = r.get("updated_at") or r.get("submitted_at")
        vis = "public" if r.get("is_public") else "not public"
        print(f"  {when}  {r['name']}  ({vis})")
        print(f"      id={r['id']}  password={r['password']}  ({r['report_url']})")


def main():
    p = argparse.ArgumentParser(description="Submit or update an AIMe report and store its key")
    p.add_argument("--base-url", default=gen.DEFAULT_BASE, help=f"registry API (default {gen.DEFAULT_BASE})")
    p.add_argument("--email", default=None, help="contact email (default: provenance.contacts[0].email)")
    p.add_argument("--store", default=str(DEFAULT_STORE), help=f"credentials file (default {DEFAULT_STORE})")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("submit", help="build + POST + store credentials (default)")
    s.add_argument("input", nargs="?", default=str(gen.DEFAULT_INPUT))
    s.add_argument("--public", action="store_true", help="appear in search right away (default: not public)")

    u = sub.add_parser("update", help="build + PUT a new revision of an existing report")
    u.add_argument("report_id")
    u.add_argument("input", nargs="?", default=str(gen.DEFAULT_INPUT))
    u.add_argument("--password", default=None, help="report password (default: from the store)")
    vis = u.add_mutually_exclusive_group()
    vis.add_argument("--public", dest="visibility", action="store_const", const=True,
                     help="make the report appear in search")
    vis.add_argument("--private", dest="visibility", action="store_const", const=False,
                     help="hide the report from search")

    sub.add_parser("list", help="show stored report credentials")

    # global options may appear anywhere; a bare path or bare flags mean `submit ...`
    argv, global_opts, rest, i = sys.argv[1:], [], [], 0
    while i < len(argv):
        a = argv[i]
        if a in ("--base-url", "--email", "--store") and i + 1 < len(argv):
            global_opts += argv[i:i + 2]; i += 2; continue
        if a.split("=", 1)[0] in ("--base-url", "--email", "--store"):
            global_opts.append(a)
        else:
            rest.append(a)
        i += 1
    if not rest or rest[0] not in {"submit", "update", "list", "-h", "--help"}:
        rest = ["submit"] + rest
    args = p.parse_args(global_opts + rest)

    if args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "update":
        cmd_update(args)
    else:
        cmd_submit(args)


if __name__ == "__main__":
    main()
