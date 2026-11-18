# ETD Robotics Skill Runtime (`robot`)

Прототип фреймворка прикладного уровня (application-layer) для упаковки, валидации, симуляции, дистрибуции через маркетплейс и развёртывания навыков роботов (**robot skills**) поверх существующих OEM-стеков управления.

> [!NOTE]
> ETD не является низкоуровневой операционной системой робота — это прикладная надстройка с контрактами безопасности и валидации поверх OEM-контроллера. На ветке `main` находятся документы концепции, сводки и три zip-архива прототипа; основная распакованная кодовая база находится в неслитой ветке [`claude/add-hyundai-robot-docs-kvCBq`](../../tree/claude/add-hyundai-robot-docs-kvCBq).

## Содержимое ветки `main`

| Файл | Назначение |
|---|---|
| `documentation-blueprint.md` | Карта документации для партнёров, интеграторов, разработчиков навыков и специалистов по безопасности |
| `marketplace-architecture.md` | Архитектура слоя маркетплейса навыков (индекс, политики, валидатор) |
| `ip-protection-and-package-security.md` | Модель защиты интеллектуальной собственности и безопасности пакетов |
| `skill-economics-licensing.md` | Экономика и модели лицензирования навыков |
| `store-governance-review-model.md` | Модель ревью и управления каталогом магазина навыков |
| `unitree-skill-marketplace-analysis.md` | Сравнение промышленного подхода ETD и потребительского магазина навыков Unitree |
| `marketplace_policy.json` | Политика установки и уровни ревью (`low`, `medium`, `high`) |
| `skill_store_index.json` | Эталонный индекс из 4 пакетов (`etd.pickplace.basic`, `etd.assembly.precision`, `etd.inspect.vision`, `etd.cobot.safeassist`) |
| `report_summary.json`, `report_summary.md` | Сводка прохождения валидации (уровень `A`), сценариев и отказов |
| `etd_proto_repo (6).zip`, `(5).zip`, `(1).zip` | Три выгруженные версии прототипа ETD (хронологически от `(6)` к `(1)`) |
| `Роботы Hyundai (1).md`, `(1).json`, `(2).txt` | Экспорт обсуждения по робототехнике Hyundai в трёх форматах |

## Ветки репозитория

- `claude/add-hyundai-robot-docs-kvCBq` — основная неслитая ветка разработки (около 140 коммитов, до `v0.95.0`): Python-кодовая база с CLI (`etd_cli.py`), эталонным валидатором (`etd_reference_validator.py`, `validate_examples.py`), JSON Schema (`schemas/`), подписями Ed25519 (`keys/`), FastAPI REST API (`api/`), подсистемами `marketplace/`, `fleet/`, `sim/`, `adapters/`, `integrations/`, 9 пакетами в `examples/`, `docs/INDEX.md` и тестами `tests/`.
- `claude/determined-hawking-q8xvi0` — ветка с отчётом технического аудита [`AUDIT.md`](../../blob/claude/determined-hawking-q8xvi0/AUDIT.md) от 2026-11-06 (инвентаризация `main`, архивов и ветки разработки, проверка валидатора, разбор падений CI и лицензионного конфликта).
- `codex/readme-overview-20261118` ([PR #2](../../pull/2), draft) — краткий обзорный `README.md`.
- `svend4-patch-1` — ветка от закрытого/слитого [PR #1](../../pull/1).

## Стек и команды запуска

- **Стек (по коду прототипа и ветке разработки):** Python 3, PyYAML, `jsonschema`, PyNaCl (подписи Ed25519), FastAPI, Uvicorn, Click, `httpx`, `matplotlib`, `pytest`.

```bash
# Проверка архива прототипа (1) после распаковки
unzip -q "etd_proto_repo (1).zip" -d /tmp/etd-v1
cd /tmp/etd-v1/etd_proto_repo
pip install -r requirements.txt
python validate_examples.py
python sim/report_runner.py
```

```bash
# Команды в ветке claude/add-hyundai-robot-docs-kvCBq
pip install -r requirements.txt
pytest -q
python validate_examples.py
python etd_cli.py verify examples/etd.pickplace.basic
python etd_cli.py sandbox-check examples/etd.pickplace.basic
```

## Лицензия

- В ветке `main` размещён файл `LICENSE` (**GNU Affero General Public License v3.0 / AGPL-3.0**).
- В `pyproject.toml`, `LICENSE` архива `(1)` и манифестах пакетов ветки `claude/add-hyundai-robot-docs-kvCBq` указана лицензия **MIT** (конфликт лицензий зафиксирован в `AUDIT.md`).
