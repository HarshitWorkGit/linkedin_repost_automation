"""Workflow skeleton: LinkedIn post URL to Facebook and Instagram.

Nothing is scraped and nothing is published. Each stage calls a placeholder
that marks where the real implementation will go.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from facebook_publisher import publish_to_facebook
from instagram_publisher import publish_to_instagram
from linkedin_extractor import LinkedInPost, extract_linkedin_post

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
APPROVAL_TOKEN = "APPROVE"


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
    """Hand an approved preview to the Facebook and Instagram placeholders.

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


def run(url: str) -> int:
    """Run the repost workflow for one LinkedIn URL.

    Steps:
        1. Accept the LinkedIn URL.
        2. Extract the caption and image.
        3. Prepare preview data.
        4. Require explicit approval.
        5. Publish to Facebook and Instagram only after approval.
    """
    load_dotenv(ENV_PATH)

    # TODO: Validate that the URL is a LinkedIn post before extraction.
    post = extract_linkedin_post(url.strip())
    preview = prepare_preview(post)
    if not require_explicit_approval(preview):
        return 0

    publish_approved(preview)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Repost a LinkedIn image post to Facebook and Instagram after approval."
    )
    parser.add_argument("url", help="LinkedIn post URL")
    args = parser.parse_args(argv)

    try:
        return run(args.url)
    except NotImplementedError as exc:
        print(f"Not implemented: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
