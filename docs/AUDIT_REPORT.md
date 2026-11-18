# Технический аудит кодовой базы `svend4/robot` (Wave 2)

**Дата аудита:** 2026-11-18  
**Базовая ветка:** `consolidate/ready-for-main` (`786fc31417fa402cf564c9c342cb8b0748e545d6`)  
**Ветка аудита:** `audit/code-review` (создана от `consolidate/ready-for-main`, не затрагивает `main`, `consolidate/ready-for-main`, `docs/add-readme-ru` и `claude/*`)  
**Объект сравнения:** отчёт `AUDIT.md` на ветке `claude/determined-hawking-q8xvi0` (`2b02ae49`, от 2026-11-06)

---

## 1. Резюме и состояние веток

| Ветка | Голова (`SHA`) | Содержание и статус |
|---|---|---|
| `main` | `b39283c...` | Исходные концептуальные `.md`, `LICENSE` (GNU AGPL v3), 3 архива `etd_proto_repo (1)/(5)/(6).zip`, 3 экспорта переписки `Роботы Hyundai *`. |
| `claude/add-hyundai-robot-docs-kvCBq` | `9efce0c0...` | Основная ветка разработки до `v0.95.0` (~140 коммитов): CLI, валидатор, JSON Schema Draft 2020-12, Ed25519 подпись/токены, FastAPI API (22 файла), `marketplace/`, `adapters/`, `sim/`, `tests/`. |
| `claude/determined-hawking-q8xvi0` | `2b02ae49...` | Независимый аудит `AUDIT.md` от `2026-11-06`. |
| `consolidate/ready-for-main` | `786fc314...` | База поверх `kvCBq` + 3 коммита от `2026-11-18`: `b42348f0` (русский `README.md`), `71e0588c` (`docs/BRANCH_README_ORIG.md`), `786fc314` (`LICENSE` GNU AGPL v3 с `main`). |
| `audit/code-review` | (текущая) | Ветка Wave 2 аудита от `consolidate/ready-for-main` с данным отчётом и безопасными исправлениями `.gitignore` и `pyproject.toml`. |

**Главный вывод:** консолидация в `consolidate/ready-for-main` сохранила полную кодовую базу `kvCBq` и улучшила документацию на русском языке, но **все критические блокеры слияния в `main` остаются открытыми**: 5 структурно падающих/нестабильных проверок в CI, лицензионный конфликт `LICENSE` (`AGPL-3.0`) vs `pyproject.toml`/манифесты (`MIT`), уязвимости безопасности в `api/app.py`, `marketplace/skill_store.py` и `etd_reference_validator.py`, а также наличие zip-архивов и экспортов чата в корне дерева.

---

## 2. Структура кода и точки входа

### 2.1. Корневые модули и CLI (`etd_cli.py`)
- **`etd_cli.py`** (3232 строки, `click`): единый монолитный CLI (`etd = "etd_cli:cli"`), объединяющий базовый жизненный цикл пакетов (`validate`, `publish`, `verify`, `install`, `list`, `info`, `stations`, `keygen`, `serve`, `validate-context`, `audit-log`, `revoke`, `review`, `versions`, `sandbox-check`, `dashboard`) и около 15 групп операционных/маркетплейс-подкоманд (`rollout`, `publisher`, `feed`, `token`, `compose`, `platform`, `onrobot`, `fleet`, `deps`, `schedule`, `quota`, `ab`, `telemetry`, `health`, `circuit`, `retry`, `bulkhead`, `skill-config`, `tag`, `rating`, `flag`, `maintenance`, `notes`, `sla`).
- **Риск захламления рабочего дерева CLI-командами:** в `etd_cli.py` определены 17 каталогов хранения состояния по умолчанию относительно корня репозитория (`ROOT`), среди них `robot_cache/` (стр. 940), `deps/` (1176), `scheduler/` (1326), `quota/` (1493), `ab/` (1628), `telemetry/` (1856), `health/` (1971), `circuits/` (2117), `retry/` (2220), `bulkhead/` (2356), `skill_configs/` (2487), `skill_tags/` (2622), `skill_ratings_data/` (2749), `feature_flags_data/` (2845), `maintenance_data/` (2950), `operator_notes_data/` (3038), `sla_data/` (3146). Ни один из этих каталогов ранее не был внесён в `.gitignore`.
- **`etd_reference_validator.py`** (307 строк): проверка обязательных файлов пакета (`REQUIRED_FILES`), валидация Draft 2020-12 через `schemas/*.schema.json` (`schemas/manifest.schema.json` и др. — полноценные схемы, в отличие от заглушек внутри zip-архивов), семантические правила и скоринг совместимости (`A`/`B`/`C`/`D`).
- **`etd_demo_runner.py`** (104 строки): пакетный прогон `ETDReferenceValidator` по всем 8+ эталонным пакетам в `examples/` с подбором `runtime_context_*.json`.
- **`etd_middleware_contract.py`** (83 строки): абстрактный контракт `ETDMiddleware` (`read`, `publish`, `validate`) и загрузчик `load_middleware_adapter`.
- **`validate_examples.py`**: скрипт валидации примеров, вызываемый в CI.

