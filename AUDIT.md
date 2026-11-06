# Аудит репозитория `svend4/robot`

| | |
|---|---|
| Дата аудита | 2026-11-06 |
| Объект | ветка `main` @ `b39283c` и неслитая ветка `claude/add-hyundai-robot-docs-kvCBq` @ `9efce0c` |
| Видимость репозитория | public |
| Ветка с этим отчётом | `claude/determined-hawking-q8xvi0` |

## 1. Главные выводы

1. **`main` не содержит проекта.** В нём лежат три zip-архива с тремя разными версиями прототипа «ETD Robotics Skill Runtime», личный экспорт переписки с ChatGPT в трёх форматах и 11 файлов, скопированных россыпью из разных версий архивов. README состоит из слова `info`. Кода, тестов и CI на `main` нет.
2. **Вся реальная работа лежит в неслитой ветке** `claude/add-hyundai-robot-docs-kvCBq` (11–13 мая 2026): около 140 коммитов, 297 файлов, 73,6 тыс. добавленных строк, 2446 pytest-тестов, CI, настоящие JSON Schema, подпись пакетов Ed25519, REST API и CLI. Ветка отстаёт от `main` на один коммит (LICENSE) и никогда не сливалась.
3. **CI этой ветки красный.** Из 127 запусков GitHub Actions успешными были только № 1–4 и № 7 (11 мая); все последующие 120 завершились `failure`. Локальный прогон: 2441 passed, 5 failed. Причины: тесты зависят от файлов, которые исключены `.gitignore` (приватный ключ, `rollout_state.json`), а acceptance-прогон недетерминирован (`random` без seed).
4. **Лицензионный конфликт.** `main/LICENSE` = AGPL-3.0 (добавлен 2 ноября 2026). Архив (1), ветка, `pyproject.toml` и манифесты пакетов = MIT. Манифесты архива (5) = `Proprietary`. Документы проекта рекомендуют MIT/Apache для открытого ядра. При слиянии ветки будет конфликт, и его надо решить осознанно.
5. **Прототип в архивах запускается, но часть заявленного не реализована:** «схемы» в `schemas/` — пустые заглушки, которые никто не читает; валидатор проверяет только декларации, а не код политики; три из четырёх «failure scenarios» — строковые константы; политики четырёх «разных» пакетов побайтно идентичны.
6. **Секретов, ключей и персональных контактов в файлах не найдено.** Приватный ключ подписи в ветке корректно исключён из репозитория.

**Рекомендуемый порядок действий:** выбрать лицензию → довести ветку до зелёного CI → слить её в `main` → убрать zip-архивы и экспорт чата из дерева → переписать README. Подробности в разделе 8.

## 2. Методика

Проверено:

- все 18 файлов `main`, их кодировки, валидность JSON, происхождение (побайтное сравнение с содержимым архивов);
- три архива распакованы в изолированные каталоги с проверкой на path traversal и сравнены между собой (`diff -r`);
- во всех трёх версиях прототипа выполнены все команды из README (quick start), код скомпилирован (`py_compile`), просканирован на опасные конструкции (`eval`, `exec`, `subprocess`, сеть, небезопасный YAML);
- валидатор актуальной версии проверен девятью негативными сценариями (намеренно испорченные пакеты);
- ветка `claude/add-hyundai-robot-docs-kvCBq` выгружена в отдельный worktree, зависимости установлены в venv, выполнены полный `pytest`, все шаги её CI-воркфлоу, проверка подписей всех пакетов и статический sandbox-анализ;
- через GitHub API проверены PR, issues, ветки и история запусков Actions;
- в текстовых файлах выполнен поиск секретов (API-ключи, токены, приватные ключи), e-mail и телефонов.

Не проверялось: фактическая достоверность утверждений о Hyundai/Unitree в экспорте чата; уязвимости сторонних зависимостей (pip-audit не запускался).

## 3. Инвентаризация `main`

