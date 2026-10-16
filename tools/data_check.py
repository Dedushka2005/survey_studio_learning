"""Проверка выгрузки массива SURVEYSTUDIO (Excel или SPSS) по логике анкеты.

Общая часть: чтение выгрузки, доступ к ответам в формате выгрузки, типовые проверки, отчёт.
Правила конкретной анкеты — в surveys/<проект>/check_data.py (пример: hcp_perception_ru).

Формат выгрузки (шпаргалка, раздел 9):
  одиночный выбор / число / текст   S4, Rid, Q42;  «Другое» к одиночному — S6_96T
  множественный выбор               слоты с кодами Q7_1_1 … Q7_1_5;  текст «Другого» — Q7_1_96T
  таблица                           Q8_1.<строка>;  текст строки «Другое» — Q8_1.96_T или Q37.96T
  ранжирование                      Q25_RANK_<код> = место
  цикл                              Q23_<код>.<код>.<строка>, Q24_<код>.<код>_<слот>
Пустая ячейка = вопрос/строка не показаны (или не отвечены).

Уровни замечаний:
  ОШИБКА  — данные противоречат логике анкеты (показан лишний вопрос, нет обязательного ответа, …)
  ВНИМАНИЕ — логика соблюдена, но ответ подозрительный (качество данных)
  ИНФО    — справочно (например, на каком вопросе брошено интервью)
"""
import math
import re
import sys
from collections import OrderedDict

ERROR, WARN, INFO = 'ОШИБКА', 'ВНИМАНИЕ', 'ИНФО'

# служебные колонки выгрузки (не ответы)
SERVICE_COLS = re.compile(r'^(ID|RespExtID|UserID|UserName|UserLgIn|IVDate\d|IVDur|Phone|IPAddress|UserAgent|'
                          r'StartupQuery|IVProcessingStatus|DB_.*)$')


def load_export(path):
    """Строки выгрузки: список словарей {колонка: строка или None}. Excel (.xlsx) или SPSS (.sav)."""
    import pandas as pd
    if path.lower().endswith('.sav'):
        import pyreadstat
        df, _ = pyreadstat.read_sav(path)
    else:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            df = pd.read_excel(path, dtype=str)
    rows = []
    for rec in df.to_dict('records'):
        rows.append({c: _clean(v) for c, v in rec.items()})
    return list(df.columns), rows


def _clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s if s != '' else None


def _num(s):
    if s is None:
        return None
    try:
        return float(s.replace(',', '.'))
    except ValueError:
        return None


class Columns:
    """Индекс колонок выгрузки (общий для всех респондентов, с кэшем по шаблонам)."""

    def __init__(self, names):
        self.names = list(names)
        self._cache = {}

    def match(self, pattern):
        """[(колонка, int(группа 1))] для колонок, полностью совпадающих с шаблоном."""
        if pattern not in self._cache:
            rx = re.compile(pattern)
            found = []
            for c in self.names:
                m = rx.fullmatch(c)
                if m:
                    found.append((c, int(m.group(1))))
            self._cache[pattern] = found
        return self._cache[pattern]


class Resp:
    """Один респондент. Все обращения к колонкам запоминаются (touched), чтобы найти
    данные, которые не проверило ни одно правило."""

    def __init__(self, cols, row):
        self.cols, self.row = cols, row
        self.touched = set()

    # --- значения ---
    def v(self, col):
        self.touched.add(col)
        return self.row.get(col)

    def num(self, col):
        return _num(self.v(col))

    def code(self, col):
        x = self.num(col)
        return int(x) if x is not None else None

    def has(self, col):
        return self.v(col) is not None

    # --- структуры ---
    def multi(self, prefix):
        """Множественный выбор: множество отмеченных кодов (по слотам prefix_1, prefix_2, …)."""
        codes = []
        for c, _ in self.cols.match(re.escape(prefix) + r'_(\d+)'):
            x = self.code(c)
            if x is not None:
                codes.append(x)
        return codes

    def table(self, prefix):
        """Таблица: {код строки: значение-строка} для непустых строк prefix.<код>."""
        out = OrderedDict()
        for c, code in self.cols.match(re.escape(prefix) + r'\.(\d+)'):
            val = self.v(c)
            if val is not None:
                out[code] = val
        return out

    def table_num(self, prefix):
        return OrderedDict((k, _num(v)) for k, v in self.table(prefix).items())

    def rank(self, prefix):
        """Ранжирование: {код: место}."""
        out = {}
        for c, code in self.cols.match(re.escape(prefix) + r'_RANK_(\d+)'):
            x = self.code(c)
            if x is not None:
                out[code] = x
        return out

    def loop_codes(self, base):
        """Цикл: коды итераций, по которым есть хоть один ответ (колонки base_<код>.<код>…)."""
        codes = set()
        for c, code in self.cols.match(re.escape(base) + r'_(\d+)\.\d+(?:[._].*)?'):
            if self.v(c) is not None:
                codes.add(code)
        return codes

    def all_empty(self, pattern):
        """Колонки по шаблону (regex) — все пустые? Возвращает список непустых."""
        bad = []
        rx = re.compile(pattern)
        for c in self.cols.names:
            if rx.fullmatch(c):
                if self.v(c) is not None:
                    bad.append(c)
        return bad

    def untouched_answers(self):
        return [c for c in self.cols.names
                if c not in self.touched and not SERVICE_COLS.match(c) and self.row.get(c) is not None]


