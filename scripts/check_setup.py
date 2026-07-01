import os
import sys
import urllib.error
import urllib.request


def check_line_token(token):
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/info",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.status, res.read().decode("utf-8", errors="replace")


def main():
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    user_ids = [v.strip() for v in os.getenv("LINE_USER_IDS", "").split(",") if v.strip()]
    problems = []

    if not token:
        problems.append("LINE_CHANNEL_ACCESS_TOKEN is missing")
    if not user_ids:
        problems.append("LINE_USER_IDS is missing")
    if token:
        try:
            status, body = check_line_token(token)
            print(f"LINE token OK: {status} {body}")
        except urllib.error.HTTPError as exc:
            problems.append(f"LINE token check failed: {exc.code} {exc.read().decode('utf-8', errors='replace')}")
        except urllib.error.URLError as exc:
            problems.append(f"LINE token check failed: {exc}")

    print(f"LINE_USER_IDS count: {len(user_ids)}")
    if problems:
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        raise SystemExit(1)
    print("Setup looks ready.")


if __name__ == "__main__":
    main()
