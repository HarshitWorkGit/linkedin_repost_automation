"""Local Synergy AI site and posts API. Python standard library only."""

import json
import os
import tempfile
import threading
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
POSTS_PATH = ROOT / "data" / "posts.json"

HOST = "127.0.0.1"
PORT = 5174
MAX_BODY = 64 * 1024

FIELDS = ("id", "content", "image_url", "linkedin_url", "posted_at")
NONEMPTY = ("id", "content", "image_url", "linkedin_url")

WRITE_LOCK = threading.Lock()


def load_posts():
    with POSTS_PATH.open(encoding="utf-8") as handle:
        posts = json.load(handle)

    if not isinstance(posts, list):
        raise ValueError("data/posts.json must contain a JSON list")

    return posts


def save_posts(posts):
    POSTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=POSTS_PATH.parent,
        prefix=".posts-",
        suffix=".tmp",
    )

    tmp_path = Path(tmp_name)

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            json.dump(
                posts,
                handle,
                indent=2,
                ensure_ascii=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(tmp_path, POSTS_PATH)

    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def parse_posted_at(value):
    if not isinstance(value, str):
        return None

    text = value.strip()

    if "T" not in text:
        return None

    normalized = (
        text[:-1] + "+00:00"
        if text.endswith("Z")
        else text
    )

    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return None

    return text


def validate_post(payload):
    if not isinstance(payload, dict):
        return None, "Expected a JSON object"

    unknown = sorted(set(payload) - set(FIELDS))

    if unknown:
        return None, "Unexpected field: " + ", ".join(unknown)

    missing = [
        field
        for field in FIELDS
        if field not in payload
    ]

    if missing:
        return None, "Missing field: " + ", ".join(missing)

    post = {}

    for field in NONEMPTY:
        value = payload[field]

        if not isinstance(value, str):
            return None, f"{field} must be a string"

        value = value.strip()

        if not value:
            return None, f"{field} must not be empty"

        post[field] = value

    posted_at = parse_posted_at(payload["posted_at"])

    if posted_at is None:
        return None, "posted_at must be an ISO-8601 datetime string"

    post["posted_at"] = posted_at

    return post, None


class SiteHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/posts":
            self.get_posts()
            return

        if (
            path.startswith("/api/")
            or path == "/data"
            or path.startswith("/data/")
        ):
            self.send_json(
                404,
                {"error": "Not found"},
            )
            return

        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path

        if path != "/api/posts":
            self.send_json(
                404,
                {"error": "Not found"},
            )
            return

        self.create_post()

    def get_posts(self):
        try:
            with WRITE_LOCK:
                posts = load_posts()

        except (OSError, json.JSONDecodeError, ValueError):
            self.send_json(
                500,
                {"error": "Could not read posts"},
            )
            return

        self.send_json(200, posts)

    def create_post(self):
        content_type = self.headers.get("Content-Type", "")

        if (
            content_type.split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            self.send_json(
                400,
                {"error": "Content-Type must be application/json"},
            )
            return

        length_header = self.headers.get("Content-Length")

        if length_header is None:
            self.send_json(
                411,
                {"error": "Content-Length is required"},
            )
            return

        try:
            length = int(length_header)
        except ValueError:
            self.send_json(
                400,
                {"error": "Invalid Content-Length"},
            )
            return

        if length < 0 or length > MAX_BODY:
            self.send_json(
                400,
                {"error": "Request body is too large"},
            )
            return

        raw = self.rfile.read(length)

        try:
            payload = json.loads(
                raw.decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(
                400,
                {"error": "Invalid JSON"},
            )
            return

        post, error = validate_post(payload)

        if error:
            self.send_json(
                400,
                {"error": error},
            )
            return

        try:
            with WRITE_LOCK:
                posts = load_posts()

                duplicate = any(
                    isinstance(item, dict)
                    and item.get("id") == post["id"]
                    for item in posts
                )

                if duplicate:
                    self.send_json(
                        409,
                        {"error": "Duplicate id"},
                    )
                    return

                posts.append(post)
                save_posts(posts)

        except (OSError, json.JSONDecodeError, ValueError):
            self.send_json(
                500,
                {"error": "Could not save posts"},
            )
            return

        self.send_json(201, post)

    def send_json(self, status, payload):
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.send_header(
            "Cache-Control",
            "no-store",
        )
        self.end_headers()

        self.wfile.write(body)


def main():
    handler = partial(
        SiteHandler,
        directory=str(ROOT),
    )

    server = HTTPServer(
        (HOST, PORT),
        handler,
    )

    print(
        f"Synergy AI running at http://{HOST}:{PORT}",
        flush=True,
    )

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("\nStopping.")

    finally:
        server.server_close()


if __name__ == "__main__":
    main()