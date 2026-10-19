"""Общие проверки выгрузки данных поля (SPSS .sav) на соответствие логике анкеты — для surveys/*/check_data.py.

Resp — одно интервью: доступ к переменным выгрузки (одиночные, слоты множественного ответа `base_<n>`,
таблицы `base_xr<строка>`) и типовые проверки, копящие ERR (логика) и WARN (качество).
"""
import re


def empty(v):
    return v is None or v == '' or (isinstance(v, float) and v != v)


def num(v):
    return None if empty(v) else float(v)


def txt(v):
    return '' if empty(v) else str(v).strip()


class Resp:
    def __init__(self, row, cols):
        self.r = row
        self.cols = cols
        self.errs = []
        self.warns = []

    def v(self, name):
        return self.r.get(name)

    def has(self, prefix):
        """Есть ли хоть один ответ в переменных с этим префиксом."""
        return any(not empty(self.r[c]) for c in self.cols if c.startswith(prefix))

    def multi(self, base):
        """Коды множественного ответа (слоты base_1, base_2 …)."""
        pat = re.compile(re.escape(base) + r'_\d+$')
        return [int(self.r[c]) for c in self.cols if pat.match(c) and not empty(self.r[c])]

    def table(self, base):
        """{строка: значение} для таблицы base_xr<строка>."""
        pat = re.compile(re.escape(base) + r'xr(\d+)$')
        out = {}
        for c in self.cols:
            m = pat.match(c)
            if m and not empty(self.r[c]):
                out[int(m.group(1))] = self.r[c]
        return out

    def err(self, msg):
        self.errs.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

    # --- типовые проверки ---
    def check_multi(self, base, mn=1, mx=None, none_code=None, other_code=96, other_txt=None, asked=True):
        codes = self.multi(base)
        if not asked:
            if codes:
                self.err(f'{base}: ответ есть, а вопрос не должен показываться')
            return codes
        if not codes:
            self.err(f'{base}: нет ответа')
            return codes
        if len(codes) != len(set(codes)):
            self.err(f'{base}: повтор кодов {codes}')
        if none_code is not None and none_code in codes and len(codes) > 1:
            self.err(f'{base}: исключающий {none_code} вместе с другими {codes}')
        if not (none_code is not None and codes == [none_code]):
            if len(codes) < mn:
                self.err(f'{base}: выбрано {len(codes)} < {mn}')
            if mx is not None and len(codes) > mx:
                self.err(f'{base}: выбрано {len(codes)} > {mx}')
        self.check_other(base, other_code in codes, other_txt or f'{base}_{other_code}T')
        return codes

    def check_other(self, base, chosen, txt_var):
        if txt_var not in self.r:
            return
        t = txt(self.v(txt_var))
        if chosen and not t:
            self.err(f'{base}: выбрано «Другое» без текста')
        if not chosen and t:
            self.err(f'{base}: текст «Другое» без отметки ({t!r})')
        if chosen and t and len(t) < 3:
            self.warn(f'{base}: короткий текст «Другое» {t!r}')

    def check_other_row(self, base, code=96):
        """Числовая строка «Другое» в таблице (requireRowText): число > 0 — нужен текст, текст — нужно число."""
        val, t = num(self.v(f'{base}xr{code}')), txt(self.v(f'{base}xr{code}T'))
        if val and not t:
            self.err(f'{base}: строка «Другое» = {val:g} без текста')
        if t and val is None:
            self.err(f'{base}: текст «Другое» без числа ({t!r})')
        if t and val == 0:
            self.warn(f'{base}: строка «Другое» = 0 с текстом {t!r}')

    def check_single(self, name, asked=True, allowed=None, other_txt=None):
        val = num(self.v(name))
        if not asked:
            if val is not None:
                self.err(f'{name}: ответ есть, а вопрос не должен показываться')
            return None
        if val is None:
            self.err(f'{name}: нет ответа')
            return None
        if allowed is not None and int(val) not in allowed:
            self.err(f'{name}: недопустимый код {int(val)}')
        if other_txt:
            self.check_other(name, int(val) == 96, other_txt)
        return int(val)

    def check_rows(self, base, rows, asked=True, lo=None, hi=None, allowed=None):
        """Таблица: ответы ровно в строках rows."""
        t = self.table(base)
        if not asked:
            if t:
                self.err(f'{base}: ответ есть, а вопрос не должен показываться')
            return t
        got, need = set(t), set(rows)
        if got - need:
            self.err(f'{base}: лишние строки {sorted(got - need)} (должны быть {sorted(need)})')
        if need - got:
            self.err(f'{base}: не заполнены строки {sorted(need - got)}')
        for k, val in t.items():
            if isinstance(val, str):
                continue
            if lo is not None and val < lo or hi is not None and val > hi:
                self.err(f'{base}: строка {k} = {val} вне [{lo}; {hi}]')
            if allowed is not None and int(val) not in allowed:
                self.err(f'{base}: строка {k} — недопустимый код {int(val)}')
        return t


def is_flat(t):
    """Прямолинейные ответы: одно значение во всех строках таблицы (≥ 4 строк)."""
    vals = [v for v in t.values() if not isinstance(v, str)]
    return len(vals) >= 4 and len(set(vals)) == 1
