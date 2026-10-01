"""Publish a local image and caption to a Facebook Page.

Uses the Graph API photo upload from the tested publisher:
``POST /{page-id}/photos`` with the image as multipart ``source``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"

FACEBOOK_PAGE_ID_ENV = "FACEBOOK_PAGE_ID"
FACEBOOK_PAGE_ACCESS_TOKEN_ENV = "FACEBOOK_PAGE_ACCESS_TOKEN"

GRAPH_API_VERSION = "v26.0"
GRAPH_BASE_URL = "https://graph.facebook.com"
DEFAULT_TIMEOUT = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def load_environment() -> tuple[str, str]:
    """Load and validate Facebook credentials from this project's ``.env``."""
    load_dotenv(ENV_PATH)

    page_id = os.getenv(FACEBOOK_PAGE_ID_ENV)
    page_access_token = os.getenv(FACEBOOK_PAGE_ACCESS_TOKEN_ENV)

    missing = []

    if not page_id:
        missing.append(FACEBOOK_PAGE_ID_ENV)

    if not page_access_token:
        missing.append(FACEBOOK_PAGE_ACCESS_TOKEN_ENV)

    if missing:
        raise ValueError(
            f"Missing required environment variable(s): {', '.join(missing)}"
        )

    return page_id, page_access_token


def build_feed_url(page_id: str) -> str:
    """Build the Facebook Graph API endpoint for publishing page posts."""
    return f"{GRAPH_BASE_URL}/{GRAPH_API_VERSION}/{page_id}/feed"


def build_photo_url(page_id: str) -> str:
    """Build the Facebook Graph API endpoint for publishing images."""
    return f"{GRAPH_BASE_URL}/{GRAPH_API_VERSION}/{page_id}/photos"


def publish_image_post(
    page_id: str,
    access_token: str,
    image_path: str,
    caption: str | None = None,
) -> dict[str, Any]:
    """Publish a single image to a Facebook Page."""
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    url = build_photo_url(page_id)

    data = {
        "access_token": access_token,
    }

    if caption:
        data["caption"] = caption.strip()

    with open(image_path, "rb") as image_file:
        files = {
            "source": image_file,
        }

        logger.info("Publishing Facebook image...")

        response = requests.post(
            url,
            data=data,
            files=files,
            timeout=60,
        )

    if not response.ok:
        print("Facebook API error:")
        print(response.text)
        response.raise_for_status()

    result = response.json()

    return {
        "success": True,
        "type": "image",
        "post_id": result.get("post_id") or result.get("id"),
        "media_id": result.get("id"),
        "response": result,
    }


def publish_text_post(
    page_id: str,
    access_token: str,
    message: str,
) -> dict[str, Any]:
    """Publish a text post to a Facebook Page."""
    if not message or not message.strip():
        raise ValueError("Post message cannot be empty.")

    url = build_feed_url(page_id)

    payload = {
        "message": message.strip(),
        "access_token": access_token,
    }

    logger.info("Publishing Facebook post...")

    response = requests.post(
        url,
        data=payload,
        timeout=DEFAULT_TIMEOUT,
    )

    response.raise_for_status()

    result = response.json()

    return {
        "success": True,
        "type": "text",
        "post_id": result.get("id"),
        "response": result,
    }


def publish_to_facebook(image_path: Path, caption: str) -> dict[str, Any]:
    """Publish one local image and caption to the configured Facebook Page.

    Args:
        image_path: Local image file saved by the LinkedIn extractor.
        caption: Text that should accompany the image.

    Returns:
        ``success``, ``type``, ``post_id``, ``media_id``, and the Graph API
        ``response``.

    Raises:
        ValueError: The image path, caption, or required credentials are missing.
        FileNotFoundError: The image file does not exist.
    """
    load_dotenv(ENV_PATH)

    if image_path is None or not str(image_path).strip():
        raise ValueError("An image path is required to publish to Facebook.")
    if not caption or not caption.strip():
        raise ValueError("A caption is required to publish to Facebook.")

    page_id, access_token = load_environment()

    return publish_image_post(
        page_id=page_id,
        access_token=access_token,
        image_path=str(image_path),
        caption=caption,
    )
