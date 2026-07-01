import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MESSAGE = ROOT / "data" / "line_message.txt"


def post_line_message(token, user_id, text):
    body = json.dumps(
        {
            "to": user_id,
            "messages": [{"type": "text", "text": text[:5000]}],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.status, res.read().decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", type=Path, default=DEFAULT_MESSAGE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    text = args.message.read_text(encoding="utf-8")
    user_ids = [v.strip() for v in os.getenv("LINE_USER_IDS", "").split(",") if v.strip()]
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()

    if args.dry_run:
        print(text)
        return
    if not token:
        raise SystemExit("LINE_CHANNEL_ACCESS_TOKEN is required")
    if not user_ids:
        raise SystemExit("LINE_USER_IDS is required. Use comma-separated LINE user IDs.")

    for user_id in user_ids:
        try:
            status, response = post_line_message(token, user_id, text)
            print(f"sent to {user_id}: {status} {response}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"LINE API error for {user_id}: {exc.code} {detail}") from exc


if __name__ == "__main__":
    main()
