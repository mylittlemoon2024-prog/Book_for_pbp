"""FSM states used during the registration and feedback flows."""
from aiogram.fsm.state import State, StatesGroup


class RegistrationForm(StatesGroup):
    full_name = State()
    phone = State()


class SuggestionForm(StatesGroup):
    name = State()
    text = State()
