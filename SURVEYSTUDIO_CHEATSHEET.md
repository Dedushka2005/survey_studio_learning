# SURVEYSTUDIO — шпаргалка по программированию анкет

Конспект базы знаний https://kb.surveystudio.ru/ (скачать заново: `python3 tools/fetch_kb.py`, страницы
сохраняются в `kb/`, эта папка не коммитится).

## 1. Три уровня логики

| Уровень | Где задаётся | Для чего |
|---|---|---|
| Условие показа | свойство вопроса `Condition` | показать/не показать вопрос |
| Действия | «Перед показом» / «После ответа» | переходы, скрытие ответов, переменные, ошибки, завершение |
| Скрипты (JavaScript) | глобальные и у вопроса | всё, что не решается первыми двумя |

Действия выполняются по порядку, пока одно не вернёт окончательный результат (переход, завершение, ошибка).

## 2. Синтаксис выражений (условия показа, действий, счётчиков, квот)

- Операторы: `=  !=  >  <  >=  <=`, `and or not`, скобки.
- Ключевые слова: `code`, `row`, `valueTxt`, `valueNum`, `valueInt`, `null`.
- `Q` без номера — текущий вопрос (рекомендуется в «после ответа»).
- Всегда истинно: `1 = 1`, `any`, `all`. Никогда: `false`, `1 = 2`.

```
Q1 = 2                          выбран код 2
Q1(code = 1 or code = 3)        выбран 1 или 3 (предпочтительнее, чем Q1=1 or Q1=3)
Q1(code >= 1 and code <= 5)     код в диапазоне
Q1(code = 98 and valueTxt != null)   выбран 98 и заполнено «другое»
Q1(valueNum >= 18 and valueNum <= 35) числовой вопрос в диапазоне
Q1(row = 1 and code = 4)        таблица: в строке 1 выбран код 4
not Q1 != 99                    таблица: во всех строках выбран 99
Q1 and not Q1 = 3               вопрос отвечен и код 3 НЕ выбран
Q = 3 and not Q != 3            выбран ТОЛЬКО код 3
```

**Ловушка `!=`:** `Q1 != 3` означает «есть ли ответ с кодом ≠ 3». Для множественного выбора
это почти всегда не то. Правильно — `Q1 and not Q1 = 3`.

Сравнение `valueTxt` только по точному совпадению (регистр и пробелы важны).

## 3. Подстановки в тексты

- `{Q1}` — текст выбранного ответа (для «другое» — вписанный текст; несколько — через запятую).
- `{Q5.1N}` / `{Q5.98T}` — число/текст из открытого поля ответа (или строки таблицы).
- `{Q5.1}` — значение строки 1 табличного текстового/числового вопроса.
- `{Q5.1.2N}` — число поля ответа 2 в строке 1 таблицы с выбором.
- `{ИмяПеременной}` — значение из `variables` (действие «Установить значение переменной» или `V.x = ...`).
- В циклах: `{answerText}`, `{answerCode}`.

## 4. Основные действия (ActionType в файле анкеты)

Переходы: `JumpToQuestion`(N1=номер), `JumpToEnd`(T1=текст, N1=результат), `Skip`, `SkipIfNoVisible`,
`SkipIfVisibleNoMoreThan`(N1), `Answered`, `AnsweredOrSkip`, `ReturnError`(T1=текст), `ResetAnswers`,
`CopyAnswersFromQuestion`(N1), `ChooseFirstVisibleAnswer`(N1), `FillAnswerFromParameter`, `LoadAnswersFromContactData`.

Ответы: `HideAll`, `HideCodes`(T1="2,5,6"), `HideOnlyCodes`, `HideCheckedInQuestion`(N1),
`HideOnlyCheckedInQuestion`, `HideFromTo`(N1,N2), `ShowAll`, `ShowCodes`, `ShowOnlyCodes`,
`ShowCheckedInQuestion`(N1), `ShowOnlyCheckedInQuestion`(N1), `ShowFromTo`(N1,N2) …
Для строк — префикс `Rows…`, для колонок — `Columns…`.

Переменные: `SetVariableValue`(T1=имя, T2=значение), `SetVariableValueFromOpenValue`(T1=имя, N2=вопрос, T2=код),
`SetVariableValueFromContactData`(T1=имя, T2=поле).

