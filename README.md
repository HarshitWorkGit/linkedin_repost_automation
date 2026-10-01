# LinkedIn Repost Automation

Self-contained workflow that takes a LinkedIn post URL, extracts its caption and image, shows a preview, and publishes to Facebook and Instagram only after an explicit approval.

This repository is scaffolding. LinkedIn extraction is not implemented, and neither publisher sends an API request.

## Workflow

```text
LinkedIn post URL
        │
        ▼
linkedin_extractor.extract_linkedin_post
        │  caption + image saved under generated/
        ▼
repost.prepare_preview
        │
        ▼
repost.require_explicit_approval
        │  continues only if the operator types APPROVE
        ▼
facebook_publisher.publish_to_facebook
instagram_publisher.publish_to_instagram
```

`repost.py` is the only orchestrator. The extractor and the two publishers do not import each other.

| Module | Responsibility |
| --- | --- |
| `repost.py` | CLI, preview, approval gate, and the call order above |
| `linkedin_extractor.py` | Turn a LinkedIn URL into a caption and a local image |
| `facebook_publisher.py` | Publish that image and caption to a Facebook Page |
| `instagram_publisher.py` | Publish that image and caption to Instagram |
| `generated/` | Local image output. Contents are gitignored except `.gitkeep` |

## Requirements

- Python 3.11+
- A virtual environment is recommended

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The only dependency today is `python-dotenv`. HTTP clients will be added when the publishers are implemented.

## Configuration

Copy the example file and keep secrets in `.env` only:

```bash
copy .env.example .env
```

```env
FACEBOOK_PAGE_ID=
FACEBOOK_PAGE_ACCESS_TOKEN=
INSTAGRAM_BUSINESS_ACCOUNT_ID=
INSTAGRAM_ACCESS_TOKEN=
```

`.env` is listed in `.gitignore`. Do not hardcode tokens in Python modules. Publisher code reads these names from the environment and does not log their values.

## Usage

```bash
python repost.py "https://www.linkedin.com/posts/..."
```

The command accepts the URL, then stops at the extraction placeholder. After extraction exists, the same command prints the caption and image path and waits until the operator types `APPROVE`. Any other input skips both publishes. A non-interactive terminal cannot approve a publish.

Expected exit codes once the surrounding checks run:

| Code | Meaning |
| --- | --- |
| 0 | Finished, or the operator did not approve |
| 1 | Invalid input, such as a missing URL, image, or caption |
| 2 | A stage is still a placeholder |

## Current status

- [x] Project layout, environment loading, and workflow skeleton
- [ ] LinkedIn caption and image extraction
- [ ] Facebook image publish
- [ ] Instagram image publish

Each unfinished step is marked with `TODO` in the module that owns it.