class Report:
    def __init__(self):
        self.items = []  # (id респондента, уровень, вопрос, текст)

    def add(self, rid, level, q, msg):
        self.items.append((rid, level, q, msg))

    def err(self, rid, q, msg):
        self.add(rid, ERROR, q, msg)

    def warn(self, rid, q, msg):
        self.add(rid, WARN, q, msg)

    def count(self, level):
        return sum(1 for i in self.items if i[1] == level)

    def print(self, total, statuses, out=sys.stdout):
        print(f'Интервью в выгрузке: {total}', file=out)
        for st, n in statuses.items():
            print(f'  {st}: {n}', file=out)
        print(f'Ошибок логики: {self.count(ERROR)}, замечаний по качеству: {self.count(WARN)}', file=out)
        cur = object()
        for rid, level, q, msg in self.items:
            if rid != cur:
                print(f'\n— Респондент {rid}', file=out)
                cur = rid
            print(f'  [{level}] {q}: {msg}', file=out)
        if not self.items:
            print('\nЗамечаний нет.', file=out)

    def to_xlsx(self, path):
        import pandas as pd
        pd.DataFrame(self.items, columns=['Респондент', 'Уровень', 'Вопрос', 'Замечание']).to_excel(path, index=False)


class Checker:
    """Типовые проверки для одного респондента. q — имя вопроса в отчёте."""

    def __init__(self, r, rep, rid):
        self.r, self.rep, self.rid = r, rep, rid

    def err(self, q, msg):
        self.rep.err(self.rid, q, msg)

    def warn(self, q, msg):
        self.rep.warn(self.rid, q, msg)

    # --- показ ---
    def shown_if(self, q, cond, present):
        """Вопрос должен быть показан (есть ответ) ровно тогда, когда cond. Возвращает cond and present."""
        if cond and not present:
            self.err(q, 'нет ответа, хотя вопрос должен был быть задан')
        elif present and not cond:
            self.err(q, 'есть ответ, хотя вопрос не должен был задаваться')
        return cond and present

    def same_set(self, q, what, actual, expected):
        actual, expected = set(actual), set(expected)
        if actual != expected:
            parts = []
            if expected - actual:
                parts.append('нет ' + _codes(expected - actual))
            if actual - expected:
                parts.append('лишние ' + _codes(actual - expected))
            self.err(q, f'{what}: ' + '; '.join(parts) + f' (ожидалось {_codes(expected) or "ничего"})')

    # --- вопросы ---
    def single(self, q, col, cond=True, allowed=None, other=None):
        """Одиночный выбор / число. other — код «Другое» с текстом col_<код>T. Возвращает код или None."""
        val = self.r.code(col)
        if not self.shown_if(q, cond, val is not None):
            if other is not None:
                self._no_text(q, f'{col}_{other}T', val == other)
            return None
        if allowed is not None and val not in allowed:
            self.err(q, f'недопустимый код {val}')
        if other is not None:
            self._other_text(q, f'{col}_{other}T', val == other)
        return val

    def multi(self, q, prefix, cond=True, min_n=1, max_n=None, exclusive=(97,), other=96, allowed=None):
        """Множественный выбор. Возвращает множество кодов (пустое, если не задан)."""
        codes = self.r.multi(prefix)
        other_col = f'{prefix}_{other}T' if other is not None else None
        if not self.shown_if(q, cond, bool(codes)):
            if other_col:
                self._no_text(q, other_col, False)
            return set()
        if len(codes) != len(set(codes)):
            self.err(q, 'один код отмечен дважды')
        s = set(codes)
        if len(s) < min_n:
            self.err(q, f'выбрано {len(s)}, нужно не меньше {min_n}')
        if max_n is not None and len(s) > max_n:
            self.err(q, f'выбрано {len(s)}, допускается не больше {max_n}')
        for x in exclusive or ():
            if x in s and len(s) > 1:
                self.err(q, f'код {x} (исключающий) отмечен вместе с другими')
        if allowed is not None and s - set(allowed):
            self.err(q, 'недопустимые коды ' + _codes(s - set(allowed)))
        if other_col:
            self._other_text(q, other_col, other in s)
        return s

    def rows(self, q, prefix, expected_rows, allowed=None, num_range=None):
        """Таблица: заполнены ровно строки expected_rows. Возвращает {строка: значение}."""
        vals = self.r.table(prefix)
        self.same_set(q, 'строки', vals.keys(), expected_rows)
        out = OrderedDict()
        for k, raw in vals.items():
            x = _num(raw)
            if allowed is not None and (x is None or int(x) not in allowed):
                self.err(q, f'строка {k}: недопустимое значение {raw}')
            if num_range is not None:
                lo, hi = num_range
                if x is None or x < lo or x > hi:
                    self.err(q, f'строка {k}: значение {raw} вне диапазона {lo}–{hi}')
            out[k] = x if x is not None else raw
        return out

    def ranking(self, q, prefix, items):
        """Ранжирование: проранжированы ровно items, места 1..n без повторов."""
        rk = self.r.rank(prefix)
        if not self.shown_if(q, bool(items), bool(rk)):
            return
        self.same_set(q, 'проранжированы', rk.keys(), items)
        if sorted(rk.values()) != list(range(1, len(rk) + 1)):
            self.err(q, f'места {sorted(rk.values())} — должны быть 1…{len(rk)} без повторов')

    def sum_eq(self, q, vals, total=100):
        s = sum(v for v in vals.values() if isinstance(v, (int, float)))
        if vals and abs(s - total) > 1e-6:
            self.err(q, f'сумма {s:g}, должна быть {total}')

    def straightline(self, q, vals, min_rows=6):
        """ВНИМАНИЕ: во всей таблице один и тот же ответ."""
        v = [x for x in vals.values() if x is not None]
        if len(v) >= min_rows and len(set(v)) == 1:
            self.warn(q, f'во всех {len(v)} строках один ответ ({_fmt(v[0])})')

    # --- «Другое» ---
    def _other_text(self, q, col, needed):
        has = self.r.has(col)
        if needed and not has:
            self.err(q, 'отмечено «Другое», но текст не вписан')
        elif has and not needed:
            self.err(q, f'текст «Другого» ({self.r.v(col)!r}) без отметки')

    def _no_text(self, q, col, _):
        if self.r.has(col):
            self.err(q, f'текст «Другого» ({self.r.v(col)!r}) у незаданного вопроса')


