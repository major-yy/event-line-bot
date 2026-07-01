import argparse
import csv
import datetime as dt
import json
from pathlib import Path

from collect_events import next_weekend, overlaps, parse_date_range


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "sources.json"
DEFAULT_EVENTS = ROOT / "data" / "events.json"
DEFAULT_MD = ROOT.parents[1] / "outputs" / "event_score_table.md"
DEFAULT_CSV = ROOT.parents[1] / "outputs" / "event_score_table.csv"


def keyword_hits(words, text):
    return [word for word in words if word in text]


def score_breakdown(event, config):
    text = " ".join(
        str(event.get(k, "")) for k in ["name", "venue", "address", "summary", "prefecture"]
    )
    source_weights = {
        group["name"]: group.get("weight", 1) for group in config.get("source_groups", [])
    }
    source_score = source_weights.get(event.get("source_group"), 0)
    location_score = config.get("location_weights", {}).get(event.get("prefecture", ""), 0)

    prefs = config.get("ranking_preferences", {})
    positives = keyword_hits(prefs.get("positive_keywords", []), text)
    negatives = keyword_hits(prefs.get("negative_keywords", []), text)
    keyword_score = len(positives) * 2 - len(negatives) * 3

    date_score = 0
    date_reasons = []
    date_weights = config.get("date_weights", {})
    if event.get("start_date"):
        date_score += date_weights.get("has_date", 1)
        date_reasons.append("日付あり+1")

    start, end = parse_date_range(
        " ".join(str(event.get(k, "")) for k in ["start_date", "end_date", "name"])
    )
    weekend_start, weekend_end = next_weekend()
    today = dt.date.today()
    if overlaps(start, end, weekend_start, weekend_end):
        date_score += date_weights.get("next_weekend_overlap", 4)
        date_reasons.append("次の週末に開催+4")
    elif start and today <= start <= today + dt.timedelta(days=10):
        date_score += date_weights.get("starts_within_10_days", 2)
        date_reasons.append("10日以内に開始+2")
    elif end and end < today:
        date_score += date_weights.get("already_ended", -20)
        date_reasons.append("終了済み-20")
    elif start and start > today + dt.timedelta(days=30):
        date_score += date_weights.get("starts_after_30_days", -1)
        date_reasons.append("30日より先に開始-1")
    elif not start and not end:
        date_score += date_weights.get("unknown_date", -2)
        date_reasons.append("日付不明-2")

    url_score = 1 if event.get("url") and event["url"] != event.get("source_url") else 0
    return {
        "source_score": source_score,
        "location_score": location_score,
        "keyword_score": keyword_score,
        "date_score": date_score,
        "url_score": url_score,
        "positive_hits": ", ".join(positives),
        "negative_hits": ", ".join(negatives),
        "date_reasons": ", ".join(date_reasons),
    }


def clean_cell(value):
    return str(value or "").replace("|", "/").replace("\n", " ")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    events = json.loads(args.events.read_text(encoding="utf-8"))["events"]

    rows = []
    for event in events:
        parts = score_breakdown(event, config)
        rows.append(
            {
                "score": event.get("score", 0),
                "source_score": parts["source_score"],
                "location_score": parts["location_score"],
                "keyword_score": parts["keyword_score"],
                "date_score": parts["date_score"],
                "url_score": parts["url_score"],
                "prefecture": event.get("prefecture", ""),
                "date": f"{event.get('start_date', '')} ～ {event.get('end_date', '')}",
                "venue": event.get("venue", ""),
                "name": event.get("name", ""),
                "positive_hits": parts["positive_hits"],
                "negative_hits": parts["negative_hits"],
                "date_reasons": parts["date_reasons"],
                "url": event.get("url", ""),
            }
        )

    rows.sort(key=lambda row: row["score"], reverse=True)
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.csv.parent.mkdir(parents=True, exist_ok=True)

    with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# イベント候補スコア表",
        "",
        f"候補数: {len(rows)}",
        "",
        "|順位|総合|場所|日付|情報源|キーワード|URL|都県|日程|会場|イベント|加点KW|減点KW|日付理由|",
        "|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|",
    ]
    for index, row in enumerate(rows, start=1):
        link = f"[{clean_cell(row['name'])}]({row['url']})" if row["url"] else clean_cell(row["name"])
        lines.append(
            "|"
            + "|".join(
                [
                    str(index),
                    str(row["score"]),
                    str(row["location_score"]),
                    str(row["date_score"]),
                    str(row["source_score"]),
                    str(row["keyword_score"]),
                    str(row["url_score"]),
                    clean_cell(row["prefecture"]),
                    clean_cell(row["date"]),
                    clean_cell(row["venue"]),
                    link,
                    clean_cell(row["positive_hits"]),
                    clean_cell(row["negative_hits"]),
                    clean_cell(row["date_reasons"]),
                ]
            )
            + "|"
        )
    args.md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.md}")
    print(f"wrote {args.csv}")


if __name__ == "__main__":
    main()
