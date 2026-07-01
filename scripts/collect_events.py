import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "sources.json"
DEFAULT_OUT = ROOT / "data" / "events.json"
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def fetch_text(url, timeout=20):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "personal-weekly-event-bot/0.1 (+private LINE notification)"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        raw = res.read()
        charset = res.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def strip_tags(value):
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.I)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def absolute_url(base, href):
    if not href:
        return base
    return urllib.parse.urljoin(base, href)


def extract_jsonld_events(page_text, source):
    events = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
        page_text,
        flags=re.I,
    ):
        payload = html.unescape(match.group(1)).strip()
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        for item in stack:
            if isinstance(item, dict) and "@graph" in item:
                stack.extend(item["@graph"])
                continue
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type")
            if isinstance(item_type, list):
                is_event = "Event" in item_type
            else:
                is_event = item_type == "Event"
            if not is_event:
                continue
            location = item.get("location") or {}
            if isinstance(location, dict):
                venue = location.get("name") or ""
                address = location.get("address") or ""
                if isinstance(address, dict):
                    address = format_address(address)
            else:
                venue = str(location)
                address = ""
            events.append(
                normalize_event(
                    {
                        "name": item.get("name", ""),
                        "prefecture": source.get("prefecture", ""),
                        "venue": venue,
                        "address": address,
                        "start_date": item.get("startDate", ""),
                        "end_date": item.get("endDate", ""),
                        "summary": strip_tags(str(item.get("description", "")))[:180],
                        "url": absolute_url(source["url"], item.get("url") or ""),
                        "image_url": extract_image_url(item, source["url"]),
                        "source_name": source["name"],
                        "source_url": source["url"],
                    }
                )
            )
    return events


