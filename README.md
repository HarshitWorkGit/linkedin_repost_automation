# LinkedIn Repost Automation

Publishes one queued LinkedIn post to Facebook and Instagram after an explicit approval.

`data/linkedin_posts.json` is the source of truth. The command does not take a LinkedIn URL. It selects one eligible record, downloads that post's first image, and publishes only when the operator types `APPROVE`.

## Workflow

```text
data/linkedin_posts.json
        │
        ▼
post_store.get_next_post
        │  status = "new", caption, LinkedIn URL, first image URL
        │  oldest postedat.date
        ▼
repost.download_post_image
        │  local file under generated/
        ▼
repost.prepare_preview
        │
        ▼
repost.require_explicit_approval
        │  continues only if the operator types APPROVE
        ▼
facebook_publisher.publish_to_facebook
instagram_publisher.publish_to_instagram
        │
        ▼
post_store.mark_published
        │  status "new" -> "published" only when both publishes return
```

If no eligible post exists, the command exits without publishing.

If approval is declined, or the terminal is not interactive, the record stays `"new"` and nothing is published.

If Facebook or Instagram raises an error, the record stays `"new"` so the same post can be retried. Status is not changed unless both publishes return.

`repost.py` is the orchestrator. The queue, the extractor, and the two publishers do not import each other. Publisher modules still load their own credentials from `.env`.

| Module | Responsibility |
| --- | --- |
| `repost.py` | Queue run, image download, preview, approval gate, and publish order |
| `post_store.py` | Load `data/linkedin_posts.json`, select one eligible post, update status |
| `linkedin_extractor.py` | Validate the caption and local image before preview |
| `facebook_publisher.py` | Publish that image and caption to a Facebook Page |
| `instagram_publisher.py` | Publish that image and caption to Instagram |
| `data/linkedin_posts.json` | Post queue. Eligible records use `status` `"new"` |
| `generated/` | Downloaded images. Contents are gitignored except `.gitkeep` |

## Queue rules

A record is eligible when all of these are true:

- `status` is `"new"`
- `content` is non-empty
- `linkedinurl` is non-empty
- `postimages` parses to a list with at least one image URL

`postimages` and `postedat` are JSON strings in the file. The store parses them when selecting a post and writes back only `status`. Every other field is preserved.

When more than one record is eligible, the oldest `postedat.date` is selected. Pass `--post-id` to select one eligible record by `id` instead.

Only the first image URL is downloaded. The file is saved as `generated/<post-id>.<ext>` and is not committed.

## Requirements

- Python 3.11+
- A virtual environment is recommended

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Dependencies: `python-dotenv` and `requests`. The queue itself uses the Python standard library. Instagram publishing also needs `cloudflared` on the machine that runs the command.

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
python repost.py
```

Optional, for one eligible record:

```bash
python repost.py --post-id 7507679936275644416
```

The command prints the LinkedIn URL, caption, and downloaded image path, then waits until the operator types `APPROVE`. Any other input skips both publishes. A non-interactive terminal cannot approve a publish.

| Code | Meaning |
| --- | --- |
| 0 | Published, the operator did not approve, or no eligible post was found |
| 1 | Invalid input, a missing image, a download error, or a publish error |
| 2 | A stage raised `NotImplementedError` |

A publish error leaves the queue record at `"new"`.