### 2.2. REST API (`api/app.py` и 20 роутеров)
- **`api/app.py`** (273 строки, `FastAPI(..., version='0.95.0')`): базовые маршруты `/health`, `/validate`, `/store/skills`, `/store/skills/{skill_id:path}`, `/store/stations`, `/store/stations/{station_id}`, `/store/install`, `/store/policy`, `/store/sign` + 20 подключённых роутеров (`publisher`, `cross_platform`, `fleet`, `composer`, `telemetry`, `ab_testing`, `quota`, `scheduler`, `dependency`, `health_monitor`, `circuit_breaker`, `retry_policy`, `bulkhead`, `skill_config`, `skill_tags`, `skill_ratings`, `feature_flags`, `maintenance`, `operator_notes`, `sla`).
- **Находки по `api/app.py`:**
  1. **Path Traversal (Высокий):** в `POST /validate` (стр. 133–137) и `POST /store/sign` (стр. 252–261) параметры `package_path` и `key_path` принимаются произвольно без проверки `resolve().is_relative_to(ROOT)`. Кроме того, на эндпоинтах (включая `/store/sign`) отсутствует аутентификация/авторизация.
  2. **Обход проверки Ed25519 entitlement-токенов (Высокий):** в `api/app.py:88` (и аналогично в `etd_cli.py:248`) создаётся `_store = SkillStore(ROOT)` **без передачи `entitlement_pubkey_path`**. В результате `SkillStore._entitlement_verify_key` равен `None`, и в `marketplace/skill_store.py:177-205` проверка токена пропускает **любую непустую строку** без криптографической верификации Ed25519 (это фактически закреплено в `tests/test_api.py:134-140`, где тест передаёт `'entitlement_token': 'valid-token-123'`).
  3. **Внутреннее расхождение версий:** `FastAPI(..., version='0.95.0')` (стр. 39), но `GET /health` возвращает `'version': '0.5.0', 'validator_version': '0.5.0'` (стр. 118–119), что закреплено ассертом в `tests/test_api.py:34` (`assert body['version'] == '0.5.0'`).
  4. **Production-режим в `__main__` (стр. 274):** `uvicorn.run('api.app:app', host='0.0.0.0', port=8080, reload=True)` запускается с `reload=True`.

### 2.3. Валидация и подсистемы (`marketplace/`, `adapters/`, `sim/`, `keys/`)
- **`etd_reference_validator.py` — пробелы безопасности:**
  - `entrypoint_exists` (стр. 191–192): проверяет `(p / ep_file).exists()` без контроля выхода за пределы каталога пакета (`..`);
  - `capability_safe` (стр. 200–205): опирается только на регистрозависимый blacklist `FORBIDDEN_CAPS` (7 строк) и наличие `command.skill_intent`, но не использует whitelist допустимых `write`-возможностей (варианты регистра вроде `command.Servo_Torque` или неизвестные `oem.*` проходят);
  - **Fail-open режим при отсутствии `jsonschema` или файла схемы** (стр. 94–96, 168, 274–275): при отсутствии `jsonschema` `_jsonschema_validate` и `validate_runtime_context` молча возвращают успех;
  - `SandboxChecker` (`marketplace/sandbox.py`) не вызывается из `ETDReferenceValidator` и `SkillStore.validate_for_install`, хотя `sim/acceptance_runner.py` и другие модули динамически исполняют `policies/*.py` через `importlib`.
- **`keys/`:** в репозитории хранится только публичный ключ `keys/etd_verify_key.hex` (64 байта); приватный ключ `keys/etd_signing_key.hex` исключён `.gitignore`.

---

## 3. Упаковка, зависимости и CI/тесты

### 3.1. Пробелы `pyproject.toml` и `requirements.txt`
1. **Лицензионное противоречие:** коммит `786fc314` в `consolidate/ready-for-main` синхронизировал `LICENSE` с `main` (**GNU AGPL v3**), однако `pyproject.toml:11,21` по-прежнему декларирует `license = {text = "MIT"}` и `"License :: OSI Approved :: MIT License"`, а манифесты пакетов в `examples/` используют MIT.
2. **Дрейф версий:** `pyproject.toml:7` = `0.5.0`; `api/app.py:39` и `CHANGELOG.md` = `0.95.0`; `api/app.py:118` (`/health`) = `0.5.0`; `docs/BRANCH_README_ORIG.md:2` = `v0.70.0`.
3. **Неполный `py-modules` и упаковка каталогов:** до текущего аудита `[tool.setuptools].py-modules` перечислял только `etd_cli`, `etd_reference_validator`, `validate_examples`, пропуская корневые модули `etd_demo_runner` и `etd_middleware_contract`. Кроме того, `packages.find` включает `scripts*`, где отсутствует `__init__.py` (работает только как PEP 420 namespace package), а `integrations/ros2/etd_ros2_bridge` в установку не включён.
4. **Зависимости:** `requirements.txt` содержит `pytest>=8.0.0` и `matplotlib>=3.8.0` в одном плоском списке без lock-файла (хотя в `pyproject.toml` они вынесены в `[project.optional-dependencies] dev/all`).