def extract_link_candidates(page_text, source):
    events = []
    link_re = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', re.I)
    event_words = (
        r"(イベント|祭|フェス|マルシェ|花火|展示|展覧|展|マーケット|"
        r"グルメ|開催|ライブ|音楽|クラフト|イルミネーション|ビア|ビール|映画|体験)"
    )
    date_words = (
        r"(\d{1,2}/\d{1,2}|\d{1,2}月\d{1,2}日|"
        r"\d{4}年|\d{4}/\d{1,2}/\d{1,2}|\d{4}\.\d{1,2}\.\d{1,2}|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    )
    for href, label_html in link_re.findall(page_text):
        label = strip_tags(label_html)
        if len(label) < 4 or len(label) > 80:
            continue
        url = absolute_url(source["url"], href)
        if not is_event_detail_url(url):
            continue
        if not (re.search(event_words, label) or re.search(date_words, label, re.I)):
            continue
        events.append(
            normalize_event(
                {
                    "name": label,
                    "prefecture": source.get("prefecture", ""),
                    "venue": "",
                    "address": "",
                    "start_date": guess_date(label),
                    "end_date": "",
                    "summary": "",
                    "url": url,
                    "image_url": "",
                    "source_name": source["name"],
                    "source_url": source["url"],
                }
            )
        )
    return events


def format_address(address):
    keys = [
        "addressRegion",
        "addressLocality",
        "streetAddress",
        "postalCode",
        "addressCountry",
    ]
    parts = [str(address.get(key, "")).strip() for key in keys if address.get(key)]
    if parts:
        return " ".join(parts)
    return " ".join(
        str(value).strip()
        for key, value in address.items()
        if value and not str(key).startswith("@")
    )


def extract_image_url(item, base_url):
    image = item.get("image")
    if isinstance(image, str):
        return absolute_url(base_url, image)
    if isinstance(image, list):
        for candidate in image:
            if isinstance(candidate, str):
                return absolute_url(base_url, candidate)
            if isinstance(candidate, dict) and candidate.get("url"):
                return absolute_url(base_url, candidate["url"])
    if isinstance(image, dict) and image.get("url"):
        return absolute_url(base_url, image["url"])
    return ""


def is_event_detail_url(url):
    lowered = url.lower()
    excluded = [
        "/story/guide/",
        "/see-and-do/",
        "/travel-directory/",
        "/gourmet",
        "/restaurants",
        "/category",
        "/search",
        "/result/",
        "#",
    ]
    if any(part in lowered for part in excluded):
        return False
    included = ["/event/", "/events/", "event-", "events-", "tokyotouristinfo"]
    return any(part in lowered for part in included)


def guess_date(text):
    patterns = [
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}",
        r"\d{4}\.\d{1,2}\.\d{1,2}",
        r"\d{4}[/-]\d{1,2}[/-]\d{1,2}",
        r"\d{4}年\d{1,2}月\d{1,2}日",
        r"\d{1,2}月\d{1,2}日",
        r"\d{1,2}/\d{1,2}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(0)
    return ""


def normalize_event(event):
    name = re.sub(r"\s+", " ", event.get("name", "")).strip()
    url = event.get("url") or event.get("source_url", "")
    key = hashlib.sha1(f"{name}|{url}".encode("utf-8")).hexdigest()[:16]
    event["id"] = key
    event["name"] = name
    event["url"] = url
    start, end = parse_date_range(
        " ".join(str(event.get(k, "")) for k in ["start_date", "end_date", "name"])
    )
    event["start_date_iso"] = start.isoformat() if start else ""
    event["end_date_iso"] = end.isoformat() if end else ""
    event["collected_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return event


def is_publishable_event(event):
    if event.get("url") == event.get("source_url"):
        return False
    if event.get("name", "").strip() in {"イベント", "イベントトップ"}:
        return False
    text = " ".join(str(event.get(k, "")) for k in ["name", "url", "summary"])
    blocked = [
        "イベントカレンダー",
        "イベントスペース",
        "展覧会トップ",
        "展覧会検索",
        "現在地周辺の展覧会",
        "新着展覧会",
        "人気の展覧会",
        "ビール・ビアガーデン",
        "展示・展覧会",
        "体験・遊び",
        "没入体験・イマーシブ",
        "イベントの詳細を見る",
        "公演・イベントを見る",
        "半券サービス",
        "セゾンの木曜日",
        "宿泊プラン",
        "移動販売車",
        "テイクアウト",
        "デリバリー",
        "/event/calendar",
        "/facilities/event",
        "/event/takeout",
        "/events?category",
        "/events?prefecture",
    ]
    return not any(word in text for word in blocked)


def parse_date_range(text, today=None):
    today = today or dt.date.today()
    english_dates = re.findall(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),\s+(\d{4})",
        text,
        re.I,
    )
    if english_dates:
        parsed = [
            dt.date(int(year), MONTHS[month[:3].lower()], int(day))
            for month, day, year in english_dates
        ]
        return min(parsed), max(parsed)

    full_numeric = re.findall(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text)
    if full_numeric:
        parsed = [dt.date(int(y), int(m), int(d)) for y, m, d in full_numeric]
        return min(parsed), max(parsed)

    dotted_numeric = re.findall(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", text)
    if dotted_numeric:
        parsed = [dt.date(int(y), int(m), int(d)) for y, m, d in dotted_numeric]
        return min(parsed), max(parsed)

    japanese_full = re.findall(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if japanese_full:
        parsed = [dt.date(int(y), int(m), int(d)) for y, m, d in japanese_full]
        return min(parsed), max(parsed)

    month_day = re.findall(r"(?<!\d)(\d{1,2})[月/](\d{1,2})(?:日)?", text)
    if month_day:
        parsed = []
        for month, day in month_day:
            candidate = dt.date(today.year, int(month), int(day))
            if candidate < today - dt.timedelta(days=30):
                candidate = dt.date(today.year + 1, int(month), int(day))
            parsed.append(candidate)
        return min(parsed), max(parsed)
    return None, None


def next_weekend(today=None):
    today = today or dt.date.today()
    days_until_saturday = (5 - today.weekday()) % 7
    saturday = today + dt.timedelta(days=days_until_saturday)
    sunday = saturday + dt.timedelta(days=1)
    return saturday, sunday


def overlaps(start, end, window_start, window_end):
    if not start:
        return False
    end = end or start
    return start <= window_end and end >= window_start


def score_event(event, config, source_weight):
    text = " ".join(
        str(event.get(k, "")) for k in ["name", "venue", "address", "summary", "prefecture"]
    )
    score = source_weight
    score += config.get("location_weights", {}).get(event.get("prefecture", ""), 0)
    prefs = config.get("ranking_preferences", {})
    for word in prefs.get("positive_keywords", []):
        if word in text:
            score += 2
    for word in prefs.get("negative_keywords", []):
        if word in text:
            score -= 3
    date_weights = config.get("date_weights", {})
    if event.get("start_date"):
        score += date_weights.get("has_date", 1)
    start, end = parse_date_range(
        " ".join(str(event.get(k, "")) for k in ["start_date", "end_date", "name"])
    )
    weekend_start, weekend_end = next_weekend()
    today = dt.date.today()
    if overlaps(start, end, weekend_start, weekend_end):
        score += date_weights.get("next_weekend_overlap", 4)
    elif start and today <= start <= today + dt.timedelta(days=10):
        score += date_weights.get("starts_within_10_days", 2)
    elif end and end < today:
        score += date_weights.get("already_ended", -20)
    elif start and start > today + dt.timedelta(days=30):
        score += date_weights.get("starts_after_30_days", -1)
    elif not start and not end:
        score += date_weights.get("unknown_date", -2)
    if event.get("url") and event["url"] != event.get("source_url"):
        score += 1
    return score


def dedupe(events):
    seen = {}
    for event in events:
        fingerprint = re.sub(r"\W+", "", event["name"].lower())[:40]
        fingerprint += "|" + event.get("prefecture", "")
        old = seen.get(fingerprint)
        if old is None or event.get("score", 0) > old.get("score", 0):
            seen[fingerprint] = event
    return list(seen.values())


def collect(config):
    events = []
    errors = []
    for group in config["source_groups"]:
        for source in group["sources"]:
            for page_source in expand_source_pages(source):
                try:
                    page_text = fetch_text(page_source["url"])
                    found = extract_jsonld_events(page_text, page_source)
                    found.extend(extract_link_candidates(page_text, page_source))
                    for event in found:
                        event["score"] = score_event(event, config, group.get("weight", 1))
                        event["base_score"] = event["score"]
                        event["source_group"] = group["name"]
                    events.extend(found)
                except (urllib.error.URLError, TimeoutError, UnicodeError) as exc:
                    errors.append(
                        {
                            "source": page_source["name"],
                            "url": page_source["url"],
                            "error": str(exc),
                        }
                    )
    events = dedupe(events)
    events = [event for event in events if is_publishable_event(event)]
    events.sort(key=lambda item: item.get("score", 0), reverse=True)
    return {"events": events, "errors": errors, "count": len(events)}


def expand_source_pages(source):
    max_pages = int(source.get("max_pages", 1) or 1)
    for page in range(1, max_pages + 1):
        page_source = dict(source)
        page_source["url"] = paged_url(source, page)
        yield page_source


def paged_url(source, page):
    url = source["url"]
    if page <= 1:
        return url
    template = source.get("page_url_template")
    base = url.rstrip("/")
    if template:
        return template.format(base=base, page=page)
    if base.endswith(".html"):
        stem = base[:-5]
        return f"{stem}/{page}.html"
    return f"{base}/{page}.html"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = collect(config)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"collected {result['count']} candidate events -> {args.out}")
    if result["errors"]:
        print("source errors:", file=sys.stderr)
        for error in result["errors"]:
            print(f"- {error['source']}: {error['error']}", file=sys.stderr)


if __name__ == "__main__":
    main()
