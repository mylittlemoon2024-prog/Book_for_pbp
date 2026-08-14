"""Handlers for browsing meetings and registering/cancelling attendance."""
import asyncio
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import cancel_fsm_kb, consent_kb, main_menu_kb, meeting_card_kb, meetings_list_kb
from bot.services.sheets import CANCELLATION_CUTOFF_HOURS, Meeting, SheetsService, meeting_datetime
from bot.states import RegistrationForm

router = Router(name="registration")
sheets = SheetsService()

REGISTRATION_CONSENT_TEXT = (
    "Для записи на встречу нужны ваше имя и телефон.\n\n"
    "Нажимая «Согласен(на)», вы даёте согласие на обработку персональных "
    "данных (имя, телефон, Telegram username) в соответствии с ФЗ №152-ФЗ "
    "«О персональных данных». Данные используются только для организации "
    "встреч книжного клуба «ВМЕСТЕ» и не передаются третьим лицам."
)


def _can_cancel(meeting: Meeting) -> bool:
    """Cancellation is only allowed up to CANCELLATION_CUTOFF_HOURS before
    the meeting starts. A meeting whose date/time can't be parsed is treated
    as still cancellable rather than silently locking users out."""
    dt = meeting_datetime(meeting)
    if dt is None:
        return True
    return dt - datetime.now() >= timedelta(hours=CANCELLATION_CUTOFF_HOURS)


def _meeting_card_text(meeting: Meeting, taken: int, is_registered: bool, can_cancel: bool) -> str:
    text = (
        f"<b>{meeting.title}</b>\n"
        f"🗓 {meeting.date} в {meeting.time}\n"
        f"📍 {meeting.location}\n"
    )
    if meeting.description:
        text += f"\n{meeting.description}\n"
    if meeting.capacity:
        text += f"\n👥 Занято мест: {taken}/{meeting.capacity}"
    if is_registered:
        text += "\n\n✅ Вы записаны на эту встречу"
        if can_cancel:
            text += (
                f"\nОтменить запись можно не позднее чем за "
                f"{CANCELLATION_CUTOFF_HOURS} ч. до встречи."
            )
        else:
            text += "\n⏰ Срок отмены записи истёк."
    return text


async def _show_meeting_card(callback: CallbackQuery, meeting_id: str) -> None:
    meeting = await asyncio.to_thread(sheets.get_meeting, meeting_id)
    if meeting is None:
        await callback.answer("Встреча не найдена", show_alert=True)
        return

    registration = await asyncio.to_thread(
        sheets.get_user_registration, meeting_id, callback.from_user.id
    )
    taken = await asyncio.to_thread(sheets.count_active_registrations, meeting_id)
    can_cancel = _can_cancel(meeting)

    text = _meeting_card_text(meeting, taken, is_registered=bool(registration), can_cancel=can_cancel)
    await callback.message.edit_text(
        text,
        reply_markup=meeting_card_kb(
            meeting_id, is_registered=bool(registration), can_cancel=can_cancel
        ),
    )


@router.callback_query(F.data == "list_meetings")
async def cb_list_meetings(callback: CallbackQuery) -> None:
    meetings = await asyncio.to_thread(sheets.list_upcoming_meetings)
    if not meetings:
        await callback.message.edit_text(
            "Ближайших встреч пока нет 🙁", reply_markup=main_menu_kb()
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        "Выберите встречу:", reply_markup=meetings_list_kb(meetings)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("meeting:"))
async def cb_meeting_card(callback: CallbackQuery) -> None:
    meeting_id = callback.data.split(":", 1)[1]
    await _show_meeting_card(callback, meeting_id)
    await callback.answer()


