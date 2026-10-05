// ============================================================================
// Общая библиотека функций для анкет SURVEYSTUDIO
// Вставляется в раздел «Функции» анкеты генератором (tools/ss_builder.py).
// Тексты __SCREEN_TEXT__ и __REFUSE_TEXT__ подставляются при сборке.
// ============================================================================

// Скринаут с результатом «Скрининг» (не подходит по критериям отбора).
// Использование в скрипте после ответа: if (Q.isChecked(3)) return screenOut();
function screenOut() {
    return exitWithResult(InterviewResult.Screening, __SCREEN_TEXT__);
}

// Отказ от участия с результатом «Завершено».
function refuseOut() {
    return exitWithResult(InterviewResult.Exited, __REFUSE_TEXT__);
}

// Число в строке табличного числового вопроса (0, если строка скрыта или пуста).
function numRow(q, code) {
    let row = q.rows[code];
    if (row === undefined || !row.visible) return 0;
    let v = row.answer.openValueNum;
    return v === undefined ? 0 : v;
}

// Сумма чисел во всех видимых строках табличного числового вопроса.
function sumRows(q) {
    let total = 0;
    for (let code of q.rows.getCodes()) total += numRow(q, code);
    return total;
}

// Показать только строки, для кодов которых predicate(code) вернул true.
// Пример: showRowsWhere(Q, function (code) { return numRow(Q10, code) > 0; });
function showRowsWhere(q, predicate) {
    q.rows.hideAll();
    for (let code of q.rows.getCodes()) {
        if (predicate(code)) q.rows.show(code);
    }
}

// Показать только варианты ответа, для кодов которых predicate(code) вернул true.
function showAnswersWhere(q, predicate) {
    q.answers.hideAll();
    for (let code of q.answers.getCodes()) {
        if (predicate(code)) q.answers.show(code);
    }
}

// Строка «Другое» числовой таблицы: если указано число > 0 — требовать уточнение текста,
// если вписан текст — требовать число. Строку можно сделать необязательной флагом CustomRowValidation.
// Использование в скрипте после ответа: return requireRowText(Q, 98);
function requireRowText(q, code) {
    let row = q.rows[code];
    if (row === undefined || !row.visible) return ok;
    let v = row.answer.openValueNum;
    if (v !== undefined && v > 0 && !row.openValueTxt) {
        return error('Пожалуйста, уточните вариант «' + row.plainText + '»');
    }
    if (row.openValueTxt && v === undefined) {
        return error('Пожалуйста, укажите значение для варианта «' + row.plainText + '»');
    }
    return ok;
}

// Подставить текст «Другое» из строки вопроса src в текст строки вопроса dst.
function copyOtherText(src, dst, code) {
    if (dst.rows[code] === undefined || src.rows[code] === undefined) return;
    let txt = src.rows[code].openValueTxt;
    dst.rows[code].text = txt ? 'Другое: ' + txt : 'Другое';
}

// Текст выбранных ответов через запятую (для «другого» — вписанный текст).
function checkedText(q) {
    let parts = [];
    for (let a of q.getChecked()) {
        parts.push(a.settings.openValueTxt && a.openValueTxt ? a.openValueTxt : a.plainText);
    }
    return parts.join(', ');
}

// ---------------------------------------------------------------------------
// Автоответ, если после фильтра остался один вариант (приём из анкеты пользователя)
// Использовать только там, где единственный вариант — логически вынужденный ответ
// («чаще всего» из одного регулярно назначаемого, ранжирование одной компании и т.п.).
// ---------------------------------------------------------------------------

// Вопрос с выбором: один видимый вариант — отметить и не показывать; ни одного — пропустить.
// Использование в скрипте перед показом:
//   Q.showOnly(Q23.getCheckedCodes());
//   return autoAnswerIfSingle(Q);
function autoAnswerIfSingle(q) {
    let codes = q.answers.getVisibleCodes();
    if (codes.length === 1) {
        q[codes[0]].checked = true;
        return answered;
    }
    return codes.length > 0 ? ok : skip;
}

// Числовая таблица (доли, сумма = total): одна видимая строка — вписать total и не показывать.
// Использование: showRowsWhere(Q, …); return autoFillIfSingle(Q, 100);
function autoFillIfSingle(q, total) {
    let codes = q.rows.getVisibleCodes();
    if (codes.length === 1) {
        q.rows[codes[0]].answer.openValueNum = total;
        return answered;
    }
    return codes.length > 0 ? ok : skip;
}

