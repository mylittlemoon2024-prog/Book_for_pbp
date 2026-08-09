"""FSM states used during the registration flow."""
from aiogram.fsm.state import State, StatesGroup


class RegistrationForm(StatesGroup):
    full_name = State()
    phone = State()