## 5. Скрипты

Типы: **Подготовка** (один раз при старте и при выгрузке; только структура: создание/порядок вопросов,
циклы, флаги; не логика!), **Обработка** (после завершения, перед записью), **Перед показом**,
**После ответа** (глобальные — выполняются до скриптов вопроса), **Функции** (общие функции),
**Во время показа** (в браузере, без API), **CSS**.

Пишется только тело функции; параметр `Q` — текущий вопрос.

Возвращаемые значения:
```js
return ok;            // ничего особенного
return skip;          // (перед показом) сбросить и пропустить
return answered;      // (перед показом) ответ проставлен скриптом, не показывать
return error('Текст');// (после ответа) показать вопрос снова с ошибкой
return question(123); // переход на Q123
return exit('Спасибо');                                  // завершить (Завершено)
return exitWithResult(InterviewResult.Screening, 'Текст'); // скринаут
return exitAndRedirect('Текст', 'https://...');
```
`InterviewResult`: Completed, Screening, Overquoting, Defect, Interrupted, Postponed, Exited, Unknown.

### Доступ к данным
```js
Q1, questions[34]              // вопрос
Q1[5].checked / Q1.answers[5]  // ответ с кодом 5
Q1.isChecked(5)                // выбран ли код 5
Q1.getCheckedCode()            // код (единств. выбор), 0 если нет
Q1.getCheckedCodes()           // массив кодов
Q1.getChecked()                // массив объектов-ответов
Q1.openValueNum / openValueInt / openValueTxt   // числовой/текстовый вопрос
Q1[98].openValueTxt            // «другое»
Q1.isAnswered
Q2.rows[3].getCheckedCode()    // таблица
calc('Q1(code = 1 or code = 3)')  // выражение из п.2 внутри скрипта
V.name = '...'; variables['ФИО']  // глобальные переменные (только простые типы)
parameters.city                // параметр ссылки
contact.data['Поле']           // база контактов
getCounter('Имя') -> {value, quota}
isTesting(), isPostProcessing(), isValidation(), isRedial()
```

### Управление ответами (то же для `rows`, `columns`)
```js
Q.hideAll(); Q.show(1, [3,5]); Q.showOnly(Q1.getCheckedCodes()); Q.hide(99);
Q.showFromTo(1, 10); Q.visibleCount; Q.hasVisible
Q.answers.randomize(); Q.answers.rotate(); Q.answers.randomizeGroups([[1,3],[4,6]]);
Q.answers.setOrder(Q1.answers.getCodes());   // тот же порядок, что в Q1
Q.answers.add(99, 'Не знаю').settings.blocking = true;
Q.reset();
```

### Вопросы (в Подготовке)
```js
questions.randomize([1,3,5]); questions.rotateFromTo(10, 20);
questions.randomizeGroups([[1,2],[3,8],[9,9]]);
questions.repeat(2, 3, 1);        // цикл: Q2–Q3 для каждого выбранного в Q1
questions.repeatIfNot(2, 3, 1);   // для невыбранных
```
Цикл пересоздаёт вопросы с номерами «исходный номер + код ответа» (Q201, Q298 …; разрядность по максимальному коду).
Внутри цикла: `Q.sourceAnswerCode`, `Q.sourceQuestionNumber`, `Q.currentIterationQuestions[2]`.
Обычные условия показа по вопросам цикла не работают — используйте скрипты перед показом.
Ответу, который не должен порождать итерацию (например «Никакими»), ставится флаг «Запрещено использовать в циклах».

## 6. Типовые приёмы

- **Скринаут:** действие после ответа `JumpToEnd` с условием, либо `return exitWithResult(InterviewResult.Screening)`.
- **Показать только выбранные ранее:** действие `ShowOnlyCheckedInQuestion` (N1 = номер) + `SkipIfNoVisible`.
- **Автокодирование возраста** (перед показом вопроса-группы):
  ```js
  let age = Q1.openValueInt;
  Q[1].checked = age <= 17; Q[2].checked = age >= 18 && age <= 24; /* … */
  return answered;
  ```
