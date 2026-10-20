# Changelog

Все заметные изменения проекта. Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версии: [SemVer](https://semver.org/lang/ru/).

## [Unreleased]

## [0.1.0] - 2026-10-20

Этап 1: каркас.

### Добавлено

- Python-пакет `f1lab` (src-layout) с подпакетами `ingest`, `db`, `models`, `sim`, `report`, `api`.
- `f1lab.config`: пути к данным, кэшу FastF1 и SQLite, переопределение через `F1LAB_DATA_DIR`.
- `pyproject.toml`, `requirements.txt` и `requirements-dev.txt`; ruff (линтер + форматтер), pytest.
- Хуки pre-commit: ruff и базовая гигиена файлов (пробелы, концы строк, LF, yaml/toml).
- Веб-приложение `web/`: Vite + React + TypeScript, Tailwind CSS, Oxlint, Prettier, Vitest.
- Стартовая страница дашборда: дизайн-система (тёмная тема, цвета составов шин, шрифт Geist),
  иллюстрация стратегии, дорожная карта этапов.
- GitHub Actions: проверки Python и web на ubuntu и windows.
- `CLAUDE.md`, `LICENSE` (MIT), `README.md`, этот `CHANGELOG.md`.

### Изменено

- Стек в `CLAUDE.md`: pip + requirements вместо uv; дашборд на React + FastAPI вместо Streamlit.