### 3.2. Анализ CI (`.github/workflows/validate-examples.yml`) и тестов
Workflow запускает на `ubuntu-latest` (Python 3.11): `validate_examples.py` → `pytest tests/ -v` → `sim/report_runner.py` → `sim/marketplace_demo.py` → `sim/acceptance_runner.py` → `sim/visualizer.py`.

По коду `consolidate/ready-for-main` подтверждены следующие причины падений/нестабильности:
1. **`tests/test_entitlement_token.py::TestTokenCLI` (стр. 322–367):** вызывает `etd_cli.py token issue`, который по умолчанию (`etd_cli.py:709,715`) открывает `keys/etd_signing_key.hex`. Файл исключён `.gitignore` и отсутствует в чистом клоне → `FileNotFoundError` в 4 CLI-тестах (`test_token_issue_prints_token`, `test_token_issue_json_flag`, `test_token_issue_custom_station_and_org`, `test_token_verify_valid`).
2. **`tests/test_dashboard.py::TestDashboardRealData::test_real_repo_rollout_entries` (стр. 398–401):** ожидает `len(snap.rollout_entries) >= 1` из `ROOT / 'marketplace' / 'rollout_state.json'`, но этот файл также исключён `.gitignore` и отсутствует в репозитории.
3. **Запись тестами в отслеживаемые JSON:** прогоны тестов перезаписывают рабочие файлы репозитория (`fleet/fleet_deployments.json` вырос до 83 725 Б, `marketplace/submissions.json` — до 247 861 Б).
4. **Недетерминированность `sim/acceptance_runner.py`:** в `examples/etd.inspect.vision/policies/chs_adapter.py:37,88-93` функция `_classify_defects` без фиксированного seed вычисляет `confidence = round(0.93 + random.uniform(-0.04, 0.04), 3)` (интервал `[0.89, 0.97]`) при `confidenceThreshold = 0.92` (~37.5% вероятность прерывания по `low_classification_confidence`) и дополнительно с вероятностью 8% (`random.random() < 0.08`) добавляет дефект `scratch`.

---

## 4. Сравнение с `AUDIT.md` на ветке `claude/determined-hawking-q8xvi0`

| Пункт из `AUDIT.md` (2026-11-06) | Статус в `consolidate/ready-for-main` (2026-11-18) | Уточнения настоящего аудита |
|---|---|---|
| `main` не содержит проекта; разработка не слита (`kvCBq`) | **Частично решено:** `consolidate/ready-for-main` объединяет `kvCBq` с `README.md` и `LICENSE`, но в `main` ещё не влита. | Подтверждено; оригинальный `README.md` из `kvCBq` сохранён в `docs/BRANCH_README_ORIG.md`. |
| Отсутствует осмысленный `README.md` | **Решено:** добавлен русский `README.md` из `docs/add-readme-ru` (`b42348f0`). | В `README.md` указано, что код находится на `kvCBq`, а не на `main`; после слияния формулировку нужно обновить. |
| Лицензионный конфликт (AGPL-3.0 в `main` vs MIT в коде) | **Не решено:** `LICENSE` синхронизирован на AGPL-3.0 (`786fc314`), но `pyproject.toml` и пакеты остаются MIT. | Требуется осознанное решение владельца до слияния в `main`. |
| Красный CI (4 теста `TestTokenCLI` + 1 тест `TestDashboardRealData` + `acceptance_runner`) | **Не решено:** тесты и политики в `consolidate/ready-for-main` не менялись. | Выявлена вторая причина нестабильности `etd.inspect.vision`: `confidence` `[0.89, 0.97]` при пороге `0.92` (~37.5% сбоев), помимо `random() < 0.08`. |
| Запись тестами в tracked-файлы | **Не решено:** `fleet_deployments.json` (83 КБ) и `submissions.json` (248 КБ) всё ещё раздуты. | Дополнительно найдено 17 дефолтных state-директорий `etd_cli.py`, отсутствовавших в `.gitignore`. |
| Zip-архивы и экспорт чата `Роботы Hyundai *` в корне | **Не решено:** все 3 `.zip` и 3 файла `Роботы Hyundai *` остались в дереве. | Пробелы/скобки/кириллица в именах сохраняются. |
| Пробелы безопасности валидатора (`SandboxChecker`, path traversal `entrypoint`, blacklist) | **Не решено:** код `etd_reference_validator.py` не изменялся. | Дополнительно обнаружены path traversal в `api/app.py` (`/validate`, `/store/sign`) и отключение Ed25519 проверки токенов в `SkillStore(ROOT)` (`api/app.py:88`, `etd_cli.py:248`). |
| Дрейф версий (`0.5.0` vs `0.70.0` vs `0.95.0`) | **Не решено:** `pyproject.toml` (`0.5.0`), `api/app.py` (`0.95.0` и `/health` `'0.5.0'`). | Установлено, что `tests/test_api.py:34` жёстко проверяет `'0.5.0'` в `/health`. |

