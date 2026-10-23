"""Russian wording for the report: numbers, dates, plurals and names of things.

These are the only transformations the template may apply to facts (Jinja
filters), so the provenance test can list every number they can produce.
"""

import math
from datetime import date

MINUS = "−"
PERCENT = 100
S_PER_MIN = 60
DECIMAL_COMMA = ","

MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)
COMPOUND_NAMES = {
    "SOFT": "Soft",
    "MEDIUM": "Medium",
    "HARD": "Hard",
    "INTERMEDIATE": "Inter",
    "WET": "Wet",
    "UNKNOWN": "неизвестно",
}
NEUTRALISATION_NAMES = {
    "SC": "сейфти-кар",
    "VSC": "виртуальный сейфти-кар",
    "RED": "красный флаг",
}
STATUS_NAMES = {
    "Retired": "сход",
    "Accident": "авария",
    "Collision": "столкновение",
    "Collision damage": "повреждения после столкновения",
    "Engine": "двигатель",
    "Gearbox": "коробка передач",
    "Hydraulics": "гидравлика",
    "Brakes": "тормоза",
    "Power Unit": "силовая установка",
    "Disqualified": "дисквалификация",
}


def number(value: float, digits: int = 1) -> str:
    """`4.348` → `4,3`; negative numbers get a true minus sign."""
    text = f"{value:.{digits}f}".replace(".", DECIMAL_COMMA)
    return text.replace("-", MINUS)


def signed(value: float, digits: int = 2) -> str:
    """Signed difference: `+1,02`, `−0,31`; zero stays unsigned."""
    text = f"{abs(value):.{digits}f}".replace(".", DECIMAL_COMMA)
    if float(text.replace(DECIMAL_COMMA, ".")) == 0:
        return text
    return f"{'+' if value > 0 else MINUS}{text}"


def unsigned(value: float, digits: int = 2) -> str:
    """Magnitude only, for phrases like «на 0,31 позиции выше»."""
    return number(abs(value), digits)


def percent(share: float) -> str:
    """Whole percent; tiny non-zero shares read `<1%`."""
    value = share * PERCENT
    if 0 < value < 0.5:
        return "<1%"
    return f"{round(value)}%"


def lap_time(seconds: float) -> str:
    """`95.14` → `1:35,140`."""
    minutes = math.floor(seconds / S_PER_MIN)
    rest = seconds - minutes * S_PER_MIN
    return f"{minutes}:{rest:06.3f}".replace(".", DECIMAL_COMMA)


def long_date(iso: str) -> str:
    """`2025-04-13` → `13 апреля 2025`."""
    day = date.fromisoformat(iso)
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def plural(count: int, one: str, few: str, many: str) -> str:
    """Russian plural form: 1 круг, 3 круга, 5 кругов (grammar, not tunable numbers)."""
    mod10, mod100 = count % 10, count % 100
    if mod10 == 1 and mod100 != 11:
        return one
    if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
        return few
    return many


def compounds(names: tuple[str, ...]) -> str:
    """`('SOFT', 'MEDIUM')` → `Soft → Medium`."""
    return " → ".join(COMPOUND_NAMES.get(name, name.title()) for name in names) or "—"


def neutralisation(kind: str) -> str:
    """Name of a neutralisation kind."""
    return NEUTRALISATION_NAMES.get(kind, kind)


def status(text: str) -> str:
    """Jolpica status in Russian where known (e.g. `Accident` → `авария`)."""
    return STATUS_NAMES.get(text, text.lower())


def setup_reason(reason: str | None) -> str:
    """Why the simulator skipped a race, in Russian."""
    if not reason:
        return "причина не указана"
    if "INTERMEDIATE" in reason or "WET" in reason:
        return "мокрая гонка, а симулятор считает только сухие"
    if "UNKNOWN" in reason:
        return "в данных OpenF1 нет составов шин"
    if reason.startswith("No tyre model"):
        return "для трассы нет модели шин"
    return reason
