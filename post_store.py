"""JSON file queue for LinkedIn posts.

``data/linkedin_posts.json`` is the source of truth. This module loads that
file, selects one eligible record, and updates its status. Nested Airbyte
fields stay JSON strings. Nothing here talks to Facebook or Instagram.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_POSTS_PATH = PROJECT_ROOT / "data" / "linkedin_posts.json"

_MISSING_DATE = "9999-12-31T23:59:59Z"


@dataclass(frozen=True)
class QueuedPost:
    """One eligible queue record, ready for preview and publishing."""

    id: str
    content: str
    linkedin_url: str
    image_url: str
    posted_at: str


def load_posts(path: Path | None = None) -> list[dict[str, Any]]:
    """Load the post queue.

    Nested fields such as ``postimages`` and ``postedat`` are left as JSON
    strings, matching the file written by the source sync.
    """
    posts_path = Path(path) if path is not None else DEFAULT_POSTS_PATH
    with posts_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{posts_path} must contain a JSON list of posts.")
    return data


def get_next_post(
    post_id: str | None = None,
    path: Path | None = None,
) -> QueuedPost | None:
    """Return one eligible post, or ``None`` when the queue has nothing to publish.

    Eligible records have ``status == "new"``, non-empty ``content`` and
    ``linkedinurl``, and at least one image URL in ``postimages``.

    Without ``post_id``, the oldest ``postedat.date`` wins. With ``post_id``,
    that record is returned only when it is eligible.
    """
    eligible = [record for record in load_posts(path) if _is_eligible(record)]
    if post_id is not None:
        wanted = str(post_id)
        eligible = [record for record in eligible if str(record.get("id")) == wanted]
    eligible.sort(key=_sort_key)
    if not eligible:
        return None
    return _to_queued_post(eligible[0])


def mark_published(post_id: str, path: Path | None = None) -> None:
    """Set one record's status to ``published`` and leave every other field unchanged."""
    posts_path = Path(path) if path is not None else DEFAULT_POSTS_PATH
    posts = load_posts(posts_path)
    wanted = str(post_id)
    found = False
    for record in posts:
        if str(record.get("id")) == wanted:
            record["status"] = "published"
            found = True
            break
    if not found:
        raise ValueError(f"Post id was not found: {post_id}")
    _atomic_write(posts_path, posts)


def _is_eligible(record: dict[str, Any]) -> bool:
    if record.get("status") != "new":
        return False
    content = record.get("content")
    linkedin_url = record.get("linkedinurl")
    if not isinstance(content, str) or not content.strip():
        return False
    if not isinstance(linkedin_url, str) or not linkedin_url.strip():
        return False
    return _first_image_url(record) is not None


def _to_queued_post(record: dict[str, Any]) -> QueuedPost:
    image_url = _first_image_url(record)
    if image_url is None:
        raise ValueError(f"Post {record.get('id')} has no image URL.")
    return QueuedPost(
        id=str(record["id"]),
        content=str(record["content"]).strip(),
        linkedin_url=str(record["linkedinurl"]).strip(),
        image_url=image_url,
        posted_at=_posted_at(record),
    )


def _first_image_url(record: dict[str, Any]) -> str | None:
    images = _parse_json_value(record.get("postimages"))
    if not isinstance(images, list) or not images:
        return None
    first = images[0]
    if not isinstance(first, dict):
        return None
    url = first.get("url")
    if not isinstance(url, str) or not url.strip():
        return None
    return url.strip()


def _posted_at(record: dict[str, Any]) -> str:
    posted = _parse_json_value(record.get("postedat"))
    if not isinstance(posted, dict):
        return ""
    date = posted.get("date")
    if not isinstance(date, str):
        return ""
    return date


def _sort_key(record: dict[str, Any]) -> tuple[str, str]:
    return (_posted_at(record) or _MISSING_DATE, str(record.get("id", "")))


def _parse_json_value(value: Any) -> Any:
    """Parse a JSON string field. Invalid JSON becomes ``None`` so the record is skipped."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _atomic_write(path: Path, posts: list[dict[str, Any]]) -> None:
    """Replace the queue file only after the new contents are fully written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = None
    temporary_path: str | None = None
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        )
        temporary_path = handle.name
        json.dump(posts, handle, ensure_ascii=False, indent="\t")
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        handle = None
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if handle is not None:
            handle.close()
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
