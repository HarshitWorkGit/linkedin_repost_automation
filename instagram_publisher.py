"""Publish a local image and caption to an Instagram professional account.

Local images follow the tested Quick Tunnel path:

local image -> temporary local HTTP server -> Cloudflare Quick Tunnel
-> public HTTPS image URL -> Instagram media container
-> wait for processing -> publish -> cleanup.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"

INSTAGRAM_BUSINESS_ACCOUNT_ID_ENV = "INSTAGRAM_BUSINESS_ACCOUNT_ID"
INSTAGRAM_ACCESS_TOKEN_ENV = "INSTAGRAM_ACCESS_TOKEN"

GRAPH_API_VERSION = "v26.0"
GRAPH_BASE_URL = "https://graph.instagram.com"

DEFAULT_TIMEOUT = 30
DEFAULT_STATUS_WAIT = 60
STATUS_POLL_INTERVAL = 3

LOCAL_IMAGE_HOST = "127.0.0.1"
LOCAL_IMAGE_PORT = 8000

if os.name == "nt":
    CLOUDFLARED_PATH = os.path.join(
        os.path.expanduser("~"),
        "cloudflared.exe",
    )
else:
    CLOUDFLARED_PATH = shutil.which("cloudflared") or "/usr/local/bin/cloudflared"

CLOUDFLARED_START_TIMEOUT = 30
PUBLIC_URL_CHECK_TIMEOUT = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def start_temporary_image_host(
    image_path: str,
) -> tuple[ThreadingHTTPServer, threading.Thread, subprocess.Popen, str, str]:
    """Temporarily expose a local image through a Cloudflare Quick Tunnel.

    Returns:
        http_server,
        http_thread,
        cloudflared_process,
        public_image_url,
        temporary_directory
    """
    source_path = Path(image_path).resolve()

    if not source_path.is_file():
        raise FileNotFoundError(
            f"Image not found: {source_path}"
        )

    temporary_directory = tempfile.mkdtemp(
        prefix="instagram_image_"
    )

    temporary_image_path = (
        Path(temporary_directory) / source_path.name
    )

    shutil.copy2(
        source_path,
        temporary_image_path,
    )

    logger.info(
        "Starting temporary local image server..."
    )

    handler = partial(
        SimpleHTTPRequestHandler,
        directory=temporary_directory,
    )

    http_server = ThreadingHTTPServer(
        (LOCAL_IMAGE_HOST, LOCAL_IMAGE_PORT),
        handler,
    )

    http_thread = threading.Thread(
        target=http_server.serve_forever,
        daemon=True,
    )

    http_thread.start()

    if not os.path.isfile(CLOUDFLARED_PATH):
        http_server.shutdown()
        http_server.server_close()
        shutil.rmtree(
            temporary_directory,
            ignore_errors=True,
        )
        raise FileNotFoundError(
            "cloudflared.exe was not found at: "
            f"{CLOUDFLARED_PATH}"
        )

    logger.info(
        "Starting temporary Cloudflare Tunnel..."
    )

    cloudflared_process = subprocess.Popen(
        [
            CLOUDFLARED_PATH,
            "tunnel",
            "--url",
            f"http://{LOCAL_IMAGE_HOST}:{LOCAL_IMAGE_PORT}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    public_base_url = None

    start_time = time.time()

    while time.time() - start_time < CLOUDFLARED_START_TIMEOUT:

        if cloudflared_process.stdout is None:
            break

        line = cloudflared_process.stdout.readline()

        if line:
            logger.debug(
                "cloudflared: %s",
                line.strip(),
            )

            match = re.search(
                r"https://[a-zA-Z0-9-]+\.trycloudflare\.com",
                line,
            )

            if match:
                public_base_url = match.group(0)
                break

        if cloudflared_process.poll() is not None:
            break

    if not public_base_url:

        if cloudflared_process.poll() is None:
            cloudflared_process.terminate()

        http_server.shutdown()
        shutil.rmtree(
            temporary_directory,
            ignore_errors=True,
        )

        raise RuntimeError(
            "Could not obtain a public Cloudflare Tunnel URL."
        )

    public_image_url = (
        f"{public_base_url}/{source_path.name}"
    )

    logger.info(
        "Temporary public image URL created."
    )

    logger.info(
        "Image URL: %s",
        public_image_url,
    )

    return (
        http_server,
        http_thread,
        cloudflared_process,
        public_image_url,
        temporary_directory,
    )


def verify_public_image_url(
    image_url: str,
) -> None:
    """Verify that the temporary public image URL is reachable.

    Cloudflare Quick Tunnels can take a few seconds to become
    reachable after the tunnel URL is created, so retry several times.
    """
    logger.info(
        "Verifying public image URL..."
    )

    last_error = None

    for attempt in range(1, 11):

        try:

            response = requests.get(
                image_url,
                timeout=10,
                stream=True,
            )

            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type",
                "",
            ).lower()

            if not content_type.startswith("image/"):
                raise RuntimeError(
                    "Temporary public URL did not return an image. "
                    f"Content-Type: {content_type}"
                )

            logger.info(
                "Public image URL is reachable."
            )

            response.close()

            return

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
        ) as exc:

            last_error = exc

            logger.info(
                "Public image URL is not reachable yet "
                "(attempt %d/10). Retrying in 2 seconds...",
                attempt,
            )

            time.sleep(2)

        except requests.exceptions.HTTPError as exc:

            response = getattr(exc, "response", None)

            if response is not None:
                logger.error(
                    "Public image URL returned HTTP %s.",
                    response.status_code,
                )

            raise

    raise RuntimeError(
        "Temporary public image URL could not be reached "
        "after multiple attempts."
    ) from last_error


def stop_temporary_image_host(
    http_server: ThreadingHTTPServer | None,
    cloudflared_process: subprocess.Popen | None,
    temporary_directory: str | None,
) -> None:
    """Stop temporary hosting and remove temporary files."""
    logger.info(
        "Cleaning up temporary image hosting..."
    )

    if http_server is not None:
        try:
            http_server.shutdown()
            http_server.server_close()
        except Exception:
            logger.debug(
                "Failed to cleanly stop local HTTP server.",
                exc_info=True,
            )

    if cloudflared_process is not None:
        try:
            if cloudflared_process.poll() is None:
                cloudflared_process.terminate()

                try:
                    cloudflared_process.wait(
                        timeout=5
                    )
                except subprocess.TimeoutExpired:
                    cloudflared_process.kill()
        except Exception:
            logger.debug(
                "Failed to cleanly stop cloudflared.",
                exc_info=True,
            )

    if temporary_directory:
        shutil.rmtree(
            temporary_directory,
            ignore_errors=True,
        )

    logger.info(
        "Temporary image hosting cleaned up."
    )


def load_environment() -> tuple[str, str]:
    """Load and validate Instagram credentials from this project's ``.env``."""
    load_dotenv(ENV_PATH)

    instagram_account_id = os.getenv(
        INSTAGRAM_BUSINESS_ACCOUNT_ID_ENV
    )

    access_token = os.getenv(
        INSTAGRAM_ACCESS_TOKEN_ENV
    )

    missing = []

    if not instagram_account_id:
        missing.append(INSTAGRAM_BUSINESS_ACCOUNT_ID_ENV)

    if not access_token:
        missing.append(INSTAGRAM_ACCESS_TOKEN_ENV)

    if missing:
        raise ValueError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
        )

    return instagram_account_id, access_token


