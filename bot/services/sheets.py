"""Thin wrapper around Google Sheets used as storage for meetings and registrations.

Two worksheets are used inside a single spreadsheet:

Meetings:       id | title | date (YYYY-MM-DD) | time | location | capacity | description
Registrations:  meeting_id | user_id | username | full_name | phone | registered_at | status

gspread calls are blocking, so callers should run them via asyncio.to_thread
to avoid blocking the bot's event loop.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from bot.config import settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

MEETINGS_HEADER = ["id", "title", "date", "time", "location", "capacity", "description"]
REGISTRATIONS_HEADER = [
    "meeting_id",
    "user_id",
    "username",
    "full_name",
    "phone",
    "registered_at",
    "status",
]

STATUS_ACTIVE = "active"
STATUS_CANCELLED = "cancelled"


@dataclass
class Meeting:
    id: str
    title: str
    date: str
    time: str
    location: str
    capacity: int
    description: str

    def label(self) -> str:
        return f"{self.date} {self.time} — {self.title}"


class SheetsService:
    """Reads/writes meetings and registrations stored in a Google Sheet."""

    def __init__(self) -> None:
        creds = Credentials.from_service_account_file(
            settings.google_credentials_path, scopes=SCOPES
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(settings.spreadsheet_id)
        self._meetings_ws = self._get_or_create(
            spreadsheet, settings.meetings_sheet, MEETINGS_HEADER
        )
        self._registrations_ws = self._get_or_create(
            spreadsheet, settings.registrations_sheet, REGISTRATIONS_HEADER
        )

    @staticmethod
    def _get_or_create(spreadsheet: gspread.Spreadsheet, title: str, header: list[str]):
        try:
            ws = spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=title, rows=200, cols=len(header))
            ws.append_row(header)
        return ws

    # ---- meetings -----------------------------------------------------

    def list_upcoming_meetings(self) -> list[Meeting]:
        rows = self._meetings_ws.get_all_records()
        today = datetime.now().date()
        meetings: list[Meeting] = []
        for row in rows:
            raw_date = str(row.get("date", "")).strip()
            try:
                meeting_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                continue
            if meeting_date < today:
                continue
            meetings.append(
                Meeting(
                    id=str(row.get("id", "")),
                    title=str(row.get("title", "")),
                    date=raw_date,
                    time=str(row.get("time", "")),
                    location=str(row.get("location", "")),
                    capacity=int(row.get("capacity") or 0),
                    description=str(row.get("description", "")),
                )
            )
        meetings.sort(key=lambda m: (m.date, m.time))
        return meetings

    def get_meeting(self, meeting_id: str) -> Meeting | None:
        for meeting in self.list_upcoming_meetings():
            if meeting.id == meeting_id:
                return meeting
        return None

    # ---- registrations --------------------------------------------------

    def _registration_rows(self) -> list[dict]:
        return self._registrations_ws.get_all_records()

    def count_active_registrations(self, meeting_id: str) -> int:
        return sum(
            1
            for row in self._registration_rows()
            if str(row.get("meeting_id")) == meeting_id and row.get("status") == STATUS_ACTIVE
        )

    def get_user_registration(self, meeting_id: str, user_id: int) -> dict | None:
        for row in self._registration_rows():
            if (
                str(row.get("meeting_id")) == meeting_id
                and str(row.get("user_id")) == str(user_id)
                and row.get("status") == STATUS_ACTIVE
            ):
                return row
        return None

    def list_user_registrations(self, user_id: int) -> list[dict]:
        return [
            row
            for row in self._registration_rows()
            if str(row.get("user_id")) == str(user_id) and row.get("status") == STATUS_ACTIVE
        ]

    def register(
        self,
        meeting_id: str,
        user_id: int,
        username: str,
        full_name: str,
        phone: str,
    ) -> None:
        self._registrations_ws.append_row(
            [
                meeting_id,
                user_id,
                username,
                full_name,
                phone,
                datetime.now().isoformat(timespec="seconds"),
                STATUS_ACTIVE,
            ]
        )

    def cancel_registration(self, meeting_id: str, user_id: int) -> bool:
        values = self._registrations_ws.get_all_values()
        if not values:
            return False
        header = values[0]
        meeting_col = header.index("meeting_id")
        user_col = header.index("user_id")
        status_col = header.index("status")

        for row_idx, row in enumerate(values[1:], start=2):
            if (
                row[meeting_col] == meeting_id
                and row[user_col] == str(user_id)
                and row[status_col] == STATUS_ACTIVE
            ):
                self._registrations_ws.update_cell(row_idx, status_col + 1, STATUS_CANCELLED)
                return True
        return False
