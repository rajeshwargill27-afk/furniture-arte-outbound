import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import gspread

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

STATE_COLS = ["email", "first_name", "company", "region", "list_id",
              "seq_stage", "last_sent", "next_due", "status"]


@dataclass
class Contact:
    email: str
    first_name: str
    company: str
    region: str
    list_id: str
    seq_stage: int
    last_sent: Optional[date]
    next_due: Optional[date]
    status: str
    row_index: int = field(default=0, repr=False)

    def to_row(self) -> list:
        return [
            self.email,
            self.first_name,
            self.company,
            self.region,
            self.list_id,
            str(self.seq_stage),
            self.last_sent.isoformat() if self.last_sent else "",
            self.next_due.isoformat() if self.next_due else "",
            self.status,
        ]


def _parse_date(value: str) -> Optional[date]:
    value = value.strip()
    if not value:
        return None
    return date.fromisoformat(value)


def _open_sheet() -> gspread.Spreadsheet:
    sheet_id = os.environ["SHEET_ID"]

    raw_client = os.environ.get("GOOGLE_OAUTH_CLIENT_JSON")
    if raw_client:
        client_dict = json.loads(raw_client)
    else:
        with open("credentials.json", encoding="utf-8") as f:
            client_dict = json.load(f)

    raw_user = os.environ.get("GOOGLE_AUTHORIZED_USER_JSON")
    if raw_user:
        authorized_user_dict = json.loads(raw_user)
    else:
        with open("authorized_user.json", encoding="utf-8") as f:
            authorized_user_dict = json.load(f)

    client = gspread.oauth_from_dict(
        client_config=client_dict,
        authorized_user_info=authorized_user_dict,
    )
    return client.open_by_key(sheet_id)


def load_config(spreadsheet: gspread.Spreadsheet) -> dict:
    ws = spreadsheet.worksheet("config")
    rows = ws.get_all_values()
    return {r[0]: r[1] for r in rows if len(r) >= 2 and r[0]}


def load_contacts(spreadsheet: gspread.Spreadsheet) -> list[Contact]:
    ws = spreadsheet.worksheet("state")
    rows = ws.get_all_values()
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    contacts = []
    for i, row in enumerate(rows[1:], start=2):
        padded = row + [""] * (len(header) - len(row))
        r = dict(zip(header, padded))
        contacts.append(Contact(
            email=r.get("email", "").strip(),
            first_name=r.get("first_name", "").strip(),
            company=r.get("company", "").strip(),
            region=r.get("region", "").strip(),
            list_id=r.get("list_id", "").strip(),
            seq_stage=int(r.get("seq_stage", "0") or "0"),
            last_sent=_parse_date(r.get("last_sent", "")),
            next_due=_parse_date(r.get("next_due", "")),
            status=r.get("status", "").strip(),
            row_index=i,
        ))
    return contacts


def write_contacts(spreadsheet: gspread.Spreadsheet, contacts: list[Contact]) -> None:
    if not contacts:
        return
    ws = spreadsheet.worksheet("state")
    updates = []
    for c in contacts:
        cell_range = f"A{c.row_index}:I{c.row_index}"
        updates.append({
            "range": cell_range,
            "values": [c.to_row()],
        })
    ws.batch_update(updates)


def write_config_value(spreadsheet: gspread.Spreadsheet, key: str, value: str) -> None:
    ws = spreadsheet.worksheet("config")
    rows = ws.get_all_values()
    for i, row in enumerate(rows, start=1):
        if row and row[0] == key:
            ws.update_cell(i, 2, value)
            return
    ws.append_row([key, value])


def open_sheet() -> gspread.Spreadsheet:
    return _open_sheet()
