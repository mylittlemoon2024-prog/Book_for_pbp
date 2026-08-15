"""Thin wrapper around Google Sheets used as storage for meetings, registrations,
the book catalog, the lecture catalog and user suggestions.

Five worksheets are used inside a single spreadsheet:

Meetings:       id | title | date (YYYY-MM-DD) | time | location | capacity | description
Registrations:  meeting_id | user_id | username | full_name | phone | registered_at | status
Books:          id | genre | title | author | description | photo_url
Lectures:       id | category | title | speaker | description | video_url
Suggestions:    name | suggestion | user_id | username | submitted_at

gspread calls are blocking, so callers should run them via asyncio.to_thread
to avoid blocking the bot's event loop.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, datetime
from datetime import time as dt_time

import gspread
from google.oauth2.service_account import Credentials

from bot.config import settings

# Google Sheets auto-converts recognizable date text into its own Date type
# and displays it per the spreadsheet's locale — a cell typed as
# "2026-09-13" can come back as "13.09.2026" (and vice versa) regardless of
# what was entered. Accept both rather than fighting the spreadsheet's
# formatting.
_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y")


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


# A registration can only be cancelled up to this many hours before the
# meeting starts.
CANCELLATION_CUTOFF_HOURS = 24


def meeting_datetime(meeting: "Meeting") -> datetime | None:
    """Best-effort combined date+time for a meeting, or None if the date
    cell couldn't be parsed at all."""
    date_part = _parse_date(meeting.date)
    if date_part is None:
        return None
    try:
        hh, mm = meeting.time.strip().split(":")[:2]
        time_part = dt_time(int(hh), int(mm))
    except (ValueError, IndexError):
        time_part = dt_time(0, 0)
    return datetime.combine(date_part, time_part)


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
BOOKS_HEADER = ["id", "genre", "title", "author", "description", "photo_url", "age_rating"]

# Russian legal age-rating marks (ФЗ-436), used to validate the age_rating
# cell — anything else is treated as unset rather than shown to users.
AGE_RATINGS = ("0+", "6+", "12+", "16+", "18+")

# Fixed genre taxonomy for the "Choose a book" catalog — shown in this exact
# order regardless of which genres currently have books in the sheet, so the
# menu stays stable and predictable. A book's `genre` cell must match one of
# these strings exactly (including capitalization) to show up under it.
GENRES = (
    "Проза",
    "Фантастика",
    "Детектив и триллер",
    "Ужасы и мистика",
    "Любовный жанр",
    "Приключения",
    "Драма и трагедия",
    "Юмор и сатира",
    "Поэзия",
    "Драматургия",
    "Для детей",
    "Нон-фикшн",
)
LECTURES_HEADER = ["id", "category", "title", "speaker", "description", "video_url"]

# Fixed direction taxonomy for the "Lectures" catalog — same idea as GENRES:
# shown in this exact order regardless of what's currently in the sheet.
LECTURE_CATEGORIES = (
    "Литература и писательство",
    "Психология",
    "История",
    "Философия",
    "Саморазвитие",
    "Искусство и культура",
    "Наука",
    "Мотивация и карьера",
)

SUGGESTIONS_HEADER = ["name", "suggestion", "user_id", "username", "submitted_at"]

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
    age_rating: str = ""

    def caption(self) -> str:
        title_line = f"<b>{self.title}</b>"
        if self.age_rating:
            title_line += f"  🔞 {self.age_rating}" if self.age_rating == "18+" else f"  {self.age_rating}"
        text = f"{title_line}\n👤 {self.author}"
        if self.description:
            text += f"\n\n{self.description}"
        return text


@dataclass
class Lecture:
    id: str
    category: str
    title: str
    speaker: str
    description: str
    video_url: str

    def caption(self) -> str:
        text = f"<b>{self.title}</b>"
        if self.speaker:
            text += f"\n🎤 {self.speaker}"
        if self.description:
            text += f"\n\n{self.description}"
        if self.video_url:
            text += f"\n\n🎬 Смотреть: {self.video_url}"
        return text


class SheetsService:
    """Reads/writes meetings and registrations stored in a Google Sheet."""

    def __init__(self) -> None:
        if settings.google_credentials_json:
            # Some hosts (e.g. Railway) have no way to mount a secret file —
            # the key is passed as the raw JSON content of an env var instead.
            info = json.loads(settings.google_credentials_json)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
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
        self._lectures_ws = self._get_or_create(
            spreadsheet, settings.lectures_sheet, LECTURES_HEADER
        )
        self._suggestions_ws = self._get_or_create(
            spreadsheet, settings.suggestions_sheet, SUGGESTIONS_HEADER
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
        parsed: list[tuple[date, str, Meeting]] = []
        for row in rows:
            raw_date = str(row.get("date", "")).strip()
            meeting_date = _parse_date(raw_date)
            if meeting_date is None or meeting_date < today:
                continue
            time = str(row.get("time", ""))
            parsed.append(
                (
                    meeting_date,
                    time,
                    Meeting(
                        id=str(row.get("id", "")),
                        title=str(row.get("title", "")),
                        date=raw_date,
                        time=time,
                        location=str(row.get("location", "")),
                        capacity=int(row.get("capacity") or 0),
                        description=str(row.get("description", "")),
                    ),
                )
            )
        parsed.sort(key=lambda item: (item[0], item[1]))
        return [meeting for _, _, meeting in parsed]

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
            age_rating = str(row.get("age_rating", "")).strip()
            books.append(
                Book(
                    id=str(row.get("id", "")),
                    genre=genre,
                    title=title,
                    author=str(row.get("author", "")),
                    description=str(row.get("description", "")),
                    photo_url=str(row.get("photo_url", "")).strip(),
                    age_rating=age_rating if age_rating in AGE_RATINGS else "",
                )
            )
        return books

    def books_by_genre(self, genre: str) -> list[Book]:
        return [book for book in self.list_books() if book.genre == genre]

    def random_book(self, genre: str, exclude_id: str | None = None) -> Book | None:
        candidates = self.books_by_genre(genre)
        if not candidates:
            return None
        if exclude_id is not None and len(candidates) > 1:
            candidates = [b for b in candidates if b.id != exclude_id]
        return random.choice(candidates)

    # ---- lecture catalog --------------------------------------------------

    def list_lectures(self) -> list[Lecture]:
        rows = self._lectures_ws.get_all_records()
        lectures: list[Lecture] = []
        for row in rows:
            category = str(row.get("category", "")).strip()
            title = str(row.get("title", "")).strip()
            if not category or not title:
                continue
            lectures.append(
                Lecture(
                    id=str(row.get("id", "")),
                    category=category,
                    title=title,
                    speaker=str(row.get("speaker", "")),
                    description=str(row.get("description", "")),
                    video_url=str(row.get("video_url", "")).strip(),
                )
            )
        return lectures

    def lectures_by_category(self, category: str) -> list[Lecture]:
        return [lecture for lecture in self.list_lectures() if lecture.category == category]

    def random_lecture(self, category: str, exclude_id: str | None = None) -> Lecture | None:
        candidates = self.lectures_by_category(category)
        if not candidates:
            return None
        if exclude_id is not None and len(candidates) > 1:
            candidates = [lec for lec in candidates if lec.id != exclude_id]
        return random.choice(candidates)

    # ---- suggestions ------------------------------------------------------

    def add_suggestion(self, name: str, suggestion: str, user_id: int, username: str) -> None:
        self._suggestions_ws.append_row(
            [
                name,
                suggestion,
                user_id,
                username,
                datetime.now().isoformat(timespec="seconds"),
            ]
        )