// Проверка суммы видимых строк числовой таблицы (скрипт после ответа).
// Использование: return requireSum(Q, 100);  или  return requireSum(Q, Q16.openValueInt);
function requireSum(q, target) {
    let total = +sumRows(q).toFixed(2);
    if (total !== target) {
        return error('Сумма значений должна быть равна ' + target + '. Сейчас: ' + total + '.');
    }
    return ok;
}

// Выделить строку таблицы красным и вернуть ошибку (скрипт после ответа).
// Перед проверками вызвать resetRowMarks(Q), чтобы снять старые выделения.
//   resetRowMarks(Q);
//   if (…) return rowError(Q, code, 'Ранее вы сказали, что …');
function rowError(q, code, message) {
    q.rows[code].text = '<font color="red"><b>' + q.rows[code].plainText + '</b></font>';
    return error(message);
}

function resetRowMarks(q) {
    for (let row of q.rows.getVisible()) row.text = row.plainText;
}

// Строка «Другое» таблицы с выбором (необязательная строка с полем для текста):
// вписан текст — нужен ответ в строке; есть ответ — нужен текст.
// Использование в скрипте после ответа: return requireChoiceRowText(Q, 96);
function requireChoiceRowText(q, code) {
    let row = q.rows[code];
    if (row === undefined || !row.visible) return ok;
    let answered = row.getCheckedCodes().length > 0;
    if (row.openValueTxt && !answered) {
        return error('Пожалуйста, дайте ответ в строке «' + row.plainText + '»');
    }
    if (answered && !row.openValueTxt) {
        return error('Пожалуйста, уточните вариант «' + row.plainText + '»');
    }
    return ok;
}

// Нестрогая проверка: при первом «Далее» показать предупреждение, при повторном нажатии
// с теми же ответами — пропустить. Если ответ изменили и условие снова выполняется — предупредить снова.
// Использование в скрипте после ответа:
//   return softWarning(Q, Q.rows.getVisible().some(r => r.answer.openValueNum > 12),
//                      'Вы указали больше 12. Проверьте, пожалуйста, верно ли указано число.');
function softWarning(q, condition, message) {
    if (isPostProcessing() || isValidation()) return ok;
    let key = 'softWarning_' + q.number;
    if (!condition) { V[key] = ''; return ok; }
    let signature = answerSignature(q);
    if (V[key] === signature) return ok;
    V[key] = signature;
    return error(message);
}

// Строка-«слепок» ответа на вопрос (для softWarning): числа/тексты строк, открытые значения, коды.
function answerSignature(q) {
    let parts = [];
    try {
        for (let row of q.rows.getVisible()) {
            parts.push(row.code + ':' + row.answer.openValueNum + ':' + row.answer.openValueTxt + ':' + row.openValueTxt);
        }
    } catch (e) { }
    try { parts.push(String(q.openValueNum) + ':' + String(q.openValueTxt)); } catch (e) { }
    try { parts.push(q.getCheckedCodes().join(',')); } catch (e) { }
    return parts.join('|');
}

// ❌ УСТАРЕЛО: SURVEYSTUDIO не умеет фильтровать варианты в «Таблица: выпадающий список» (ответ поддержки).
// Оставлено только для совместимости со старой анкетой Aesthetics RU. В новых анкетах не использовать.
function filterDropdown(q, codes) {
    if (codes.length === 0) return;
    let isDropdownList = function (list) {
        return list !== undefined && list.getCodes().indexOf(900) === -1 && list.count > 1;
    };
    try {
        if (isDropdownList(q.answers)) { q.answers.showOnly(codes); return; }
    } catch (e) { }
    for (let row of q.rows.getAll()) {
        try {
            if (isDropdownList(row.answers)) row.answers.showOnly(codes);
        } catch (e) { }
    }
}

// Найти в тексте упоминания по словарю синонимов { код: ['вариант1', 'вариант2'] }.
// Регистр, пробелы и знаки препинания не учитываются. Возвращает массив кодов.
function findByAliases(text, aliases, codes) {
    let norm = String(text).toLowerCase().replace(/ё/g, 'е').replace(/[^a-zа-я0-9]/g, '');
    let found = [];
    for (let code of codes) {
        let list = aliases[code] || [];
        for (let a of list) {
            if (norm.indexOf(a) > -1) { found.push(code); break; }
        }
    }
    return found;
}