def _fmt(x):
    return f'{x:g}' if isinstance(x, float) else str(x)


def _codes(s):
    return ', '.join(str(x) for x in sorted(s))


def run(path, check_one, rid_col='Rid', out_xlsx=None):
    """Прогнать правила анкеты check_one(Checker) -> статус по всем интервью выгрузки."""
    names, rows = load_export(path)
    cols = Columns(names)
    rep = Report()
    statuses = OrderedDict()
    seen = {}
    for row in rows:
        r = Resp(cols, row)
        rid = row.get(rid_col) or row.get('ID')
        if rid in seen:
            rep.err(rid, rid_col, f'повтор: этот номер уже встречался (ID {seen[rid]})')
        seen[rid] = row.get('ID')
        status = check_one(Checker(r, rep, rid))
        statuses[status] = statuses.get(status, 0) + 1
        stray = r.untouched_answers()
        if stray:
            rep.warn(rid, '—', 'данные, которые не проверило ни одно правило: ' + ', '.join(stray[:15]) +
                     (' …' if len(stray) > 15 else ''))
    rep.items.sort(key=lambda i: (_sort_key(i[0]), [ERROR, WARN, INFO].index(i[1])))
    rep.print(len(rows), statuses)
    if out_xlsx:
        rep.to_xlsx(out_xlsx)
        print(f'\nОтчёт сохранён: {out_xlsx}')
    return rep


def _sort_key(rid):
    try:
        return (0, float(rid), '')
    except (TypeError, ValueError):
        return (1, 0, str(rid))
