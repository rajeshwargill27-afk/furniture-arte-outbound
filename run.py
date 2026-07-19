"""
Outbound cold-email sequencing agent.
Reads state from Google Sheets, sends due emails via Brevo SMTP, writes results back.
Idempotent: next_due only advances on successful send; failed/missed runs self-heal.
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from send_email import send_email
from sheet import load_config, load_contacts, open_sheet, write_config_value, write_contacts

# Days to wait before sending the NEXT email, keyed by the email number just sent.
# Email 1 → wait 2 days → send email 2, etc.
GAP: dict[int, int] = {2: 2, 3: 2, 4: 3, 5: 4}

TEMPLATE_DIR = Path(__file__).parent / "templates"

WARMUP_RAMP: list[tuple[int, int]] = [
    (2, 5),
    (6, 8),
    (10, 12),
    (14, 18),
    (float("inf"), 25),
]


def load_template(n: int) -> tuple[str, str]:
    path = TEMPLATE_DIR / f"email_{n}.txt"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    subject_line = lines[0]
    assert subject_line.startswith("Subject:"), f"Bad template {path}: first line must be 'Subject: ...'"
    subject = subject_line[len("Subject:"):].strip()
    body = "\n".join(lines[2:]).strip()
    return subject, body


def render(template: str, **kwargs: str) -> str:
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", value)
    return template


def effective_cap(config: dict, today: date) -> int:
    base_cap = int(config.get("daily_send_cap", "25"))
    warmup_active = config.get("warmup_active", "FALSE").strip().upper()
    if warmup_active != "TRUE":
        return base_cap

    warmup_start_str = config.get("warmup_start", "").strip()
    if not warmup_start_str:
        return 5  # day 0 of warmup, use lowest ramp

    warmup_start = date.fromisoformat(warmup_start_str)
    days_since = (today - warmup_start).days

    ramp_value = 5
    for threshold, cap in WARMUP_RAMP:
        if days_since < threshold:
            ramp_value = cap
            break

    return min(base_cap, ramp_value)


def main() -> None:
    tz = ZoneInfo("America/Toronto")
    today = date.today()
    # Allow override via env for local testing: TODAY=2026-07-15 python run.py
    if os.environ.get("TODAY"):
        today = date.fromisoformat(os.environ["TODAY"])

    print(f"[outbound] run date: {today} (America/Toronto)")

    spreadsheet = open_sheet()
    config = load_config(spreadsheet)
    contacts = load_contacts(spreadsheet)

    # Initialize warmup_start on first run if warmup is active and start date is blank
    if (
        config.get("warmup_active", "FALSE").strip().upper() == "TRUE"
        and not config.get("warmup_start", "").strip()
    ):
        write_config_value(spreadsheet, "warmup_start", today.isoformat())
        config["warmup_start"] = today.isoformat()
        print(f"[outbound] warmup_start set to {today}")

    cap = effective_cap(config, today)
    print(f"[outbound] effective daily cap: {cap}")

    due = [
        c for c in contacts
        if c.status == "active"
        and c.seq_stage < 5
        and c.next_due is not None
        and c.next_due <= today
    ]
    due.sort(key=lambda c: (c.next_due, c.list_id))

    selected = due[:cap]
    skipped = len(due) - len(selected)

    from_name = config.get("send_from_name", "Rajeshwar")
    from_email = config.get("send_from_email", "")
    reply_to = config.get("reply_to_email", "rajeshwargill@furniturearte.com")
    product_link = config.get("product_link", "")
    website_link = config.get("website_link", "")

    sent_count = 0
    error_count = 0
    updated_contacts: list = []

    for contact in selected:
        n = contact.seq_stage + 1
        subject_tpl, body_tpl = load_template(n)
        subject = render(subject_tpl,
                         first_name=contact.first_name,
                         company=contact.company,
                         product_link=product_link,
                         website_link=website_link)
        body = render(body_tpl,
                      first_name=contact.first_name,
                      company=contact.company,
                      product_link=product_link,
                      website_link=website_link)

        ok = send_email(
            to_email=contact.email,
            subject=subject,
            body=body,
            from_name=from_name,
            from_email=from_email,
            reply_to=reply_to,
        )

        if ok:
            contact.seq_stage = n
            contact.last_sent = today
            if n == 5:
                contact.status = "done"
                contact.next_due = None
            else:
                contact.next_due = today + timedelta(days=GAP[n + 1])
            sent_count += 1
            print(f"[outbound] sent email #{n} to {contact.email} ({contact.company})"
                  + (f" — next due {contact.next_due}" if contact.next_due else " — sequence done"))
            updated_contacts.append(contact)
        else:
            error_count += 1
            print(f"[outbound] FAILED email #{n} to {contact.email} — will retry next run")

    if updated_contacts:
        write_contacts(spreadsheet, updated_contacts)

    print(f"\n[outbound] summary: sent={sent_count} skipped={skipped} errors={error_count}")

    if error_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
