import argparse
import hashlib
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


def verify_signature(channel_secret, body, signature):
    if not channel_secret:
        return True
    digest = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = __import__("base64").b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature or "")


class Handler(BaseHTTPRequestHandler):
    channel_secret = ""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        signature = self.headers.get("x-line-signature", "")
        if not verify_signature(self.channel_secret, body, signature):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"invalid signature")
            return

        payload = json.loads(body.decode("utf-8"))
        print("\nReceived LINE webhook:")
        for event in payload.get("events", []):
            source = event.get("source", {})
            user_id = source.get("userId", "")
            event_type = event.get("type", "")
            message_text = (event.get("message") or {}).get("text", "")
            print(json.dumps(
                {
                    "event_type": event_type,
                    "user_id": user_id,
                    "message_text": message_text,
                },
                ensure_ascii=False,
                indent=2,
            ))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    Handler.channel_secret = os.getenv("LINE_CHANNEL_SECRET", "").strip()
    server = HTTPServer((args.host, args.port), Handler)
    print(f"Listening on http://{args.host}:{args.port}/")
    print("Expose this URL with ngrok/cloudflared and set it as the LINE webhook URL.")
    print("Ask each friend to send any message. Copy the printed user_id values.")
    server.serve_forever()


if __name__ == "__main__":
    main()
