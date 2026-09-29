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

// Если в строке «Другое» таблицы указано число > 0, требовать уточнение текста.
// Использование в скрипте после ответа: return requireRowText(Q, 98);
function requireRowText(q, code) {
    let row = q.rows[code];
    if (row === undefined || !row.visible) return ok;
    let v = row.answer.openValueNum;
    if (v !== undefined && v > 0 && !row.openValueTxt) {
        return error('Пожалуйста, уточните вариант «' + row.plainText + '»');
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

// Оставить в выпадающих списках таблицы только указанные коды. ⚠️ не проверено в системе.
// Колонкам таблицы давать код 900: если объект answers содержит его, значит это колонки,
// а не выпадающий список, и фильтровать его нельзя.
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
