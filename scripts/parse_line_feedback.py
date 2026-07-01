import argparse
import json
import re
import sys
import unicodedata


ACTION_ALIASES = {
    "行く": "go",
    "いく": "go",
    "イク": "go",
    "行きたい": "want",
    "いきたい": "want",
    "気になる": "want",
}


def normalize_text(text):
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("　", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_feedback(text):
    normalized = normalize_text(text)
    if not normalized:
        return None

    match = re.match(r"^(\d{1,2})\s*[\.\)。、,:：-]?\s*(.+?)\s*$", normalized)
    if not match:
        return None

    event_number = int(match.group(1))
    action_text = re.sub(r"\s+", "", match.group(2))
    action = ACTION_ALIASES.get(action_text)
    if not action:
        return None

    return {
        "event_number": event_number,
        "action": action,
        "action_label": "行く" if action == "go" else "行きたい",
        "normalized_text": normalized,
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    args = parser.parse_args()
    parsed = parse_feedback(args.text)
    print(json.dumps(parsed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