| Файл | Размер | Что это | Откуда |
|---|---:|---|---|
| `README.md` | 13 Б | `# robot` / `info` | — |
| `LICENSE` | 34 КБ | GNU AGPL v3 | коммит от 2026-11-02 |
| `etd_proto_repo (6).zip` | 44 КБ | прототип, 79 файлов, собран 1 апр 2026 (самая старая версия) | выгрузка из ChatGPT |
| `etd_proto_repo (5).zip` | 58 КБ | прототип, 112 файлов, собран 11 мая 2026 12:38 | выгрузка из ChatGPT |
| `etd_proto_repo (1).zip` | 156 КБ | прототип, 152 файла, собран 11 мая 2026 13:03 (самая новая версия) | выгрузка из ChatGPT |
| 6 файлов `*.md` (`documentation-blueprint`, `ip-protection-and-package-security`, `marketplace-architecture`, `skill-economics-licensing`, `store-governance-review-model`, `unitree-skill-marketplace-analysis`) | 0,4–7 КБ | копии `docs/` | побайтно идентичны архиву (1) |
| `marketplace_policy.json`, `skill_store_index.json` | 0,4–1,4 КБ | копии `marketplace/` | идентичны архиву (5), то есть устарели относительно (1) |
| `report_summary.json`, `report_summary.md` | 0,2–1,5 КБ | копии `reports/` | идентичны архиву (6), самому старому |
| `Роботы Hyundai (1).md`, `(2).txt`, `(1).json` | 122 / 112 / 187 КБ | один и тот же экспорт чата ChatGPT (65 сообщений, 1 апреля и 11 мая 2026) в трёх форматах | экспорт браузерного расширения |

Числа в скобках `(1)`, `(5)`, `(6)` — счётчик загрузок браузера, а не версии. Хронология по датам внутри архивов: (6) → (5) → (1).

