import argparse
import datetime as dt
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = ROOT / "data" / "events.json"
DEFAULT_OUT = ROOT / "data" / "line_message.txt"
DEFAULT_HISTORY = ROOT / "data" / "sent_history.json"
DEFAULT_SELECTED = ROOT / "data" / "selected_events.json"


def compact(value, limit):
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def clean_title(value):
    value = value or "名称未取得"
    value = value.strip()
    value = __import__("re").sub(
        r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\s*(-\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})?\s*",
        "",
        value,
        flags=__import__("re").I,
    )
    value = __import__("re").sub(
        r"\s*\d{4}[./]\d{1,2}[./]\d{1,2}\(.+?\)\s*～?\s*(\d{1,2}/\d{1,2}\(.+?\))?\s*$",
        "",
        value,
    )
    return value.strip() or "名称未取得"


def display_venue(event):
    venue = (event.get("venue") or "").strip()
    address = (event.get("address") or "").strip()
    if venue:
        return compact(venue, 36)
    if address:
        return compact(address, 36)
    return "公式URLで確認"


def display_address(event):
    address = (event.get("address") or "").strip()
    if address:
        return compact(address, 36)
    prefecture = (event.get("prefecture") or "").strip()
    return prefecture or "住所は公式URLで確認"


def load_seen_ids(path):
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["id"] for item in data.get("sent_events", []) if item.get("id")}


def select_events(events, seen_ids, limit=10, only_new=True):
    selected = []
    for event in events:
        if only_new and event.get("id") in seen_ids:
            continue
        selected.append(event)
        if len(selected) >= limit:
            break
    return selected


def render(events, limit=10):
    lines = ["今週の1都3県イベント候補", ""]
    if not events:
        lines.append("新しく見つかったイベント候補はありません。")
        lines.append("")
        lines.append("※既出イベントは再通知しない設定です。")
        return "\n".join(lines).strip() + "\n"
    for index, event in enumerate(events[:limit], start=1):
        title = compact(clean_title(event.get("name", "名称未取得")), 48)
        if event.get("start_date_iso") and event.get("end_date_iso"):
            date = f"{event['start_date_iso']} ～ {event['end_date_iso']}"
        else:
            date = event.get("start_date") or "日程は公式URLで確認"
        venue = display_venue(event)
        lines.append(f"{index}. 🎪 {title}")
        lines.append(f"📅 {date}")
        lines.append(f"📍 {compact(venue, 36)}")
        lines.append(f"🏠 {display_address(event)}")
        if event.get("image_url"):
            lines.append(f"🖼 {event.get('image_url')}")
        lines.append(f"🔗 {event.get('url')}")
        lines.append("")
    lines.append("※開催状況・料金は行く前に公式URLで確認してね。")
    return "\n".join(lines).strip() + "\n"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--selected-out", type=Path, default=DEFAULT_SELECTED)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--include-seen", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.infile.read_text(encoding="utf-8"))
    seen_ids = load_seen_ids(args.history)
    selected = select_events(data.get("events", []), seen_ids, args.limit, not args.include_seen)
    message = render(selected, args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(message, encoding="utf-8")
    args.selected_out.parent.mkdir(parents=True, exist_ok=True)
    args.selected_out.write_text(
        json.dumps(
            {
                "selected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "events": selected,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(message)


if __name__ == "__main__":
    main()