---

## 5. Выполненные безопасные исправления на `audit/code-review`

В коммите `16d8e89adef36643287cc725f685d956082a23e4` на ветке `audit/code-review` применены точечные неинвазивные правки, полностью основанные на прочитанных файлах:

1. **`.gitignore`:** добавлены правила для `.pytest_cache/`, `.ruff_cache/`, `build/`, `dist/`, `*.egg`, `release_out/`, `*.feed.json` и 17 дефолтных каталогов runtime-состояния `etd_cli.py` / `api/*` (`robot_cache/`, `deps/`, `scheduler/`, `quota/`, `ab/`, `telemetry/`, `health/`, `circuits/`, `retry/`, `bulkhead/`, `skill_configs/`, `skill_tags/`, `skill_ratings_data/`, `feature_flags_data/`, `maintenance_data/`, `operator_notes_data/`, `sla_data/`).
2. **`pyproject.toml`:** в `[tool.setuptools].py-modules` добавлены пропущенные корневые модули `"etd_demo_runner"` и `"etd_middleware_contract"` (помимо `"etd_cli"`, `"etd_reference_validator"`, `"validate_examples"`).

*Примечание:* файлы `pyproject.toml` (поле `license` и `version`) и `api/app.py` (`/health` `'version': '0.5.0'` и `_store = SkillStore(ROOT)`) намеренно не менялись, так как выбор лицензии требует решения владельца, а изменение `/health` и `SkillStore(ROOT)` затрагивает контракты существующих тестов `tests/test_api.py:34,134-140`.

---

## 6. Рекомендации перед слиянием в `main`

1. **Довести CI до зелёного состояния (P0):**
   - в `tests/test_entitlement_token.py::TestTokenCLI` генерировать временный Ed25519 ключ в `tmp_path` и передавать `--key` / `--pubkey` (или monkeypatch-путь);
   - в `tests/test_dashboard.py::TestDashboardRealData::test_real_repo_rollout_entries` использовать временный `rollout_state.json` (либо фикстурный пример);
   - в `examples/etd.inspect.vision/policies/chs_adapter.py` сделать выборку `random` детерминированной/управляемой (через `job_context` / seed или mock-режим для nominal-сценария);
   - перевести тестовые прогоны `fleet`, `submissions`, `reports` в `tmp_path` и очистить накопленные тестовые артефакты из `fleet/fleet_deployments.json` и `marketplace/submissions.json`.
2. **Принять решение по лицензии и версии (P0):** привести `LICENSE`, `pyproject.toml`, `api/app.py` (`/health` + `tests/test_api.py`), `README.md` и манифесты `examples/*` к единой лицензии (AGPL-3.0 или MIT) и единому источнику версии (`0.95.0`).
3. **Устранить уязвимости безопасности API и валидатора (P1):**
   - добавить `resolve().is_relative_to(ROOT)` в `api/app.py` (`/validate`, `/store/sign`) и `resolve().is_relative_to(p.resolve())` в `etd_reference_validator.py:192` (`entrypoint_exists`), убрать `reload=True` из `api/app.py:__main__`, закрыть `/store/sign` и административные роуты авторизацией;
   - передавать `entitlement_pubkey_path=ROOT / 'keys' / 'etd_verify_key.hex'` в `SkillStore` по умолчанию (и в `api/app.py`, `etd_cli.py`), обновив `tests/test_api.py:134-140` на реальный подписанный токен;
   - заменить blacklist в `etd_reference_validator.py` на whitelist допустимых `write`-capabilities + регистронезависимую нормализацию, убрать fail-open при отсутствии `jsonschema`/схем и подключить `SandboxChecker` в `validate`/`install`.
4. **Очистить дерево репозитория (P2):** вынести `etd_proto_repo (*.zip)` в GitHub Releases, удалить из публичного корня дублирующиеся личные экспорты переписки `Роботы Hyundai *` (при необходимости оставить очищенный конспект в `docs/`), а также обновить `README.md` после слияния в `main`.