def build_account_url() -> str:
    """Build the Instagram account information endpoint."""
    return (
        f"{GRAPH_BASE_URL}/"
        f"{GRAPH_API_VERSION}/me"
    )


def build_media_url(instagram_account_id: str) -> str:
    """Build the Instagram media container endpoint."""
    return (
        f"{GRAPH_BASE_URL}/"
        f"{GRAPH_API_VERSION}/"
        f"{instagram_account_id}/media"
    )


def build_publish_url(instagram_account_id: str) -> str:
    """Build the Instagram media publishing endpoint."""
    return (
        f"{GRAPH_BASE_URL}/"
        f"{GRAPH_API_VERSION}/"
        f"{instagram_account_id}/media_publish"
    )


def build_container_status_url(container_id: str) -> str:
    """Build the media container status endpoint."""
    return (
        f"{GRAPH_BASE_URL}/"
        f"{GRAPH_API_VERSION}/"
        f"{container_id}"
    )


def auth_headers(access_token: str) -> dict[str, str]:
    """Build authorization headers."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def check_credentials(
    instagram_account_id: str,
    access_token: str,
) -> dict[str, Any]:
    """Validate the access token and confirm the Instagram account."""
    url = build_account_url()

    response = requests.get(
        url,
        headers=auth_headers(access_token),
        params={
            "fields": "user_id,username,name",
        },
        timeout=DEFAULT_TIMEOUT,
    )

    response.raise_for_status()

    result = response.json()

    returned_user_id = result.get("user_id")
    username = result.get("username")
    name = result.get("name")

    if returned_user_id and returned_user_id != instagram_account_id:
        raise RuntimeError(
            "Instagram account ID mismatch. "
            f".env ID: {instagram_account_id}, "
            f"API user ID: {returned_user_id}"
        )

    return {
        "success": True,
        "type": "check",
        "instagram_account_id": instagram_account_id,
        "username": username,
        "name": name,
        "response": result,
    }


def create_media_container(
    instagram_account_id: str,
    access_token: str,
    image_url: str,
    caption: str | None = None,
) -> dict[str, Any]:
    """Create an Instagram image media container.

    Instagram fetches the image from the supplied public URL.
    """
    if not image_url.strip():
        raise ValueError("Image URL cannot be empty.")

    url = build_media_url(instagram_account_id)

    payload: dict[str, Any] = {
        "image_url": image_url.strip(),
    }

    if caption and caption.strip():
        payload["caption"] = caption.strip()

    logger.info("Creating Instagram media container...")

    response = requests.post(
        url,
        headers=auth_headers(access_token),
        json=payload,
        timeout=DEFAULT_TIMEOUT,
    )

    response.raise_for_status()

    result = response.json()

    container_id = result.get("id")

    if not container_id:
        raise RuntimeError(
            f"Instagram did not return a container ID: {result}"
        )

    logger.info("Media container created.")
    logger.info("Container ID: %s", container_id)

    return {
        "container_id": container_id,
        "response": result,
    }


def get_container_status(
    container_id: str,
    access_token: str,
) -> dict[str, Any]:
    """Check the processing status of an Instagram media container."""
    url = build_container_status_url(container_id)

    response = requests.get(
        url,
        headers=auth_headers(access_token),
        params={
            "fields": "status_code,status",
        },
        timeout=DEFAULT_TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


def wait_for_container(
    container_id: str,
    access_token: str,
    timeout_seconds: int = DEFAULT_STATUS_WAIT,
) -> dict[str, Any]:
    """Wait until Instagram finishes processing the media container."""
    logger.info("Waiting for Instagram media processing...")

    start_time = time.time()

    while True:

        result = get_container_status(
            container_id,
            access_token,
        )

        status_code = result.get("status_code")
        status = result.get("status")

        logger.info(
            "Container status: %s%s",
            status_code,
            f" | {status}" if status else "",
        )

        if status_code == "FINISHED":
            logger.info(
                "Instagram media is ready for publishing."
            )
            return result

        if status_code in {
            "ERROR",
            "EXPIRED",
        }:
            raise RuntimeError(
                "Instagram media processing failed: "
                f"{result}"
            )

        if time.time() - start_time >= timeout_seconds:
            raise TimeoutError(
                "Timed out waiting for Instagram media "
                "container to finish processing."
            )

        time.sleep(STATUS_POLL_INTERVAL)


def publish_media_container(
    instagram_account_id: str,
    access_token: str,
    container_id: str,
) -> dict[str, Any]:
    """Publish a processed Instagram media container."""
    url = build_publish_url(instagram_account_id)

    payload = {
        "creation_id": container_id,
    }

    logger.info("Publishing Instagram post...")

    response = requests.post(
        url,
        headers=auth_headers(access_token),
        json=payload,
        timeout=DEFAULT_TIMEOUT,
    )

    response.raise_for_status()

    result = response.json()

    media_id = result.get("id")

    if not media_id:
        raise RuntimeError(
            f"Instagram did not return a media ID: {result}"
        )

    return {
        "success": True,
        "type": "image",
        "media_id": media_id,
        "container_id": container_id,
        "response": result,
    }


def publish_image_post(
    instagram_account_id: str,
    access_token: str,
    image_url: str,
    caption: str | None = None,
) -> dict[str, Any]:
    """Create and publish a single-image Instagram post from a public URL."""
    container = create_media_container(
        instagram_account_id=instagram_account_id,
        access_token=access_token,
        image_url=image_url,
        caption=caption,
    )

    container_id = container["container_id"]

    wait_for_container(
        container_id=container_id,
        access_token=access_token,
    )

    result = publish_media_container(
        instagram_account_id=instagram_account_id,
        access_token=access_token,
        container_id=container_id,
    )

    result["image_url"] = image_url

    return result


def publish_to_instagram(image_path: Path, caption: str) -> dict[str, Any]:
    """Publish one local image and caption to the configured Instagram account.

    The local file is copied to a temporary directory, served on
    ``127.0.0.1:8000``, and exposed with a Cloudflare Quick Tunnel. Instagram
    receives that public HTTPS URL. The server, tunnel, and temp files are
    removed after publish succeeds or fails.

    Args:
        image_path: Local image file saved by the LinkedIn extractor.
        caption: Text that should accompany the image.

    Returns:
        ``success``, ``type``, ``media_id``, ``container_id``, ``image_url``,
        and the Graph API ``response``.

    Raises:
        ValueError: The image path, caption, or required credentials are missing.
        FileNotFoundError: The image file or ``cloudflared`` binary is missing.
        RuntimeError: The tunnel or Instagram publish step fails.
    """
    load_dotenv(ENV_PATH)

    if image_path is None or not str(image_path).strip():
        raise ValueError("An image path is required to publish to Instagram.")
    if not caption or not caption.strip():
        raise ValueError("A caption is required to publish to Instagram.")

    instagram_account_id, access_token = load_environment()

    if not os.path.isfile(image_path):
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    temporary_http_server = None
    cloudflared_process = None
    temporary_directory = None

    try:
        logger.info(
            "Local image detected: %s",
            image_path,
        )

        (
            temporary_http_server,
            _temporary_http_thread,
            cloudflared_process,
            temporary_image_url,
            temporary_directory,
        ) = start_temporary_image_host(
            str(image_path)
        )

        # The tested publisher waits for the Quick Tunnel to become reachable
        # instead of calling verify_public_image_url before create.
        time.sleep(5)

        return publish_image_post(
            instagram_account_id=instagram_account_id,
            access_token=access_token,
            image_url=temporary_image_url,
            caption=caption,
        )
    finally:
        stop_temporary_image_host(
            http_server=temporary_http_server,
            cloudflared_process=cloudflared_process,
            temporary_directory=temporary_directory,
        )
