# furniture-arte-outbound

Stateless cold-email sequencing agent for Furniture Arte. Runs on a GitHub Actions cron, reads contact state from Google Sheets, sends a 5-email sequence via Brevo SMTP.

## How it works

Each run:
1. Loads `config` and `state` tabs from the Google Sheet.
2. Filters contacts where `status = active`, `seq_stage < 5`, and `next_due <= today`.
3. Sorts by oldest `next_due` first (tie-break: `list_id`).
4. Caps sends at `daily_send_cap` (or warm-up ramp if `warmup_active = TRUE`).
5. Sends the next email in each contact's sequence, then writes updated state back.

**Idempotent:** `next_due` only advances on a successful send. A failed or missed run self-heals on the next execution.

## Sequence cadence

| Email sent | Wait before next |
|------------|-----------------|
| #1         | 2 days          |
| #2         | 2 days          |
| #3         | 3 days          |
| #4         | 4 days          |
| #5         | — (done)        |

Full sequence spans 11 days (day 0 → day 11).

## Google Sheet schema

### `state` tab (columns A–I)

| Column | Values |
|--------|--------|
| email | contact email |
| first_name | merge field |
| company | merge field |
| region | informational |
| list_id | sort tie-break |
| seq_stage | 0–5 (0 = nothing sent) |
| last_sent | YYYY-MM-DD |
| next_due | YYYY-MM-DD |
| status | `active` / `pending` / `stopped` / `done` |

### `config` tab (columns key / value)

| Key | Description |
|-----|-------------|
| daily_send_cap | Max emails per day (integer) |
| send_from_name | Sender display name |
| send_from_email | Sending address (Brevo subdomain) |
| reply_to_email | Where replies are routed (monitored inbox) |
| product_link | URL merged into email #2 |
| website_link | URL merged into email #5 |
| warmup_active | `TRUE` / `FALSE` |
| warmup_start | YYYY-MM-DD (auto-set on first warmup run if blank) |

## Secrets (GitHub Actions)

| Secret | Description |
|--------|-------------|
| `BREVO_SMTP_HOST` | `smtp-relay.brevo.com` |
| `BREVO_SMTP_PORT` | `587` |
| `BREVO_SMTP_LOGIN` | Brevo account login email |
| `BREVO_SMTP_KEY` | Brevo SMTP key |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON of the service account key |
| `SHEET_ID` | Google Sheet ID from the URL |

## Running locally

```bash
pip install -r requirements.txt
export BREVO_SMTP_HOST=smtp-relay.brevo.com
export BREVO_SMTP_PORT=587
export BREVO_SMTP_LOGIN=...
export BREVO_SMTP_KEY=...
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
export SHEET_ID=...

# Optional: override today's date for testing
export TODAY=2026-07-15

python run.py
```

## Warm-up ramp

When `warmup_active = TRUE`, effective send cap is capped by days since `warmup_start`:

| Days since start | Effective cap |
|-----------------|---------------|
| 0–2             | 5             |
| 3–5             | 8             |
| 6–9             | 12            |
| 10–13           | 18            |
| 14+             | 25            |

Effective cap = `min(daily_send_cap, ramp_value)`.

## Adding contacts

Set rows in the `state` tab with `status = active`, `seq_stage = 0`, and `next_due = today's date` to begin their sequence immediately.

## Cron schedule note

The Action runs at `0 13 * * *` UTC = 9:00 AM EDT / 8:00 AM EST. GitHub Actions cron does not adjust for DST. This is acceptable for v1.