- **Сумма = 100** в таблице чисел: свойства `AnswersSumControlTarget = 100`, `AnswersSumControlMode = Exactly`.
- **Исключающий ответ** («Затрудняюсь ответить»): флаг ответа `Blocking`.
- **Необязательный вопрос:** флаг `CanSkip` (при «Пропустить» действия/скрипты после ответа не выполняются).
- **Собственная проверка:** флаг `CustomValidation` + скрипт после ответа с `return error(...)`.
- **Служебный вопрос:** условие показа `false`, флаг `SkipExport`.
- **Нельзя переходить к вопросу, который перемешивается с другими** — остальные из группы будут пропущены.

## 7. Формат файла анкеты (импорт/экспорт, JSON, UTF‑8)

```json
{
  "Magic": "SS2EQN", "Version": "2.4", "Name": "Анкета",
  "ExportedQuestionnaireFlags": {}, "ExportedSurveyFlags": {},
  "ScriptPreProcessing": "questions.repeat(2, 3, 1);",
  "Questions": [
    { "OrderIdx": 1, "Number": 1, "Text": "Ваш пол?", "QuestionType": "SingleChoice",
      "ExportedQuestionFlags": {}, "ExportedSurveyFlags": {}, "AnswerList": "Пол",
      "AfterAnswerActions": [
        { "OrderIdx": 1, "Condition": "Q = 3", "ActionType": "JumpToEnd",
          "ActionVarTxt1": "Спасибо!" } ] }
  ],
  "AnswerLists": [
    { "Name": "Пол", "Type": "Common", "AnswerItems": [
      { "OrderIdx": 1, "Code": 1, "Text": "Мужской", "ExportedFlags": {} },
      { "OrderIdx": 2, "Code": 2, "Text": "Женский", "ExportedFlags": {} } ] }
  ]
}
```
Обязательно у вопроса: `OrderIdx, Number, Text, QuestionType, ExportedQuestionFlags, ExportedSurveyFlags`.
Типы: Information, WelcomeScreen, Text, Numeric, Phone, Email, DateTime, SingleChoice, MultipleChoice,
Dropdown_SingleChoice, Dropdown_MultipleChoice, Ranking, Rating, Slider, MaxDiff, SemanticDifferential,
Table_Text, Table_Numeric, Table_SingleChoice, Table_MultipleChoice, Table_Dropdown_SingleChoice, Table_Rating, Table_Slider …
Поля вопроса: `Condition, Comment, AnswerList, RowList, ColumnList, MinAnswerCount, MaxAnswerCount,
AnswerNumberFrom, AnswerNumberTo, ScriptBeforeShow, ScriptAfterAnswer, BeforeShowActions, AfterAnswerActions, OutputColumnTemplate`.
Флаги ответа: `OpenValueNum, OpenValueTxt, Blocking, AlwaysVisible, DisableReordering, DisableRepeat, GroupHeader, SkipExport`.
Флаги вопроса: `RandomizeAnswers, RotateAnswers, CanSkip, CustomValidation, SkipExport, ShowRowsOneByOne`.

Значит, анкету можно собрать целиком в JSON и загрузить в систему одним файлом.

## 8. Наши соглашения (обязательно соблюдать)

- **Завершение интервью — только скриптом после ответа через глобальные функции**, не действием
  «Завершить интервью» (там текст пришлось бы прописывать в каждом вопросе). В «Функциях» анкеты:
  ```js
  function screenOut() {   // не подходит по критериям -> «Скрининг»
      return exitWithResult(InterviewResult.Screening, 'Благодарим вас… не можете принять участие.');
  }
  function refuseOut() {   // отказ от участия -> «Завершено»
      return exitWithResult(InterviewResult.Exited, 'Благодарим вас за уделенное время! До свидания.');
  }
  ```
  В вопросе: `if (Q.isChecked(3) || Q.isChecked(4)) return screenOut();`
- Анкета собирается генератором на Python (`surveys/<проект>/build.py` → JSON для импорта), а не вручную в редакторе.
  Правки вносятся в генератор, затем файл пересобирается. Новая анкета — копия `surveys/_template/`.
