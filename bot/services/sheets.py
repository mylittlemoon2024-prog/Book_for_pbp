"""Thin wrapper around Google Sheets used as storage for meetings, registrations
and the book catalog.

Three worksheets are used inside a single spreadsheet:

Meetings:       id | title | date (YYYY-MM-DD) | time | location | capacity | description
Registrations:  meeting_id | user_id | username | full_name | phone | registered_at | status
Books:          id | genre | title | author | description | photo_url

gspread calls are blocking, so callers should run them via asyncio.to_thread
to avoid blocking the bot's event loop.
"""
from __future__ import annotations

import random
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
BOOKS_HEADER = ["id", "genre", "title", "author", "description", "photo_url"]

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


@dataclass
class Book:
    id: str
    genre: str
    title: str
    author: str
    description: str
    photo_url: str

    def caption(self) -> str:
        text = f"<b>{self.title}</b>\n👤 {self.author}"
        if self.description:
            text += f"\n\n{self.description}"
        return text


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
        self._books_ws = self._get_or_create(spreadsheet, settings.books_sheet, BOOKS_HEADER)

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

    # ---- book catalog ---------------------------------------------------

    def list_books(self) -> list[Book]:
        rows = self._books_ws.get_all_records()
        books: list[Book] = []
        for row in rows:
            genre = str(row.get("genre", "")).strip()
            title = str(row.get("title", "")).strip()
            if not genre or not title:
                continue
            books.append(
                Book(
                    id=str(row.get("id", "")),
                    genre=genre,
                    title=title,
                    author=str(row.get("author", "")),
                    description=str(row.get("description", "")),
                    photo_url=str(row.get("photo_url", "")).strip(),
                )
            )
        return books

    def list_genres(self) -> list[str]:
        genres = {book.genre for book in self.list_books()}
        return sorted(genres)

    def books_by_genre(self, genre: str) -> list[Book]:
        return [book for book in self.list_books() if book.genre == genre]

    def random_book(self, genre: str, exclude_id: str | None = None) -> Book | None:
        candidates = self.books_by_genre(genre)
        if not candidates:
            return None
        if exclude_id is not None and len(candidates) > 1:
            candidates = [b for b in candidates if b.id != exclude_id]
        return random.choice(candidates)
