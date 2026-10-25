from aiogram.fsm.state import State, StatesGroup


class FilterStates(StatesGroup):
    waiting_max_price = State()
    waiting_min_price = State()
    waiting_area = State()
    waiting_floor = State()