- **Общая библиотека** (использовать во всех анкетах, пополнять удачными находками):
  - `tools/ss_builder.py` — сборка: `Questionnaire(имя)`, `q(...)`, `alist(...)`, `screen_if([коды])`,
    `refuse_if([коды])`, наборы флагов `OTHER_TXT`, `BLOCKING`, `FIXED`, `NO_LOOP`, `OPT_ROW`, `OTHER_ROW`.
    `save()` проверяет уникальность номеров/имён/кодов, ссылки на списки и **синтаксис всех скриптов** (Node.js).
  - `tools/ss_lib.js` — JS-функции, автоматически попадают в раздел «Функции» каждой анкеты:
    `screenOut()`, `refuseOut()`, `numRow(q, code)`, `sumRows(q)`, `showRowsWhere(q, fn)`,
    `showAnswersWhere(q, fn)`, `requireRowText(q, code)`, `copyOtherText(src, dst, code)`,
    `checkedText(q)`, `findByAliases(text, aliases, codes)`,
    `autoAnswerIfSingle(q)`, `autoFillIfSingle(q, total)`, `requireSum(q, target)`, `rowError(q, code, msg)`,
    `resetRowMarks(q)`.
    Тексты скринаута/отказа задаются в `Questionnaire(screen_text=…, refuse_text=…)`.
  - Функции конкретной анкеты — в `qnr.global_functions`, они добавляются после общих.
  - `tools/loi_estimate.py` — **оценка длительности анкеты (LOI)** по JSON: чтение текста + действия
    (клик 2,5 с, строка шкалы 4 с, выпадающий список 5 с, число 5–9 с, короткий текст 15 с, развёрнутый 35 с,
    переход экрана 3 с; длинные тексты > 300 слов читают на ~30%). Для вопросов с фильтрами задаётся сценарий
    (сколько строк/ответов видно). Пример сценариев — `surveys/aesthetics_ru/loi.py`. Считать минимум/типичный/максимум.
- Скрипты в генераторе пишем так, чтобы их было легко читать в редакторе SURVEYSTUDIO (`Q.isChecked(...)`,
  а не хитрые конструкции).
- Исходные файлы заказчика (docx с пометкой «конфиденциально») в репозиторий не коммитим.
- **Мультивыбор с «Другое (укажите)» по нескольким объектам — не таблицей**, а циклом простых вопросов
  (в таблице у колонки «Другое» нет поля для текста, уточнение пришлось бы выносить на отдельный экран).
- Числовые границы задаём по смыслу, с запасом (мл, штуки — до 9999), а не «до 100» по умолчанию.
- Строку «Прочее (укажите)» в числовой таблице делаем необязательной (`CustomRowValidation` + `AllowEmptyOpenValue`)
  и проверяем `requireRowText()`: число без текста или текст без числа — ошибка.
- Заголовки разделов с вводным текстом — отдельным информационным экраном, а не шапкой каждого вопроса.
- **Автоответ при единственном варианте:** если после фильтра остался один вариант (или одна строка в таблице
  долей), вопрос не показываем, а ответ ставим скриптом — `return autoAnswerIfSingle(Q);` /
  `return autoFillIfSingle(Q, 100);`. Только там, где ответ логически вынужден («чаще всего» из одного
  назначаемого, ранжирование одной компании, доля одной марки = 100%).
- Проверки согласованности с предыдущими ответами — ошибкой с подсветкой строки:
  `resetRowMarks(Q); if (…) return rowError(Q, code, 'Ранее вы сказали, что …');`
- Внутри цикла код итерации берём из `Q.sourceAnswerCode`, а не вычисляем из `Q.number`.

## 9. Проверено на практике

✅ — подтверждено в системе, ⚠️ — сделано, но ещё не проверено.

- ✅ Анкета, собранная в JSON по формату SS2EQN 2.4, **загружается и запускается** (проект Aesthetics RU).
  При загрузке анкеты с уже существующим именем система добавляет к имени число.
- ✅ Все скрипты перед публикацией полезно проверять на синтаксис через Node.js:
  тело скрипта оборачивается в `new Function('Q', body)`.
- «Таблица: числа» — **одна колонка чисел на строку**. Таблицу с двумя числовыми колонками (например,
  «кол-во» и «%») делаем двумя вопросами.
- Строку таблицы можно сделать необязательной флагом строки `CustomRowValidation`
  («Проверка ответа скриптами, ответ в строке таблицы не требуется»). Так делаем «можно оставить пустым = не знаю».
