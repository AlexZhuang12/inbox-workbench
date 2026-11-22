import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor


class GogError(Exception):
    pass


def run_gog(executable, arguments, env):
    try:
        result = subprocess.run(
            [executable, "--json", "--no-input", *arguments],
            env=env, capture_output=True, encoding="utf-8-sig", errors="replace",
            timeout=45, check=False,
        )
    except subprocess.TimeoutExpired:
        raise GogError("timeout") from None
    except OSError:
        raise GogError("gog_unavailable") from None
    if result.returncode:
        diagnostic = result.stderr.casefold()
        for pattern, code in (
            (r"invalid_grant|reauthori[sz]|revoked|invalid credentials|\b401\b", "reauthorization_required"),
            (r"insufficient.*scope|permission denied|\b403\b", "permission_denied"),
            (r"rate.?limit|quota|\b429\b", "rate_limited"),
        ):
            if re.search(pattern, diagnostic):
                raise GogError(code)
        raise GogError("gog_command_failed")
    try:
        output = json.loads(result.stdout)
    except ValueError:
        raise GogError("invalid_gog_response") from None
    if not isinstance(output, dict):
        raise GogError("invalid_gog_response")
    return output


def discover(executable, env):
    output = run_gog(executable, ["auth", "list"], env)
    accounts = output.get("accounts", False)
    if accounts is None:
        return []
    if not isinstance(accounts, list):
        raise GogError("invalid_account_list")
    connections = set()
    for account in accounts:
        if not isinstance(account, dict):
            raise GogError("invalid_account_list")
        email = account.get("email")
        client = account.get("client") or "default"
        services = account.get("services")
        if isinstance(services, str):
            services = services.lower().replace(",", " ").split()
        if isinstance(services, list) and services and "gmail" not in services:
            continue
        if not isinstance(email, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+", email):
            raise GogError("invalid_account_list")
        if not isinstance(client, str):
            raise GogError("invalid_account_list")
        connections.add((email.lower(), client))
    return sorted(connections)


def search_account(executable, env, connection, query, limit):
    email, client = connection
    result = {"account": email, "oauth_client": client}
    try:
        output = run_gog(
            executable,
            [
                "--readonly", "--gmail-no-send", "--wrap-untrusted",
                "--enable-commands-exact=gmail.search",
                f"--account={email}", f"--client={client}",
                "gmail", "search", f"--max={limit}", "--", query,
            ],
            env,
        )
        threads = output.get("threads", False)
        if threads is None:
            threads = []
        if not isinstance(threads, list) or any(not isinstance(row, dict) for row in threads):
            raise GogError("invalid_search_response")
        result.update(
            status="ok",
            threads=[{key: row[key] for key in ("id", "date", "from", "subject", "messageCount") if key in row}
                     for row in threads],
            more_available=bool(output.get("nextPageToken")),
        )
    except GogError as error:
        result.update(status="error", error=str(error))
    return result


def review(executable, query, limit):
    blocked = {"GOG_ACCESS_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS", "GOG_ACCOUNT", "GOG_CLIENT"}
    env = {key: value for key, value in os.environ.items() if key.upper() not in blocked}
    accounts = discover(executable, env)
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = [pool.submit(search_account, executable, env, account, query, limit) for account in accounts]
        results = [job.result() for job in pending]
    failed = sum(account["status"] == "error" for account in results)
    status = "ok"
    if not results:
        status = "no_gmail_accounts"
    elif failed == len(results):
        status = "all_failed"
    elif failed:
        status = "partial"
    return {"status": status, "accounts": results}


def main():
    parser = argparse.ArgumentParser(description="Read-only Gmail thread search across locally authorized accounts.")
    parser.add_argument("--query", required=True, help="Gmail search syntax, e.g. is:unread newer_than:2d")
    parser.add_argument("--limit", type=int, default=10, help="Maximum threads per account (1-50)")
    args = parser.parse_args()
    if not args.query.strip() or not 1 <= args.limit <= 50:
        parser.error("provide a nonempty query and a limit between 1 and 50")
    bundled = Path(__file__).resolve().parent / "bin" / "gog.exe"
    system_gog = shutil.which("gog.exe" if os.name == "nt" else "gog")
    executable = str(bundled) if bundled.is_file() else system_gog
    try:
        if not executable:
            raise GogError("gog_unavailable")
        report = review(executable, args.query, args.limit)
    except GogError as error:
        report = {"status": "error", "error": str(error), "accounts": []}
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["status"] in {"ok", "partial"} else 1


if __name__ == "__main__":
    sys.exit(main())
