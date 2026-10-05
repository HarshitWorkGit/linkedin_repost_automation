"""Publish selected LinkedIn queue posts to the Synergy AI website."""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from post_store import QueuedPost


PROJECT_ROOT = Path(__file__).resolve().parent
WEBSITE_IMAGES_DIR = PROJECT_ROOT / "images"

WEBSITE_API_URL = os.getenv(
    "WEBSITE_API_URL",
    "http://127.0.0.1:5174/api/posts",
)

TIMEOUT = 15


def publish_to_website(
    post: QueuedPost,
    image_path: Path,
) -> None:
    """Publish a queued post and its image to the website."""

    WEBSITE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    extension = image_path.suffix.lower()
    if not extension:
        raise ValueError("Website image must have a file extension.")

    website_image_path = WEBSITE_IMAGES_DIR / f"{post.id}{extension}"
    shutil.copy2(image_path, website_image_path)

    payload = {
        "id": post.id,
        "content": post.content,
        "image_url": f"/images/{website_image_path.name}",
        "linkedin_url": post.linkedin_url,
        "posted_at": post.posted_at,
    }

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        WEBSITE_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=TIMEOUT,
        ) as response:
            if response.status != 201:
                raise RuntimeError(
                    f"Website API returned HTTP {response.status}."
                )

    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            website_image_path.unlink(missing_ok=True)
            print(
                f"Website already contains post {post.id}. "
                "Skipping duplicate."
            )
            return

        website_image_path.unlink(missing_ok=True)

        raise RuntimeError(
            f"Website API returned HTTP {exc.code}."
        ) from exc

    except urllib.error.URLError as exc:
        website_image_path.unlink(missing_ok=True)

        raise RuntimeError(
            f"Could not reach website API: {exc}"
        ) from exc