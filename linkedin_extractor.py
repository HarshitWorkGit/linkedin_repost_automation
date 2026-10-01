"""Build a LinkedIn post object from data extracted by OpenClaw.

OpenClaw is responsible for opening LinkedIn, reading the caption,
accessing the post image, and downloading the image.

This module only validates that extracted data and creates the
LinkedInPost object used by the repost workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LinkedInPost:
    """Caption and local image extracted from one LinkedIn post."""

    source_url: str
    caption: str
    image_path: Path


def build_linkedin_post(
    url: str,
    caption: str,
    image_path: str | Path,
) -> LinkedInPost:
    """Build a validated LinkedInPost from OpenClaw extraction results."""

    url = url.strip()
    caption = caption.strip()
    image_path = Path(image_path)

    if not url:
        raise ValueError("A LinkedIn post URL is required.")

    if not caption:
        raise ValueError("LinkedIn post caption is required.")

    if not image_path.exists():
        raise FileNotFoundError(
            f"LinkedIn post image was not found: {image_path}"
        )

    if not image_path.is_file():
        raise ValueError(
            f"LinkedIn post image path is not a file: {image_path}"
        )

    return LinkedInPost(
        source_url=url,
        caption=caption,
        image_path=image_path,
    )