- Код ответа 0 допустим (шкала NPS 0–10). Но `getCheckedCode()` без аргумента возвращает 0 и когда ничего
  не выбрано — использовать `getCheckedCode(true)` (вернёт `undefined`).
- Цикл по категориям только для подходящих: служебный вопрос-мультивыбор (например Q8000), который
  в скрипте перед показом сам отмечает нужные коды (`Q.reset(); Q[1].checked = …; return answered;`),
  в Подготовке `Q8000.answers.randomize(); questions.repeat(80, 125, 8000);`.
- Чтобы номера вопросов цикла не пересекались с остальными, основные вопросы нумеруем «номер по ТЗ × 10»
  (Q13 → 130), скринер — 5000+, служебные — 8000+. Имя в массиве задаём шаблоном (`S1`, `Q13`, в цикле `Q8_{3}`).
- Цикл внутри цикла избегаем (в вопросах двойного цикла не выполняются их собственные скрипты). Второй
  уровень выносим в отдельный цикл после первого: служебный вопрос-мультивыбор (например Q8500) в скрипте перед
  показом отмечает нужные объекты по ответам из вопросов первого цикла (`questions[1000 + cat]`), затем
  `questions.repeat(110, 120, 8500)`. Номера вопросов цикла = исходный номер + код (разрядность по макс. коду):
  Q100 × коды 1–3 → 1001–1003; Q110 × коды до 37 → 11001–11037.
- ⚠️ Подстановка списка в информационный экран: скрипт перед показом пишет HTML в переменную
  (`V['Категории'] = '<ul>…</ul>'`), в тексте экрана — `{Категории}`.
- ✅ Скринер и разделы 1–2 анкеты Aesthetics прошли тест пользователя (с правками выше).
- ❌ **Фильтровать варианты в «Таблица: выпадающий список» нельзя** (ответ поддержки SURVEYSTUDIO).
  Если список надо сузить — делать циклом простых вопросов с выбором (там `showOnly` работает).
- ✅ Макрос «другого» прямо в тексте варианта/строки списка: строка 98 с текстом `{Q19.98T}` покажет то,
  что вписали в «Другое» в Q19. Проще, чем скрипт `copyOtherText()`.
- ✅ Флаг анкеты `GenerateQuestionVariableByTemplate` — в скриптах можно обращаться к вопросу по имени
  шаблона (`QB7.rows…` вместо `Q26.rows…`). Чтобы имена не пересекались с `Q<номер>`, давать шаблонам префикс
  блока: `QS1`, `QB7`, `QC2`.
- ✅ Проверка суммы скриптом после ответа работает (анкета пользователя Репчек КЗ) — `requireSum()`.
- **Служебный (скрытый) вопрос — две схемы:**
  - ✅ ответы ставит **его собственный** скрипт перед показом → условие показа НЕ задавать (при `false` вопрос
    пропускается целиком и скрипт не запускается — ответов не будет, цикл по нему не создастся). Прячем через
    `return answered;` / `return skip;` (Q8000, Q8500 в Aesthetics; QB8_filter в Репчек КЗ — подтверждено
    пользователем).
  - ✅ ответы ставит скрипт **другого** вопроса → можно условие `false` (Q8003 в Репчек КЗ: перемешан в
    Подготовке, D1 `rows.setOrder(Q8003.answers.getCodes())` и цикл D2 по Q8003 идут в одном порядке).
    ⚠️ Проверить на сохранённом интервью в проекте: постобработка чистит ответы, не соответствующие условиям,
    — ответы вопроса с условием `false` и зависящих от него итераций цикла могут пропасть. Если пропадают —
    использовать первую схему.
- Частые ошибки (найдены при ревью): `exitScreen()` без `return` — интервью не завершится;
  `visibleCount > 1 ? ok : skip` пропускает вопрос с одной строкой — нужен `hasVisible`; табличный вопрос без
  видимых строк надо явно пропускать (`return Q.rows.hasVisible ? ok : skip;`); исключающему ответу без групп
  нужен флаг `Blocking`, а не `BlockingInTheGroup`.
- ⚠️ Контроль суммы (`AnswersSumControlTarget/Mode/Unit`) в таблице чисел — ждёт проверки.
