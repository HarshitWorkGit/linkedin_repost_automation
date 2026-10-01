"""Extract a LinkedIn post caption and image.

This module defines the extraction interface used by ``repost.py``.
Browser and OpenClaw extraction are not implemented. This module does not
make network requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "generated"


@dataclass(frozen=True)
class LinkedInPost:
    """Caption and local image extracted from one LinkedIn post URL."""

    source_url: str
    caption: str
    image_path: Path | None


def extract_linkedin_post(
    url: str,
    output_dir: Path | None = None,
) -> LinkedInPost:
    """Extract the caption and image for a LinkedIn post and save the image locally.

    Args:
        url: Public or authenticated LinkedIn post URL supplied by the user.
        output_dir: Directory for the saved image. Defaults to ``generated/``.

    Returns:
        A ``LinkedInPost`` with the caption text and the local image path.

    Raises:
        NotImplementedError: Extraction is not implemented in this scaffold.
        ValueError: ``url`` is empty.

    Future browser/OpenClaw extraction, not called yet:

    1. ``_open_linkedin_post`` opens the LinkedIn URL.
    2. ``_extract_visible_caption`` reads the visible post caption.
    3. ``_identify_post_image`` identifies the post image.
    4. ``_download_post_image`` downloads that image into ``output_dir``.
    5. This function returns ``LinkedInPost``.
    """
    if not url or not url.strip():
        raise ValueError("A LinkedIn post URL is required.")

    destination = output_dir if output_dir is not None else DEFAULT_OUTPUT_DIR
    destination.mkdir(parents=True, exist_ok=True)

    # TODO: OpenClaw/browser extraction. Do not call these until that work exists.
    # 1. page = _open_linkedin_post(url)
    # 2. caption = _extract_visible_caption(page)
    # 3. image_source = _identify_post_image(page)
    # 4. image_path = _download_post_image(image_source, destination)
    # 5. return LinkedInPost(source_url=url.strip(), caption=caption, image_path=image_path)

    raise NotImplementedError(
        "LinkedIn extraction is not implemented yet. "
        f"URL was accepted and output directory is ready: {destination}"
    )


def _open_linkedin_post(url: str) -> object:
    """Open a LinkedIn post so later steps can read it.

    TODO: Open ``url`` through the browser/OpenClaw session.
    TODO: Return the open post context for caption and image extraction.
    TODO: Do not add network, Selenium, Playwright, or browser code yet.
    """
    raise NotImplementedError(f"Opening a LinkedIn post is not implemented yet: {url}")


def _extract_visible_caption(page: object) -> str:
    """Read the caption that is visible on the open LinkedIn post.

    TODO: Read the visible post caption from ``page``.
    TODO: Return that caption as plain text.
    TODO: Do not add selectors or a LinkedIn API call yet.
    """
    raise NotImplementedError(
        "Extracting the visible LinkedIn caption is not implemented yet."
    )


def _identify_post_image(page: object) -> str:
    """Identify the image that belongs to the open LinkedIn post.

    TODO: Identify the post image from ``page``.
    TODO: Return a reference the download step can use.
    TODO: Do not add selectors or a LinkedIn API call yet.
    """
    raise NotImplementedError(
        "Identifying the LinkedIn post image is not implemented yet."
    )


def _download_post_image(image_source: str, output_dir: Path) -> Path:
    """Download the identified post image into ``output_dir``.

    TODO: Download ``image_source`` into ``output_dir``.
    TODO: Return the local image ``Path`` for ``LinkedInPost.image_path``.
    TODO: Do not download anything yet.
    """
    raise NotImplementedError(
        "Downloading the LinkedIn post image is not implemented yet: "
        f"{image_source} -> {output_dir}"
    )
