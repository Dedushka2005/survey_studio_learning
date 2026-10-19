"""Проверка выгрузки данных (SPSS .sav) Aesthetics v2 на соответствие логике анкеты (build.py).

Запуск:  python3 surveys/aesthetics_ru_v2/check_data.py <выгрузка.sav>
Нужен pyreadstat (pip install pyreadstat). Данные респондентов в репозиторий не кладём.

Справочники (бренды, области, сценарии, вопросы раздела 3) — импортом из build.py. Печатает по каждому интервью
нарушения логики (ERR) и замечания по качеству (WARN). Множественные ответы — слоты `Q9_1_1..` с кодами,
таблицы — `Q10_1xr<строка>`, цикл Q11–Q12 — `Q11_<кат>_<бренд>.<бренд>`, `Q12_<кат>_<бренд>.<бренд>_<слот>`.
Раздел 3 в выгрузке — по номерам ТЗ: кат.1 Q13–Q20, кат.2 Q21–Q28, кат.3 Q29–Q36.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
sys.path.insert(0, HERE)
from ss_check import empty, is_flat, load_links, num, run, txt  # noqa: E402
from build import (AREAS, BRANDS, CITIES, JUVEDERM, JUVEDERM_ANY_SCORE, NPS_EXTRA_BRANDS,  # noqa: E402
                   SCENARIOS, SCENARIOS_BIO, SEC3)

LINKS = os.path.join(HERE, 'links', 'aesthetics_ru_v2_links_7000.xlsx')
CATS = (1, 2, 3)
MIN_DUR = 15      # мин (IVDur — в минутах); заявлено 30–40
MIN_PRICE = 500   # руб.; цена сеанса / мл ниже — подозрительно
MAX_ML = 10       # мл на пациента за сеанс; больше — подозрительно


def low(score):
    return score is not None and 0 <= score <= 6


def check(R, links):
    rid, ext, typ = num(R.v('Rid')), txt(R.v('RespExtID')), num(R.v('Type'))
    if links.get(ext) != (rid, typ):
        R.err(f'Rid/Type {rid}/{typ} не соответствуют extid {ext} по базе (там {links.get(ext)})')

    # --- скринер (все интервью полные, значит прошли отбор) ---
    for name, ok in (('S0', {1}), ('S1_1', {1}), ('S1_2', {1}), ('S1', {1, 2}), ('S2', {3, 4, 5}),
                     ('S4', set(range(1, len(CITIES) + 1))), ('S7', {2, 3}), ('S8', {1}), ('S9', {1, 2}),
                     ('PD', {1, 2})):
        R.check_single(name, allowed=ok)
    R.check_single('S5', allowed={1, 2, 3, 96}, other_txt='S5_96T')
    R.check_single('S6', allowed={1, 2, 3, 4, 96}, other_txt='S6_96T')
    s3 = R.check_rows('S3', CATS, lo=0, hi=9999)
    if sum(s3.values()) < 15:
        R.err(f'S3: сумма {sum(s3.values()):g} < 15 — должен быть скринаут')
    active = [c for c in CATS if s3.get(c, 0) > 0]
    for name in ('S9', 'PD'):
        if num(R.v(name)) == 2:
            R.warn(f'{name} = «Нет / Не согласен» — продолжил (по договорённости это пометка)')

    # --- раздел 1 ---
    q1a = R.check_rows('Q1a', range(1, 7), lo=0, hi=99999)
    for c in active:
        if q1a.get(c) == 0:
            R.err(f'Q1a: кат.{c} — 0 пациентов при S3 > 0')
    if is_flat(q1a):
        R.warn(f'Q1a: одно число во всех строках ({next(iter(q1a.values())):g})')
    R.check_rows('Q1b', [k for k, v in q1a.items() if v > 0], lo=0, hi=100)
    R.check_rows('Q2', range(1, 7), allowed={1, 2, 3, 4, 5, 97})
    for qn in ('Q3a', 'Q3b'):
        for k, v in R.check_rows(qn, active, lo=0, hi=9999).items():
            if v > MAX_ML:
                R.warn(f'{qn}: кат.{k} — {v:g} мл на пациента (> {MAX_ML})')
    new = R.check_rows('Q4_new', active, lo=0, hi=100)
    rep = R.check_rows('Q4_rep', active)
    for c in active:
        if c in new and c in rep and rep[c] != 100 - new[c]:
            R.err(f'Q4_rep: кат.{c} {rep[c]:g} ≠ 100 − {new[c]:g}')
    R.check_rows('Q5', [c for c, v in rep.items() if v > 0], lo=1, hi=12)
    q6 = R.check_rows('Q6_dir', [c * 10 + y for c in active for y in (1, 2, 3)], allowed={1, 2, 3})
    R.check_rows('Q6_pct', [k for k, v in q6.items() if v in (1, 2)], lo=0, hi=100)
    R.check_rows('Q7', [1, 2, 3, 4] + ([96] if not empty(R.v('Q7xr96')) else []), lo=0, hi=100)
    R.check_other_row('Q7')

    # --- раздел 2: Q8–Q12 по категориям ---
    for c in CATS:
        a = c in active
        if a and empty(R.v(f'Q8_{c}xr1')):
            R.err(f'Q8_{c}: не заполнено первое упоминание')
        if not a and R.table(f'Q8_{c}'):
            R.err(f'Q8_{c}: ответ есть, а категория не активна')
        q9 = R.check_multi(f'Q9_{c}', none_code=97, other_txt=f'Q9_{c}_96T', asked=a)
        bad = [b for b in q9 if b not in list(BRANDS[c]) + [96, 97]]
        if bad:
            R.err(f'Q9_{c}: коды не из категории {bad}')
        brands = [b for b in q9 if b != 97]
        t10 = R.check_rows(f'Q10_{c}', brands, asked=a and bool(brands), allowed=set(range(11)) | {99})
        if is_flat(t10):
            R.warn(f'Q10_{c}: одна оценка у всех {len(t10)} брендов ({next(iter(t10.values())):g})')
        # цикл Q11–Q12: Ювидерм (кат.1, оценка 0–6) + до NPS_EXTRA_BRANDS случайных брендов с оценкой 0–6
        scores = {b: int(v) for b, v in t10.items()}
        juv = c == 1 and JUVEDERM in scores and (JUVEDERM_ANY_SCORE or low(scores[JUVEDERM]))
        others = [b for b, s in scores.items() if low(s) and not (c == 1 and b == JUVEDERM)]
        looped = [b for b in list(BRANDS[c]) + [96]
                  if R.has(f'Q11_{c}_{b}.{b}') or R.multi(f'Q12_{c}_{b}.{b}')]
        extra = [b for b in looped if not (c == 1 and b == JUVEDERM)]
        if juv != (c == 1 and JUVEDERM in looped):
            R.err(f'Q11_{c}: Ювидерм (оценка {scores.get(JUVEDERM)}) {"" if juv else "не "}должен быть в цикле')
        if [b for b in extra if b not in others]:
            R.err(f'Q11_{c}: в цикле бренды без оценки 0–6: {[b for b in extra if b not in others]}')
        if len(extra) != min(NPS_EXTRA_BRANDS, len(others)):
            R.err(f'Q11_{c}: в цикле {len(extra)} брендов с оценкой 0–6, должно {min(NPS_EXTRA_BRANDS, len(others))} '
                  f'(из {others})')
        for b in looped:
            base = f'{c}_{b}.{b}'
            t = txt(R.v(f'Q11_{base}'))
            if not t and low(scores.get(b)):
                R.err(f'Q11_{base}: нет ответа')
            elif t and len(t) < 3:
                R.warn(f'Q11_{base}: короткий ответ {t!r}')
            R.check_multi(f'Q12_{base}', mx=3, other_txt=f'Q12_{base}_96T')

    # --- раздел 3 по категориям ---
    for c in CATS:
        a, qn = c in active, SEC3[c]['qn']
        brands = [b for b in R.multi(f'Q9_{c}') if b != 97]
        share = R.check_rows(f'Q{qn}', brands, asked=a and bool(brands), lo=0, hi=100)
        if share and abs(sum(share.values()) - 100) > 1e-9:
            R.err(f'Q{qn}: сумма {sum(share.values()):g} ≠ 100')
        used = [b for b, v in share.items() if v > 0]
        for b, v in R.check_rows(f'Q{qn + 1}', used, asked=bool(used), lo=0.1, hi=20).items():
            if v > MAX_ML:
                R.warn(f'Q{qn + 1}: бренд {b} — {v:g} мл за сеанс (> {MAX_ML})')
        areas = R.check_rows(f'Q{qn + 2}', list(AREAS[c]) + ([96] if not empty(R.v(f'Q{qn + 2}xr96')) else []),
                             asked=a, lo=0, hi=100)
        if a:
            if abs(sum(areas.values()) - 100) > 1e-9:
                R.err(f'Q{qn + 2}: сумма {sum(areas.values()):g} ≠ 100')
            R.check_other_row(f'Q{qn + 2}')
        t = R.check_rows(f'Q{qn + 3}', [k for k, v in areas.items() if v > 0], asked=a and bool(used))
        wrong = {k: int(v) for k, v in t.items() if int(v) not in used}
        if wrong:
            R.err(f'Q{qn + 3}: бренды вне используемых в Q{qn} ({used}): {wrong}')
        scen = SCENARIOS_BIO if c == 3 else SCENARIOS
        t = R.check_rows(f'Q{qn + 4}', scen, asked=a)
        wrong = {k: int(v) for k, v in t.items() if int(v) not in brands + [99]}
        if wrong:
            R.err(f'Q{qn + 4}: бренды вне Q9_{c}: {wrong}')
        if a and not brands and any(int(v) != 99 for v in t.values()):
            R.err(f'Q{qn + 4}: брендов в Q9 нет — должно быть «Ни один / Не знаю» во всех строках')
        if len(brands) > 1 and is_flat(t):
            R.warn(f'Q{qn + 4}: один бренд во всех сценариях ({next(iter(t.values())):g})')
        p = R.check_single(f'Q{qn + 5}', asked=a, allowed={1, 2, 3, 96, 97}, other_txt=f'Q{qn + 5}_96T')
        for k, codes, what in ((6, (1, 3), 'сеанс'), (7, (2, 3), 'мл')):
            v = R.check_single(f'Q{qn + k}', asked=p in codes)
            if v is not None and v < MIN_PRICE:
                R.warn(f'Q{qn + k}: цена за {what} {v} руб. (< {MIN_PRICE})')

    if R.has('AE'):
        R.err('AE: есть ответы, а блок скрыт')


if __name__ == '__main__':
    run(sys.argv[1], check, load_links(LINKS, 'type'), MIN_DUR, '30–40')
