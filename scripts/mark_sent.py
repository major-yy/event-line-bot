import argparse
import datetime as dt
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SELECTED = ROOT / "data" / "selected_events.json"
DEFAULT_HISTORY = ROOT / "data" / "sent_history.json"


def load_json(path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected", type=Path, default=DEFAULT_SELECTED)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    args = parser.parse_args()

    selected = load_json(args.selected, {"events": []})
    history = load_json(args.history, {"sent_events": []})
    by_id = {item["id"]: item for item in history.get("sent_events", []) if item.get("id")}
    sent_at = dt.datetime.now(dt.timezone.utc).isoformat()

    for event in selected.get("events", []):
        event_id = event.get("id")
        if not event_id:
            continue
        by_id.setdefault(
            event_id,
            {
                "id": event_id,
                "sent_at": sent_at,
                "name": event.get("name", ""),
                "prefecture": event.get("prefecture", ""),
                "start_date_iso": event.get("start_date_iso", ""),
                "end_date_iso": event.get("end_date_iso", ""),
                "url": event.get("url", ""),
            },
        )

    args.history.parent.mkdir(parents=True, exist_ok=True)
    args.history.write_text(
        json.dumps({"sent_events": list(by_id.values())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"marked {len(selected.get('events', []))} events as sent -> {args.history}")


if __name__ == "__main__":
    main()