@router.callback_query(F.data.startswith("cancel:"))
async def cb_cancel_registration(callback: CallbackQuery) -> None:
    meeting_id = callback.data.split(":", 1)[1]
    meeting = await asyncio.to_thread(sheets.get_meeting, meeting_id)
    if meeting is not None and not _can_cancel(meeting):
        await callback.answer(
            f"Отменить запись можно не позднее чем за {CANCELLATION_CUTOFF_HOURS} ч. "
            "до встречи — срок уже истёк.",
            show_alert=True,
        )
        await _show_meeting_card(callback, meeting_id)
        return

    cancelled = await asyncio.to_thread(
        sheets.cancel_registration, meeting_id, callback.from_user.id
    )
    await callback.answer(
        "Запись отменена" if cancelled else "Активная запись не найдена",
        show_alert=True,
    )
    await _show_meeting_card(callback, meeting_id)


@router.callback_query(F.data.startswith("register:"))
async def cb_register_start(callback: CallbackQuery, state: FSMContext) -> None:
    meeting_id = callback.data.split(":", 1)[1]
    meeting = await asyncio.to_thread(sheets.get_meeting, meeting_id)
    if meeting is None:
        await callback.answer("Встреча не найдена", show_alert=True)
        return

    if meeting.capacity:
        taken = await asyncio.to_thread(sheets.count_active_registrations, meeting_id)
        if taken >= meeting.capacity:
            await callback.answer("К сожалению, свободных мест не осталось 🙁", show_alert=True)
            return

    existing = await asyncio.to_thread(
        sheets.get_user_registration, meeting_id, callback.from_user.id
    )
    if existing:
        await callback.answer("Вы уже записаны на эту встречу", show_alert=True)
        return

    await state.update_data(meeting_id=meeting_id)
    await callback.message.edit_text(
        REGISTRATION_CONSENT_TEXT, reply_markup=consent_kb("register_consent_ok")
    )
    await callback.answer()


@router.callback_query(F.data == "register_consent_ok")
async def cb_register_consent_ok(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RegistrationForm.full_name)
    await callback.message.edit_text(
        "Как вас зовут? Напишите имя и фамилию.", reply_markup=cancel_fsm_kb()
    )
    await callback.answer()


@router.message(RegistrationForm.full_name)
async def process_full_name(message: Message, state: FSMContext) -> None:
    full_name = (message.text or "").strip()
    if not full_name:
        await message.answer("Пожалуйста, напишите имя текстом.")
        return
    await state.update_data(full_name=full_name)
    await state.set_state(RegistrationForm.phone)
    await message.answer(
        "Оставьте номер телефона для связи (например, +7 900 000-00-00).",
        reply_markup=cancel_fsm_kb(),
    )


@router.message(RegistrationForm.phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()
    if not phone:
        await message.answer("Пожалуйста, напишите номер телефона текстом.")
        return

    data = await state.get_data()
    meeting_id = data["meeting_id"]
    full_name = data["full_name"]

    await asyncio.to_thread(
        sheets.register,
        meeting_id,
        message.from_user.id,
        message.from_user.username or "",
        full_name,
        phone,
    )
    await state.clear()

    meeting = await asyncio.to_thread(sheets.get_meeting, meeting_id)
    title = meeting.label() if meeting else meeting_id
    await message.answer(
        f"Готово! Вы записаны на встречу «{title}» ✅", reply_markup=main_menu_kb()
    )


@router.callback_query(F.data == "my_registrations")
async def cb_my_registrations(callback: CallbackQuery) -> None:
    registrations = await asyncio.to_thread(sheets.list_user_registrations, callback.from_user.id)
    if not registrations:
        await callback.message.edit_text(
            "У вас пока нет активных записей.", reply_markup=main_menu_kb()
        )
        await callback.answer()
        return

    meetings = {m.id: m for m in await asyncio.to_thread(sheets.list_upcoming_meetings)}
    lines = ["<b>Ваши записи:</b>"]
    for reg in registrations:
        meeting = meetings.get(str(reg["meeting_id"]))
        label = meeting.label() if meeting else f"встреча #{reg['meeting_id']}"
        lines.append(f"• {label}")

    await callback.message.edit_text("\n".join(lines), reply_markup=main_menu_kb())
    await callback.answer()
