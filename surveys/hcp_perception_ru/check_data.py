"""Проверка выгрузки данных (SPSS .sav) HCP Perception на соответствие логике анкеты (build.py).

Запуск:  python3 surveys/hcp_perception_ru/check_data.py <выгрузка.sav>
Нужен pyreadstat (pip install pyreadstat). Данные респондентов в репозиторий не кладём.

Печатает по каждому интервью нарушения логики (ERR) и мягкие замечания (WARN: срабатывали мягкие
предупреждения, короткие ответы, подозрительные значения). Множественные ответы в выгрузке — слоты
`Q3_1_1..3` с кодами, таблицы — `Q8_1xr<строка>`, циклы — `Q11_<кат>_<код>.<код>_...`, `Q23_<код>.<код>xr..`.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from ss_check import empty, is_flat, load_links, num, run, txt  # noqa: E402

LINKS = os.path.join(HERE, 'links', 'hcp_perception_ru_links_5000.xlsx')

CATS = (1, 2, 3)
BRANDS = {1: list(range(1, 19)), 2: list(range(19, 26)), 3: list(range(26, 34))}
JUVEDERM = 2
ALLERGAN = 1
COMPANIES = list(range(1, 21)) + [96]
CHANNELS = list(range(1, 13)) + [96]
MIN_DUR = 15  # мин (IVDurAll — сумма сессий, в минутах); быстрее — подозрение на «пролистывание», LOI ~40


def check(resp, links):
    R = resp
    rid, ext = num(R.v('Rid')), txt(R.v('RespExtID'))
    if links.get(ext) != rid:
        R.err(f'Rid {rid} не соответствует extid {ext} по базе (там {links.get(ext)})')

    # --- скринер (все интервью полные, значит прошли отбор) ---
    for name, ok in (('S0', {1}), ('S1_1', {1}), ('S1_2', {1}), ('S1', {1, 2}), ('S2', {3, 4, 5}),
                     ('S4', {1, 2, 3, 4}), ('S5', set(range(1, 17))), ('S8', {2, 3}), ('S9', {1})):
        R.check_single(name, allowed=ok)
    R.check_single('S6', allowed={1, 2, 3, 96}, other_txt='S6_96T')
    R.check_single('S7', allowed={1, 2, 3, 4, 96}, other_txt='S7_96T')
    R.check_single('S10', allowed={1, 2})
    R.check_single('PD', allowed={1, 2})
    s3 = R.check_rows('S3', [1, 2, 3], lo=0, hi=9999)
    if sum(s3.values()) < 15:
        R.err(f'S3: сумма {sum(s3.values())} < 15 — должен быть скринаут')
    active = [c for c in CATS if s3.get(c, 0) > 0]
    s31 = R.check_rows('S3_1', active, lo=1, hi=9999)
    for c in active:
        if c in s31 and s31[c] > s3[c]:
            R.warn(f'S3_1: пациентов ({s31[c]:g}) больше процедур ({s3[c]:g}) в кат.{c} — было мягкое предупреждение')
    for name in ('S10', 'PD'):
        if num(R.v(name)) == 2:
            R.warn(f'{name} = «Нет / Не согласен» — продолжил (по договорённости это пометка)')

    # --- раздел 1 ---
    R.check_rows('Q1', range(1, 7), allowed={1, 2, 3, 4, 5, 99})
    for qn, rows in (('Q2', range(1, 5)), ('Q5', range(1, 4))):
        t = R.check_rows(qn, rows, lo=0, hi=100)
        if abs(sum(t.values()) - 100) > 1e-9:
            R.err(f'{qn}: сумма {sum(t.values()):g} ≠ 100')
    for c in CATS:
        R.check_multi(f'Q3_{c}', mx=3, none_code=97, asked=c in active)
    R.check_multi('Q4', mx=3)
    R.check_single('Q6', allowed={1, 2, 3, 4, 5, 96}, other_txt='Q6_96T')

    # --- раздел 2 по категориям ---
    for c in CATS:
        a = c in active
        q7 = R.check_multi(f'Q7_{c}', mx=5, none_code=97, asked=a)
        bad = [b for b in q7 if b not in BRANDS[c] + [96, 97]]
        if bad:
            R.err(f'Q7_{c}: коды не из категории {bad}')
        assessed = [b for b in q7 if b != 97]
        if c == 1 and a and JUVEDERM not in assessed:
            assessed.append(JUVEDERM)
        # Q8
        t8 = R.check_rows(f'Q8_{c}', [k for k in range(1, 19)] + ([96] if f'Q8_{c}xr96' in R.r and
                                                                   not empty(R.v(f'Q8_{c}xr96')) else []),
                          asked=a, allowed={1, 2, 3, 4, 5, 99})
        if a:
            R.check_other(f'Q8_{c}', 96 in t8, f'Q8_{c}xr96_T')
            same_answer(R, f'Q8_{c}', t8)
        # Q9
        t9 = R.check_rows(f'Q9_{c}', range(1, 19), asked=a)
        if a:
            ok = set(assessed) | {99}
            wrong = {k: int(v) for k, v in t9.items() if int(v) not in ok}
            if wrong:
                R.err(f'Q9_{c}: бренды вне Q7 (+Ювидерм): {wrong}')
            if not assessed and any(int(v) != 99 for v in t9.values()):
                R.err(f'Q9_{c}: брендов нет, должно быть «Ни один» во всех строках')
            if len(assessed) > 1:
                same_answer(R, f'Q9_{c}', t9, 'один бренд во всех')
        # Q10
        t10 = R.check_rows(f'Q10_{c}', assessed if a else [], asked=a and bool(assessed),
                           allowed={1, 2, 3, 4, 99})
        # Q11 — цикл по брендам с «Увеличится»
        up = [b for b, v in t10.items() if int(v) == 1]
        for b in BRANDS[c] + [96]:
            base = f'Q11_{c}_{b}.{b}'
            R.check_multi(base, mx=3, none_code=97, other_code=14, other_txt=f'{base}_14T', asked=b in up)
        # Q12, Q13
        q12 = R.check_multi(f'Q12_{c}', none_code=97, asked=a)
        again = [b for b in q12 if b in q7 and b < 96]
        if again:
            R.err(f'Q12_{c}: выбраны бренды, уже отмеченные в Q7: {again}')
        R.check_multi(f'Q13_{c}', mx=3, asked=a and bool(q12) and 97 not in q12)

    # --- раздел 3 ---
    t14 = R.check_rows('Q14', active, allowed={1, 3, 99} if len(active) == 1 else {1, 2, 3, 99})
    sw2 = [c for c, v in t14.items() if int(v) == 2]
    t141 = R.check_rows('Q14_1', sw2, asked=bool(sw2), allowed=set(active))
    for c, v in t141.items():
        if int(v) == c:
            R.err(f'Q14_1: строка {c} — выбрана та же категория')
    for c in CATS:
        same = int(t14.get(c, 0)) == 1
        f = R.check_single(f'Q15_{c}_FROM', asked=same, allowed=set(BRANDS[c] + [96]), other_txt=f'Q15_{c}_FROM_96T')
        t = R.check_single(f'Q15_{c}_TO', asked=same, allowed=set(BRANDS[c] + [96]), other_txt=f'Q15_{c}_TO_96T')
        if same and f is not None and f == t and f != 96:
            R.err(f'Q15_{c}: исходный бренд = бренд, на который перешли ({f})')
        R.check_multi(f'Q16_{c}', mx=3, asked=int(t14.get(c, 0)) in (1, 2))
    R.check_multi('Q17', none_code=97)
    for c in CATS:
        t18 = R.check_rows(f'Q18_{c}', [k for k in (1, 2, 3) if not empty(R.v(f'Q18_{c}xr{k}'))] if c in active else [],
                           asked=c in active)
        if c in active and 1 not in t18:
            R.err(f'Q18_{c}: не заполнено первое поле')
    t19 = R.check_rows('Q19', [1, 2, 3])
    for k, val in t19.items():
        if len(txt(val)) < 3:
            R.err(f'Q19: строка {k} короче 3 символов ({val!r})')
    if len(t19) == 3 and len({txt(v).lower() for v in t19.values()}) == 1:
        R.warn(f'Q19: одинаковый ответ по всем категориям ({txt(t19[1])!r})')

    # --- раздел 4 ---
    if empty(R.v('Q20xr1')):
        R.err('Q20: не заполнено первое упоминание')
    q21 = R.check_multi('Q21', none_code=97)
    rows22 = sorted(set([ALLERGAN] + [k for k in q21 if k != 97]))
    t22 = R.check_rows('Q22', rows22, lo=0, hi=99)
    for k, val in t22.items():
        if (k != ALLERGAN or ALLERGAN in q21) and val < 1:
            R.err(f'Q22: компания {k} отмечена в Q21, а взаимодействий {val:g}')
        if k == ALLERGAN and ALLERGAN not in q21 and val > 0:
            R.warn(f'Q22: Allergan {val:g} взаимодействий, хотя в Q21 не отмечен')
        if val > 12:
            R.warn(f'Q22: компания {k} — {val:g} взаимодействий (>12, мягкое предупреждение)')
    loop23 = [k for k, val in t22.items() if val >= 1]
    flat = []
    for k in COMPANIES:
        t23 = R.check_rows(f'Q23_{k}.{k}', range(1, 12), asked=k in loop23, allowed={1, 2, 3, 4, 5, 99})
        if is_flat(t23):
            flat.append(k)
        R.check_multi(f'Q24_{k}.{k}', asked=k in loop23, other_txt=f'Q24_{k}.{k}_96T')
    loop_flat(R, 'Q23', flat, loop23)
    q25 = R.check_multi('Q25', mn=3)
    rank_check(R, 'Q25_RANK', q25, CHANNELS)
    t26 = R.check_rows('Q26', q25, lo=1, hi=99)
    for k, val in t26.items():
        if val > 12:
            R.warn(f'Q26: канал {k} — {val:g} (>12, мягкое предупреждение)')
    q27 = R.check_multi('Q27', mn=3, mx=5)
    rank_check(R, 'Q27_RANK', q27, list(range(1, 15)) + [96])
    R.check_multi('Q28', mx=3)
    loop29 = sorted(set([ALLERGAN] + [k for k in q21 if k != 97]))
    flat = []
    for k in COMPANIES:
        t29 = R.check_rows(f'Q29_{k}.{k}', range(1, 9), asked=k in loop29, allowed={1, 2, 3, 4, 5})
        if is_flat(t29):
            flat.append(k)
    loop_flat(R, 'Q29', flat, loop29)
    R.check_multi('Q30', mx=3, none_code=97)

    # --- раздел 5 ---
    R.check_single('Q31', allowed={1, 2, 3, 4, 5, 99})
    R.check_single('Q32', allowed={1, 2, 3, 4, 5, 6, 96}, other_txt='Q32_96T')
    for c in CATS:
        used = [b for b in R.multi(f'Q7_{c}') if b != 97]
        a = c in active and bool(used)
        pack = R.check_rows(f'Q33_PACK_{c}', used, asked=a)
        nums = {k: txt(v) for k, v in pack.items() if re.fullmatch(r'\d+', txt(v)) and int(txt(v)) > 1}
        if nums:
            R.warn(f'Q33_PACK_{c}: в «формате упаковки» только числа {nums} (цена или количество?)')
        for part in ('LIST', 'NET'):
            t = R.check_rows(f'Q33_{part}_{c}', used, asked=a, lo=0)
            zeros = [k for k, val in t.items() if val == 0]
            if zeros:
                R.warn(f'Q33_{part}_{c}: «не знаю» (0) у брендов {zeros}')
        if a:
            lst, net = R.table(f'Q33_LIST_{c}'), R.table(f'Q33_NET_{c}')
            for b in used:
                if lst.get(b) and net.get(b) and net[b] > lst[b]:
                    R.warn(f'Q33_{c}: бренд {b} — нетто {net[b]:g} > прейскурант {lst[b]:g}')
    t34 = R.check_rows('Q34', active, allowed={1, 2, 3, 99})
    for qn, codes in (('Q35', (1, 3)), ('Q36', (2, 3))):
        cats = [c for c, v in t34.items() if int(v) in codes]
        t = R.check_rows(qn, [c * 10 + k for c in cats for k in (1, 2, 3)], asked=bool(cats), lo=0)
        for c in cats:
            vals = [t.get(c * 10 + k) for k in (1, 2, 3)]
            nz = [x for x in vals if x]
            if any(b <= a for a, b in zip(nz, nz[1:])):
                R.err(f'{qn}: кат.{c} мин/сред/макс не по возрастанию {vals}')
    t37 = R.check_rows('Q37', [k for k in list(range(1, 7)) + [96] if not empty(R.v(f'Q37xr{k}'))], lo=0, hi=100)
    if abs(sum(v for v in t37.values() if not isinstance(v, str)) - 100) > 1e-9:
        R.err(f'Q37: сумма ≠ 100 ({t37})')
    R.check_other('Q37', t37.get(96, 0) > 0, 'Q37xr96T')
    R.check_rows('Q38', [k for k, v in t37.items() if v > 0], allowed={1, 2, 3})
    R.check_multi('Q39', mx=3)
    R.check_single('Q40', allowed={1, 2, 3, 4, 5, 99})
    q41 = R.check_multi('Q41', mn=3, mx=3)
    rank_check(R, 'Q41_RANK', q41, list(range(1, 10)) + [96])
    for name in ('Q42', 'Q43'):
        t = txt(R.v(name))
        if not t:
            R.err(f'{name}: нет ответа')
        elif name == 'Q43' and len(t) < 5:
            R.warn(f'{name}: короткий ответ {t!r}')
    if R.has('AE'):
        R.err('AE: есть ответы, а блок скрыт')


def same_answer(R, base, t, what='одинаковый ответ во всех'):
    if is_flat(t):
        R.warn(f'{base}: {what} {len(t)} строках ({next(iter(t.values())):g})')


def loop_flat(R, base, flat, loop):
    """Цикл по компаниям: одна оценка во всех строках — по одной компании бывает, у всех — замечание."""
    if len(loop) >= 2 and len(flat) == len(loop):
        R.warn(f'{base}: по всем {len(loop)} компаниям одна оценка во всех строках')


def rank_check(R, base, chosen, codes):
    ranks = {k: int(R.v(f'{base}_{k}')) for k in codes if not empty(R.v(f'{base}_{k}'))}
    if set(ranks) != set(chosen):
        R.err(f'{base}: ранжированы {sorted(ranks)}, выбраны {sorted(chosen)}')
    if sorted(ranks.values()) != list(range(1, len(ranks) + 1)):
        R.err(f'{base}: ранги не 1..{len(ranks)}: {ranks}')


if __name__ == '__main__':
    run(sys.argv[1], check, load_links(LINKS), MIN_DUR, '~40')