История `main`: 4 коммита (`Initial commit`, `Add files via upload`, merge PR #1, `Add GNU Affero General Public License v3`). `.gitignore` отсутствует. Issues: 0. Ветки на GitHub: `main`, `svend4-patch-1` (слита, не удалена), `claude/add-hyundai-robot-docs-kvCBq` (не слита), `claude/determined-hawking-q8xvi0` (этот отчёт).

## 4. Находки: `main`

Уровни: **В** — высокий, **С** — средний, **Н** — низкий.

**В-1. Репозиторий как хранилище выгрузок.** Исходники существуют только внутри zip. GitHub не индексирует их содержимое, не запускает CI-воркфлоу из архива, не показывает diff между версиями. Три архива содержат три несовместимые редакции одних и тех же файлов (например, валидатор: 130, 166 и 114 строк соответственно).

**В-2. Неслитая ветка с реальной работой.** См. раздел 6. Пока она не слита, любой, кто откроет `main`, увидит пустой проект.

**В-3. Лицензионный конфликт.** AGPL-3.0 на `main` против MIT в ветке, `pyproject.toml`, LICENSE архива (1) и манифестах всех четырёх пакетов (`license: MIT`); при этом манифесты архива (5) содержат `license: Proprietary`. Документы `skill-economics-licensing.md` и `store-governance-review-model.md` предполагают открытое ядро под MIT/Apache/BSD. Пока лицензия не определена, сторонние разработчики не могут использовать пакетный формат.

**С-1. Личные артефакты в публичном репозитории.** Экспорт чата содержит ссылку на приватную беседу `chatgpt.com/c/…`, метки времени, ссылки на другой репозиторий автора (`svend4/data2`) и 56 мёртвых ссылок вида `sandbox:/mnt/data/...`. Один и тот же разговор хранится трижды (около 420 КБ). Секретов, e-mail и телефонов в этих файлах нет, но место им не в публичном проекте, а в приватных заметках или в `docs/history/` в одном формате.

**С-2. Корневые копии взяты из разных версий и противоречат друг другу.** Документы (из архива 1) описывают поля `licenseModel`, `pricingModel`, `requiresEntitlement` в индексе магазина, а лежащий рядом `skill_store_index.json` (из архива 5) этих полей не содержит. `report_summary.json` (из архива 6) описывает структуру отчёта, которой в актуальной версии уже нет.

**Н-1. Гигиена.** Имена файлов с пробелами, скобками и кириллицей неудобны для скриптов и CI. Описание репозитория на GitHub — `info`. Нет `.gitignore`. Ветка `svend4-patch-1` слита, но не удалена.

## 5. Находки: прототип в архиве (1), ETD v0.1

Это самая поздняя из трёх редакций, и именно из неё была извлечена ветка (валидатор первого коммита ветки побайтно совпадает с архивом).

### Что работает

- Все команды из README выполняются с кодом 0: `validate_examples.py`, `sim/run_sim_demo.py`, `sim/run_assembly_demo.py`, `sim/scenario_runner.py`, `sim/failure_scenarios.py`, `sim/report_runner.py`, `sim/marketplace_demo.py`. Регенерированный отчёт совпадает с поставляемым.
- `scripts/release_package.py` валидирует пакет перед упаковкой и отказывается упаковывать невалидный (проверено на пакете с запрещённой capability: exit 1, zip не создан).
- Проверки архитектуры версий (5) и (6) также проходят своими командами.

### Негативные тесты валидатора (архив 1)

| Сценарий | Результат |
|---|---|
| в `write` добавлена `command.servo_torque` | отклонён ✓ |
| `payloadKg: 50` при `payloadKgMax: 8` | отклонён ✓ |
| версия в `manifest.yaml` ≠ версии в `skill.json` | отклонён ✓ |
| `forceWindowN: [10, 2]` | отклонён ✓ |
| в runtime-контексте нет требуемого сервиса | уровень D, отклонён ✓ |
| `robot_class: quadruped` | уровень D, отклонён ✓ |
| `entrypoint: ../../etd_reference_validator.py:main` | отклонён, но лишь потому, что файл по этому пути не нашёлся: проверки выхода за пределы пакета нет ✗ |
| `command.Servo_Torque`, `oem.direct_joint_torque` в `write` | **пропущен, уровень A** ✗ |
| `timeout_sec: -5`, `speed_profile: ludicrous`, `force_profile: 12345`, `payloadKgMax: 100000`, `robotClass: toaster` | **пропущен, уровень A** ✗ |

### Находки

**П-1. Схемы-заглушки.** Все пять файлов `schemas/*.schema.json` в архивах (1) и (5) содержат только `"type": "object"`; в (6) — лишь список `required`. Ни один `.py` ни в одной версии не читает каталог `schemas/`. `jsonschema` в `requirements.txt` архива (5) — мёртвая зависимость. При этом документация называет их «machine-readable schemas» и ставит в список обязательного для публичного релиза.

**П-2. Валидатор проверяет только декларации.** Файл политики `policies/chs_adapter.py` не анализируется и не исполняется в песочнице; «capability firewall» — это чёрный список из пяти точных строк. Нет белого списка допустимых `write`, нет нормализации регистра, любое незнакомое значение проходит.

**П-3. Диапазоны значений не проверяются.** Отрицательный таймаут, произвольные строки режимов, число вместо строки — всё проходит с уровнем A. В архиве (5) проверялись диапазон `timeout_sec` 1..300, допустимые `robotClass`, `family`, формат `apiVersion`; в (1) это потеряно, то есть пересборка в ChatGPT откатила проверки.

**П-4. «Failure scenarios» и acceptance-тесты частично фиктивны.** В `sim/failure_scenarios.py` три из четырёх сценариев (`human_too_close`, `payload_out_of_range`, `station_incompatible`) — строковые константы, реально проверяется только `missing_service`. Файлы `tests/acceptance_tests.yaml` не читает ни один скрипт ни в одной версии; валидатор лишь проверяет их наличие. Станционные профили (`station_profiles/`) валидатором и магазином не используются.

**П-5. Четыре пакета с одной политикой.** В архиве (1) `policies/chs_adapter.py` всех четырёх пакетов побайтно идентичны (md5 `f07ed563…`): «assembly», «inspect» и «cobot» — копии pickplace. В (5) и (6) политики различались, то есть это ещё одна регрессия пересборки.

**П-6. Документационный разброс.** В `docs/` 40 файлов: 9 заглушек короче 40 слов (`architecture.md` — 22 слова, `package-format.md` — 17), пять документов про лицензирование, четыре про «documentation», четыре про Unitree, четыре про защиту пакетов, в основном пересказывающие друг друга. `CHANGELOG.md` состоит из 9 секций с несовместимыми метками (`0.1.0`, `v0.1 marketplace licensing update`, `0.1.4`, `0.1.1-docs`, `0.2.0-docs-marketplace`…) в непоследовательном порядке.

**П-7. Несогласованные словари маркетплейса.** `skill_store_index.json` использует `licenseModel: commercial`, которого нет в `marketplace_policy.json → licensePolicy.allowedLicenseTypes` (там `commercial_closed_source`, `commercial_source_available`). Из восьми JSON в `marketplace/` код читает три; `commercial_policy.json`, `license_policy.json`, `license_profiles.json`, `sample_*_listing.json` не используются. Манифесты всех четырёх пакетов объявляют `license: MIT`, а индекс магазина называет три из них `commercial` / `enterprise_private` с `binary_only` / `private_source`.

**П-8. Мелкие дефекты.**
- `sim/event_replay.py` падает при прямом запуске (`ModuleNotFoundError: adapters`), единственный скрипт без вставки корня в `sys.path`.
- `marketplace/skill_store.py` игнорирует аргументы командной строки: `--help`, `list`, `validate` печатают одно и то же, хотя README архива (5) документирует подкоманды.
- В отчёте валидатора поле `schema.skill` содержит строку entrypoint вместо `true/false`.
- Валидатор ищет `telemetry.emits` в манифесте, а манифесты (1) используют `telemetry.events`; проверка проходит только за счёт `telemetry/events.json`.
- `.gitignore` исключает `release_out/*.zip`, но архив их содержит.

## 6. Находки: ветка `claude/add-hyundai-robot-docs-kvCBq`

### Состав

| Показатель | Значение |
|---|---|
| Коммиты сверх `main` | ~140 (11–13 мая 2026) |
| Изменённые файлы | 297 (+73 639 / −181 строк) |
| Python: код / тесты | 22 062 / 21 788 строк, 138 файлов |
| Тестовые функции | 2415 `def test_` в 42 файлах; pytest собирает 2446 |
| Пакеты-примеры | 9 (4 исходных + Atlas walk-fetch + 3 Hyundai + 1 составной) |
| Подсистемы | validator с JSON Schema, подпись Ed25519, SkillStore, REST API (FastAPI, 23 модуля), CLI (39 команд), fleet, rollout, ревокация, аудит-лог, A/B, SLA, квоты, рейтинги, теги, feature flags, ROS 2 bridge, визуализатор |
| Документы | 44 (все 40 из архива + 4 новых) + `docs/INDEX.md` |
| Зависимости | PyYAML, jsonschema, PyNaCl, fastapi, uvicorn[standard], click, httpx, matplotlib, pytest; все с `>=`, без lock-файла |

### Результаты проверки

| Проверка | Результат |
|---|---|
| `pytest` (локально, Python 3.13, 32 с) | **5 failed, 2441 passed** |
| `validate_examples.py` | все пакеты valid, уровень A |
| `sim/report_runner.py`, `sim/marketplace_demo.py`, `sim/visualizer.py` | exit 0 |
| `sim/acceptance_runner.py` (3 прогона) | 39/39, **38/39**, 39/39 — нестабилен |
| Подписи `package.sig` против `keys/etd_verify_key.hex` | 8 из 9 валидны; `etd.composed.fetch_inspect_place` без подписи |
| `etd sandbox-check` на политике с `import subprocess` / `os.system` | ловит обе конструкции |
| `etd validate` на той же политике | **All checks passed, уровень A** |
| GitHub Actions | 127 запусков; success только № 1–4 и № 7; последние 120 — failure |

### Находки

**Б-1. Красный CI на протяжении всей истории после 11 мая.** Последний зелёный запуск — № 7 (коммит `d3d6291`). Все коммиты с `v0.5.0` по `v0.95.0` отправлялись поверх красного CI, в том числе ~30 коммитов `chore: update test-generated data files`.

**Б-2. Тесты зависят от файлов, исключённых из репозитория.** Четыре теста `tests/test_entitlement_token.py::TestTokenCLI` требуют `keys/etd_signing_key.hex` (в `.gitignore`), падают с `FileNotFoundError`. Тест `tests/test_dashboard.py::TestDashboardRealData::test_real_repo_rollout_entries` требует `marketplace/rollout_state.json` (тоже в `.gitignore`). На чистом клоне и в CI они не могут пройти.

**Б-3. Тесты пишут в трекаемые файлы.** Один прогон меняет `fleet/fleet_deployments.json` (+110 строк), `marketplace/submissions.json` (+219), `fleet/fleet_registry.json`, `reports/report_summary.json`. Отсюда десятки коммитов «test-generated data». Хранилища должны создаваться во временном каталоге (`tmp_path`).

**Б-4. Недетерминированный acceptance-тест.** Политика `examples/etd.inspect.vision/policies/chs_adapter.py` вызывает `random.random() < 0.08` без seed; сценарий `defect_scan_nominal_pass` ожидает `completed` и примерно в 8 % прогонов получает `aborted`. CI-шаг `acceptance_runner` падает случайным образом.

**Б-5. Дрейф версий.** `README.md`: «Prototype v0.70.0», «2130 pytest tests» и «2446 tests» в разных местах; `pyproject.toml`: `0.5.0`; `api/app.py`: `0.95.0`; `CHANGELOG.md`: `0.95.0`.

**Б-6. Sandbox не входит в install-gate.** `SandboxChecker` вызывается только из CLI `sandbox-check` и из `review_pipeline`. Основной путь `validate` → `install` пакет с `subprocess`/`os.system` в политике пропускает с уровнем A. При этом `sim/acceptance_runner.py`, `sim/visualizer.py`, `sim/failure_scenarios.py` и ROS 2 action server загружают `policies/*.py` через `importlib` и исполняют его код без изоляции.

**Б-7. Подписи.** Схема рабочая (Ed25519, PyNaCl, проверка при установке в `SkillStore`), приватный ключ в репозитории отсутствует. Не описаны хранение и ротация ключа, нет подписи у составного пакета, CLI `publish` по умолчанию ждёт ключ по пути `keys/etd_signing_key.hex`.

**Б-8. Архивы и чат остались в дереве.** `.gitignore` ветки содержит `*.zip`, но три zip и три экспорта чата по-прежнему трекаются.

**Б-9. Избыточная поверхность.** За три дня код вырос с ~0,4 тыс. до 22 тыс. строк и 30+ подсистем (A/B-тесты, SLA, квоты, рейтинги, операторские заметки, окна обслуживания…) при отсутствии реального робота или мидлвари. Это характерный паттерн автогенерации «фича + N тестов» без приоритизации. Для прототипа формата skill-пакетов ядро — это validator, schemas, signing, store, CLI `validate`/`verify`/`install` и CI. Остальное стоит вынести в `experimental/` или удалить.

**Б-10. Документационный разброс унаследован.** 40 документов архива перенесены целиком; заглушки дописаны (коммиты v0.55–v0.56), но дубли не объединены. Добавлен `docs/INDEX.md`, что частично помогает навигации.

## 7. Безопасность: сводка

- **Секреты:** не найдены ни на `main`, ни в ветке (регулярные выражения для API-ключей, токенов, приватных ключей; единственное совпадение `sk-conditioning` — ложное срабатывание на слово «task-conditioning»). Приватный ключ подписи исключён `.gitignore`, в дереве только публичный.
- **Опасные конструкции в архивах:** отсутствуют. Нет `eval`/`exec`, сетевых вызовов, небезопасного YAML (`yaml.safe_load`); `subprocess` только в `sim/report_runner.py` архива (6) с `sys.executable` и фиксированными аргументами.
- **Ветка:** `subprocess.run` в `etd_cli.py publish` с фиксированным списком аргументов — инъекции нет; `os.system('clear')` в `marketplace/dashboard.py` — безвредно; загрузка кода пакетов через `importlib` — см. Б-6.
- **Данные:** публичный репозиторий содержит личный экспорт чата (С-1).
- **Zip-архивы:** проверены на path traversal и целостность (`testzip`), проблем нет.

## 8. Рекомендации по приоритету

1. **Определить лицензию.** Выбрать AGPL-3.0 или MIT и привести к одному значению `LICENSE`, `pyproject.toml`, манифесты пакетов и документы. Для стратегии «открытое ядро + коммерческие пакеты» из собственных документов проекта логичнее MIT/Apache-2.0; AGPL осмыслен, если цель — не дать закрыть форки.
2. **Довести ветку до зелёного CI** (оценка: 1–2 дня):
   - генерировать тестовый ключ в фикстуре pytest (или использовать `monkeypatch` пути к ключу) вместо зависимости от `keys/etd_signing_key.hex`;
   - тест dashboard переписать на временный `rollout_state.json`;
   - в `etd.inspect.vision` вынести генератор случайных чисел в параметр (или фиксировать seed в acceptance-прогоне);
   - все хранилища (`fleet/*.json`, `submissions.json`, `reports/`) в тестах направлять в `tmp_path`; удалить коммиты «test-generated data» из рабочего процесса;
   - синхронизировать версию: единственный источник в `pyproject.toml`, README и `api/app.py` читают её оттуда.
3. **Слить ветку в `main`** обычным merge-коммитом с сохранением истории, разрешив конфликт в `LICENSE` по решению из п. 1. Удалить `svend4-patch-1`. Включить защиту `main` (PR + зелёный CI).
4. **Очистить дерево.** Zip-архивы перенести в GitHub Releases (как «source snapshots») или в `archive/` с README о происхождении; экспорт чата вынести из публичного репозитория либо оставить один формат в `docs/history/` с пояснением. Переименовать файлы без пробелов и скобок.
5. **README и описание репозитория.** Что это (прототип формата skill-пакетов для роботов), статус (proof of concept, не для промышленного применения), quick start, структура, лицензия, ссылка на `docs/INDEX.md`. Добавить `.gitignore` и описание репозитория на GitHub.
6. **Укрепить валидатор** (актуально и для ветки):
   - белый список допустимых `write`-capabilities вместо чёрного списка; нормализация регистра;
   - проверка, что `entrypoint` не выходит за пределы каталога пакета (`Path.resolve()` + `is_relative_to`);
   - `sandbox-check` как обязательный этап `install`;
   - запуск `acceptance_tests.yaml` в CI детерминированно;
   - проверить, что JSON Schema ветки задают диапазоны (`timeout_sec`, `payloadKg`, перечисления режимов), и что валидатор при отсутствии `jsonschema` падает, а не молча пропускает проверку.
7. **Консолидировать документацию:** 44 файла → порядка 12 (architecture, package-format, validation, marketplace, licensing, security, governance, publisher guide, roadmap, competitive landscape, use cases, changelog). Один `CHANGELOG.md` по SemVer.
8. **Зависимости:** зафиксировать версии (`pip-compile` или `uv lock`), включить Dependabot, добавить `pip-audit` в CI.
9. **Сузить поверхность ветки:** оставить ядро (п. Б-9), остальное перенести в `experimental/` с явной пометкой или удалить до появления реального потребителя.

## 9. Воспроизведение

```bash
# архивы: распаковка в отдельные каталоги и сравнение
unzip -q "etd_proto_repo (1).zip" -d /tmp/v1 && unzip -q "etd_proto_repo (5).zip" -d /tmp/v5 && unzip -q "etd_proto_repo (6).zip" -d /tmp/v6
diff -rq /tmp/v1/etd_proto_repo /tmp/v5/etd_proto_repo
```

```bash
# прототип (1): quick start
cd /tmp/v1/etd_proto_repo && pip install -r requirements.txt && python validate_examples.py && python sim/report_runner.py
```

```bash
# ветка: тесты и CI-шаги
git fetch origin claude/add-hyundai-robot-docs-kvCBq && git worktree add /tmp/etd-branch origin/claude/add-hyundai-robot-docs-kvCBq
cd /tmp/etd-branch && python -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m pytest -q
```

```bash
# ветка: подписи и sandbox
for p in examples/*/; do .venv/bin/python etd_cli.py verify "$p"; done
.venv/bin/python etd_cli.py sandbox-check examples/etd.pickplace.basic
```
