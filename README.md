# F1 Strategy Lab

[![CI](https://github.com/tachiroz/f1-strategy-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/tachiroz/f1-strategy-lab/actions/workflows/ci.yml)

Симулятор гоночной стратегии Formula 1. По данным реальных гонок оценивает деградацию шин,
моделирует стратегии пит-стопов и методом Монте-Карло считает распределение результатов:
финишная позиция, время, вероятность подиума.

Итог проекта: веб-дашборд, воспроизводимый пайплайн данных и автоматический текстовый разбор гонки.

![Стартовая страница дашборда](docs/screenshots/landing.png)

## Статус

| Этап | Что делаем | Статус |
|---|---|---|
| 1. Каркас | Структура, линтеры, тесты, CI, оболочка дашборда | ✅ готово |
| 2. Загрузка данных | FastF1 + Jolpica-F1 → SQLite, кэш, идемпотентная загрузка | ⏳ следующий |
| 3. Модель шин | Деградация по составам с поправкой на топливо и трассу | — |
| 4. Симулятор | Монте-Карло, пит-стопы, Safety Car, надёжность | — |
| 5. Дашборд | Сравнение стратегий, распределения, чувствительность к SC | — |
| 6. Разбор гонки | Текстовый отчёт по шаблону, экспорт в Markdown | — |

Подробный план и правила работы описаны в [CLAUDE.md](CLAUDE.md), история изменений в [CHANGELOG.md](CHANGELOG.md).

## Стек

| Часть | Технологии |
|---|---|
| Данные | FastF1, Jolpica-F1 API |
| Хранилище | SQLite через SQLAlchemy Core (позже, возможно, PostgreSQL) |
| Расчёты | Python 3.12, pandas, NumPy, SciPy |
| API | FastAPI |
| Дашборд | React + TypeScript (Vite), Tailwind CSS |
| Качество | ruff, pytest, Oxlint, Prettier, Vitest, pre-commit |
| CI | GitHub Actions (ubuntu + windows) |

Runtime-зависимости Python добавляются на том этапе, где они реально понадобятся.

## Структура

```
f1-strategy-lab/
  src/f1lab/          # Python-пакет
    config.py         # пути и константы (никаких магических чисел в коде)
    ingest/           # загрузка данных из API, кэширование
    db/               # схема, миграции, SQL-запросы
    models/           # деградация шин, темп, топливо
    sim/              # Монте-Карло, стратегии, Safety Car
    report/           # авто-разбор гонки
    api/              # FastAPI: JSON для дашборда
  web/                # дашборд: React + TypeScript + Vite + Tailwind
  sql/                # аналитические запросы (JOIN, CTE, оконные функции)
  tests/              # pytest
  notebooks/          # исследования
  data/               # кэш FastF1 и SQLite (в .gitignore)
  docs/               # документация и скриншоты
```

## Быстрый старт

Нужны Python 3.12, Node.js 24 LTS или новее (с npm) и Git.

### Python

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pre-commit install
```

Linux / macOS:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pre-commit install
```

### Дашборд

```bash
cd web
npm ci
npm run dev        # http://localhost:5173
```

## Проверки

Эти же проверки запускает CI на каждый push в `main` и на каждый PR.

| Python (из корня) | Web (из `web/`) |
|---|---|
| `ruff check .` | `npm run lint` |
| `ruff format --check .` | `npm run format:check` |
| `pytest` | `npm test` |
| `pre-commit run --all-files` | `npm run build` (с проверкой типов) |

Автоформатирование: `ruff format .` и `npm run format`.

## Конфигурация

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `F1LAB_DATA_DIR` | Каталог для кэша FastF1 и базы SQLite | `data/` в корне репозитория |

Данные, кэш, базы и `.env` в репозиторий не коммитятся.

## Как ведётся работа

- Один этап = одна ветка `feat/stage-N-name` → PR в `main`.
- Небольшие коммиты в стиле [Conventional Commits](https://www.conventionalcommits.org/ru/v1.0.0/): `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`.
- В `main` попадает только зелёное: линтеры и тесты проходят локально и в CI.

## Лицензия

[MIT](LICENSE). Неофициальный проект, не связан с Formula 1, FIA и командами.
Источники данных: [FastF1](https://github.com/theOehrly/Fast-F1) и [Jolpica-F1](https://github.com/jolpica/jolpica-f1).
