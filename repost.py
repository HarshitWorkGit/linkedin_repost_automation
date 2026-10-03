"""Publish the next queued LinkedIn post to Facebook and Instagram.

The queue is ``data/linkedin_posts.json``. This module selects one record,
downloads its first image, shows a preview, and publishes only after the
operator types APPROVE.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from facebook_publisher import publish_to_facebook
from instagram_publisher import publish_to_instagram
from linkedin_extractor import LinkedInPost, build_linkedin_post
from post_store import get_next_post, mark_published

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
GENERATED_DIR = PROJECT_ROOT / "generated"
APPROVAL_TOKEN = "APPROVE"

_IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


@dataclass(frozen=True)
class RepostPreview:
    """What the operator reviews before anything is published."""

    source_url: str
    caption: str
    image_path: Path | None


def prepare_preview(post: LinkedInPost) -> RepostPreview:
    """Build the Facebook and Instagram preview from an extracted post.

    TODO: Format platform-specific captions if Facebook and Instagram need
    different text later. Both platforms currently share the LinkedIn caption.
    """
    return RepostPreview(
        source_url=post.source_url,
        caption=post.caption,
        image_path=post.image_path,
    )


def require_explicit_approval(preview: RepostPreview) -> bool:
    """Show the preview and continue only after an explicit APPROVE.

    Any other answer, including Enter, leaves both platforms unpublished.
    A non-interactive session cannot approve a publish.
    """
    image_display = str(preview.image_path) if preview.image_path else "(no image)"
    print("Preview")
    print(f"  LinkedIn URL: {preview.source_url}")
    print(f"  Caption: {preview.caption}")
    print(f"  Image: {image_display}")
    print("  Facebook: same caption and image")
    print("  Instagram: same caption and image")

    if not sys.stdin.isatty():
        print("Publish skipped. Approval requires an interactive terminal.")
        return False

    answer = input(f"Type {APPROVAL_TOKEN} to publish to Facebook and Instagram: ")
    if answer.strip() != APPROVAL_TOKEN:
        print("Publish skipped. Approval was not granted.")
        return False
    return True


def publish_approved(preview: RepostPreview) -> None:
    """Hand an approved preview to Facebook and then Instagram.

    TODO: Record each platform result once the publishers return post ids.
    """
    if preview.image_path is None:
        raise ValueError("Cannot publish without a local image.")

    errors: list[str] = []
    for name, publish in (
        ("Facebook", publish_to_facebook),
        ("Instagram", publish_to_instagram),
    ):
        try:
            publish(preview.image_path, preview.caption)
        except NotImplementedError as exc:
            errors.append(f"{name}: {exc}")

    if errors:
        raise NotImplementedError(" ".join(errors))


def download_post_image(
    image_url: str,
    post_id: str,
    directory: Path | None = None,
) -> Path:
    """Download the first LinkedIn image into ``generated/``."""
    if not image_url.lower().startswith("https://"):
        raise ValueError("Post image URL must use https.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", post_id):
        raise ValueError(f"Post id cannot be used as a file name: {post_id}")

    destination_dir = directory or GENERATED_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)

    request = urllib.request.Request(
        image_url,
        headers={"User-Agent": "linkedin-repost-queue/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not download the LinkedIn image: {exc}") from exc

    if not data:
        raise ValueError("Downloaded LinkedIn image was empty.")

    extension = _image_extension(content_type, data)
    if extension is None:
        raise ValueError("Downloaded LinkedIn image was not a recognized image.")

    destination = destination_dir / f"{post_id}{extension}"
    destination.write_bytes(data)
    return destination


def run(post_id: str | None = None, posts_path: Path | None = None) -> int:
    """Select one queued post, preview it, and publish only after approval.

    Steps:
        1. Load the JSON queue and select one status=new post.
        2. Download its first image under generated/.
        3. Prepare the preview.
        4. Require explicit approval.
        5. Publish to Facebook and Instagram only after approval.
        6. Mark the record published only when both publishes return.
    """
    load_dotenv(ENV_PATH)

    queued = get_next_post(post_id=post_id, path=posts_path)
    if queued is None:
        if post_id:
            print(f"No eligible post found for id {post_id}. Nothing to publish.")
        else:
            print("No eligible post found. Nothing to publish.")
        return 0

    print(f"Selected post {queued.id}")
    image_path = download_post_image(queued.image_url, queued.id)
    post = build_linkedin_post(
        url=queued.linkedin_url,
        caption=queued.content,
        image_path=image_path,
    )
    preview = prepare_preview(post)

    if not require_explicit_approval(preview):
        return 0

    publish_approved(preview)
    mark_published(queued.id, path=posts_path)
    print(f"Published post {queued.id}. Status set to published.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Publish the next new LinkedIn post from data/linkedin_posts.json "
            "to Facebook and Instagram after explicit approval."
        )
    )
    parser.add_argument(
        "--post-id",
        help=(
            "Optional queue record id. When omitted, the oldest status=new "
            "post is used."
        ),
    )
    args = parser.parse_args(argv)
    selected_id = args.post_id.strip() if args.post_id else None

    try:
        return run(post_id=selected_id)
    except NotImplementedError as exc:
        print(f"Not implemented: {exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError, OSError, RuntimeError, TimeoutError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _image_extension(content_type: str, data: bytes) -> str | None:
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type in _IMAGE_EXTENSIONS:
        return _IMAGE_EXTENSIONS[media_type]
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    return None


if __name__ == "__main__":
    raise SystemExit(main())
