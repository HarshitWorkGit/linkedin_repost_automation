"""Publish an image and caption to a Facebook Page.

This module is a placeholder. It does not call the Graph API.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"

# Read from the environment only. Never hardcode tokens.
FACEBOOK_PAGE_ID_ENV = "FACEBOOK_PAGE_ID"
FACEBOOK_PAGE_ACCESS_TOKEN_ENV = "FACEBOOK_PAGE_ACCESS_TOKEN"


def publish_to_facebook(image_path: Path, caption: str) -> dict[str, str]:
    """Publish one image and caption to Facebook.

    Args:
        image_path: Local image file saved by the LinkedIn extractor.
        caption: Text that should accompany the image.

    Returns:
        A result payload once publishing is implemented. This scaffold never
        returns a successful publish.

    Raises:
        NotImplementedError: Publishing is not implemented.
        ValueError: The image path or caption is missing.

    TODO: Load ``FACEBOOK_PAGE_ID`` and ``FACEBOOK_PAGE_ACCESS_TOKEN`` from ``.env``.
    TODO: Publish the local image and caption with the Facebook Graph API.
    TODO: Return the created post id. Do not call the API in this scaffold.
    """
    load_dotenv(ENV_PATH)

    if image_path is None or not str(image_path).strip():
        raise ValueError("An image path is required to publish to Facebook.")
    if not caption or not caption.strip():
        raise ValueError("A caption is required to publish to Facebook.")

    raise NotImplementedError(
        "Facebook publishing is not implemented yet. No API request was sent."
    )
