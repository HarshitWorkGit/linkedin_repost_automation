"""Create or reuse a queued LinkedIn post from extracted JSON input."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from post_store import DEFAULT_POSTS_PATH, _atomic_write, load_posts


_SAFE_ID = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class ExtractedPost:
    id: str
    linkedin_url: str
    caption: str
    image_url: str
    posted_at: str
    timestamp_ms: int


def load_extracted_post(path: Path) -> ExtractedPost:
    """Load and validate one extracted LinkedIn post JSON file."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Input must be a JSON object.")

    post_id = _required_string(payload, "id")
    if _SAFE_ID.fullmatch(post_id) is None:
        raise ValueError("id must contain only letters, numbers, underscores, or hyphens.")

    linkedin_url = _required_string(payload, "linkedin_url")
    _validate_linkedin_url(linkedin_url)

    caption = _required_string(payload, "caption")

    image_url = _required_string(payload, "image_url")
    _validate_https_url(image_url, "image_url")

    posted_at = _required_string(payload, "posted_at")
    timestamp_ms = _parse_posted_at(posted_at)

    return ExtractedPost(
        id=post_id,
        linkedin_url=linkedin_url,
        caption=caption,
        image_url=image_url,
        posted_at=posted_at,
        timestamp_ms=timestamp_ms,
    )


def queue_post(
    extracted: ExtractedPost,
    posts_path: Path = DEFAULT_POSTS_PATH,
) -> tuple[str, str, bool]:
    """Create a new queue record or reuse an existing one.

    Returns ``(post_id, status, created)``.
    """
    posts = load_posts(posts_path) if posts_path.exists() else []
    existing = _find_existing(posts, extracted)
    if existing is not None:
        return str(existing.get("id", "")), str(existing.get("status", "")), False

    posts.append(_to_queue_record(extracted))
    _atomic_write(posts_path, posts)
    return extracted.id, "new", True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create or reuse a LinkedIn post queue record from extracted JSON."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to extracted post JSON.",
    )
    parser.add_argument(
        "--posts-path",
        type=Path,
        default=DEFAULT_POSTS_PATH,
        help="Queue JSON path. Defaults to data/linkedin_posts.json.",
    )
    args = parser.parse_args(argv)

    try:
        extracted = load_extracted_post(args.input)
        post_id, status, created = queue_post(extracted, posts_path=args.posts_path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    action = "created" if created else "reused"
    print(f"Queue record {action}: id={post_id} status={status}")
    return 0


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string.")
    return value.strip()


def _validate_linkedin_url(value: str) -> None:
    parsed = urlparse(value)
    host = parsed.netloc.lower()
    if parsed.scheme != "https" or not (
        host == "linkedin.com" or host.endswith(".linkedin.com")
    ):
        raise ValueError("linkedin_url must be an HTTPS LinkedIn URL.")


def _validate_https_url(value: str, field: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field} must be an HTTPS URL.")


def _parse_posted_at(value: str) -> int:
    if "T" not in value:
        raise ValueError("posted_at must be an ISO-8601 datetime string.")

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("posted_at must be an ISO-8601 datetime string.") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return int(parsed.timestamp() * 1000)


def _find_existing(
    posts: list[dict[str, Any]],
    extracted: ExtractedPost,
) -> dict[str, Any] | None:
    id_match = None
    url_match = None
    for record in posts:
        if not isinstance(record, dict):
            continue
        record_id = str(record.get("id", ""))
        record_url = str(record.get("linkedinurl", "")).strip()
        if record_id == extracted.id:
            id_match = record
        if record_url == extracted.linkedin_url:
            url_match = record

    if id_match is not None and url_match is not None and id_match is not url_match:
        raise ValueError("Input id and LinkedIn URL match different existing records.")

    if id_match is not None:
        existing_url = str(id_match.get("linkedinurl", "")).strip()
        if existing_url and existing_url != extracted.linkedin_url:
            raise ValueError("Input id already exists for a different LinkedIn URL.")
        return id_match

    return url_match


def _to_queue_record(extracted: ExtractedPost) -> dict[str, Any]:
    return {
        "id": extracted.id,
        "content": extracted.caption,
        "linkedinurl": extracted.linkedin_url,
        "postimages": json.dumps(
            [{"url": extracted.image_url}],
            ensure_ascii=False,
        ),
        "postedat": json.dumps(
            {
                "date": extracted.posted_at,
                "timestamp": extracted.timestamp_ms,
                "postedAgoText": "",
                "postedAgoShort": "",
            },
            ensure_ascii=False,
        ),
        "status": "new",
        "type": "post",
    }


if __name__ == "__main__":
    raise SystemExit(main())
