import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SELECTED = ROOT / "data" / "selected_events.json"


def sync_selected_events(webhook_url, selected_path):
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    payload = {
        "kind": "selected_events_sync",
        "selected_at": selected.get("selected_at", ""),
        "selection_policy": selected.get("selection_policy", {}),
        "events": selected.get("events", []),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        response_text = res.read().decode("utf-8", errors="replace")
        return res.status, response_text


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected", type=Path, default=DEFAULT_SELECTED)
    parser.add_argument("--webhook-url", default=os.getenv("FEEDBACK_WEBHOOK_URL", ""))
    parser.add_argument("--optional", action="store_true")
    args = parser.parse_args()

    webhook_url = args.webhook_url.strip()
    if not webhook_url:
        message = "FEEDBACK_WEBHOOK_URL is not set"
        if args.optional:
            print(f"skip: {message}")
            return
        raise SystemExit(message)

    try:
        status, response_text = sync_selected_events(webhook_url, args.selected)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"feedback sync failed: {exc.code} {detail}") from exc
    print(f"feedback sync: {status} {response_text}")


if __name__ == "__main__":
    main()
