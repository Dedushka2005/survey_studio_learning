"""Проверка выгрузки массива HCP Perception по логике анкеты (build.py).

Запуск:
  python3 surveys/hcp_perception_ru/check_data.py <выгрузка.xlsx | .sav> [--out отчёт.xlsx] [--min-dur 15]

Выгрузка — из проекта: значения кодами, имена переменных как в анкете, все интервью.
ОШИБКА — данные противоречат логике анкеты; ВНИМАНИЕ — логика соблюдена, но ответ подозрительный.
Справочники (бренды, компании) берутся из build.py — при правке анкеты правила обновляются сами,
логику переходов при изменении build.py поправить и здесь.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
sys.path.insert(0, HERE)
from data_check import run, _num, INFO  # noqa: E402
import build  # noqa: E402  (справочники; JSON при импорте не пересобирается)

CATS = list(build.CATS)
ALLERGAN, JUVEDERM = build.ALLERGAN, build.JUVEDERM
SCALE5 = set(range(1, 6))

# Скринер в порядке анкеты: (переменная, коды отсева, тип)
SCREENER = [('S0', {2}, 'отказ'), ('S1_1', {2}, 'скринаут'), ('S1_2', {2}, 'скринаут'),
            ('S1', {3, 97}, 'скринаут'), ('S2', {1, 2}, 'скринаут'), ('S3', None, 'скринаут'),
            ('S4', {5, 99}, 'скринаут'), ('S5', {96}, 'скринаут'), ('S8', {1}, 'скринаут'), ('S9', {2}, 'отказ')]
MAIN_PART = r'(Q\d.*|AE\d.*)'  # всё, что после скринера

MIN_DUR = 15  # мин; быстрее — подозрение на «пролистывание» (LOI ~40 мин)


def check(ck):
    r = ck.r

    # --- служебное ---
    rid = r.code('Rid')
    if rid is None:
        ck.err('Rid', 'пусто — номер из базы контактов не подтянулся')
    elif r.has('DB_Rid') and r.code('DB_Rid') != rid:
        ck.err('Rid', f'не совпадает с базой контактов (DB_Rid = {r.v("DB_Rid")})')

    # --- скринер: первый отсев ---
    s3 = {c: r.num(f'S3.{c}') for c in CATS}
    fail = None
    for var, codes, kind in SCREENER:
        if var == 'S3':
            if all(v is None for v in s3.values()):
                break
            if sum(v or 0 for v in s3.values()) < 15:
                fail = (var, kind, 'сумма S3 < 15')
                break
            continue
        val = r.code(var)
        if val is None:
            break
        if val in codes:
            fail = (var, kind, f'{var} = {val}')
            break
    complete = r.has('Q43')

    if fail:
        var, kind, why = fail
        if complete:
            ck.err(var, f'интервью полное, хотя должно было закончиться отсевом ({why})')
        else:
            stray = r.all_empty(MAIN_PART)
            if stray:
                ck.err(var, f'после отсева ({why}) есть ответы: ' + ', '.join(stray[:8]))
            _touch_all(r)
            return f'{kind} ({var})'
    if not complete:
        last = [c for c in r.cols.names if r.row.get(c) is not None and re.fullmatch(r'(S|Q|PD|AE).*', c)]
        _touch_all(r)
        ck.rep.add(ck.rid, INFO, '—', 'не завершено (брошено или закрыта квота), последний ответ: ' +
                   (last[-1] if last else 'нет'))
        return 'не завершено / квота'

    # ===================== полное интервью =====================
    dur = r.num('IVDur')
    if dur is not None and dur < MIN_DUR:
        ck.warn('IVDur', f'интервью {dur:g} мин — быстрее {MIN_DUR} мин (LOI ~40)')

    ck.single('S0', 'S0', allowed={1})
    ck.single('S1_1', 'S1_1', allowed={1})
    ck.single('S1_2', 'S1_2', allowed={1})
    ck.single('S1', 'S1', allowed={1, 2})
    ck.single('S2', 'S2', allowed={3, 4, 5})
    ck.rows('S3', 'S3', CATS, num_range=(0, 9999))
    active = [c for c in CATS if (s3[c] or 0) > 0]
    s31 = ck.rows('S3_1', 'S3_1', active, num_range=(1, 9999))
    for c, v in s31.items():
        if isinstance(v, float) and s3[c] is not None and v > s3[c]:
            ck.warn('S3_1', f'категория {c}: пациентов ({v:g}) больше, чем процедур ({s3[c]:g})')
    ck.single('S4', 'S4', allowed={1, 2, 3, 4})
    ck.single('S5', 'S5', allowed=set(range(1, 17)))
    ck.single('S6', 'S6', allowed={1, 2, 3, 96}, other=96)
    ck.single('S7', 'S7', allowed={1, 2, 3, 4, 96}, other=96)
    ck.single('S8', 'S8', allowed={2, 3})
    ck.single('S9', 'S9', allowed={1})
    ck.single('S10', 'S10', allowed={1, 2})
    ck.single('PD', 'PD', allowed={1, 2})

    # --- Раздел 1 ---
    ck.rows('Q1', 'Q1', range(1, 7), allowed=SCALE5 | {99})
    ck.sum_eq('Q2', ck.rows('Q2', 'Q2', range(1, 5), num_range=(0, 100)))
    for c in CATS:
        ck.multi(f'Q3_{c}', f'Q3_{c}', cond=c in active, max_n=3)
    ck.multi('Q4', 'Q4', max_n=3, exclusive=())
    ck.sum_eq('Q5', ck.rows('Q5', 'Q5', range(1, 4), num_range=(0, 100)))
    ck.single('Q6', 'Q6', allowed={1, 2, 3, 4, 5, 96}, other=96)

    # --- Раздел 2: блоки по категориям ---
    q7 = {}
    for c in CATS:
        on = c in active
        brands = set(build.BRANDS[c]) | {96}
        q7[c] = ck.multi(f'Q7_{c}', f'Q7_{c}', cond=on, max_n=5, allowed=brands | {97})
        used = q7[c] - {97}

        # Q8: 18 строк + необязательная «Другое» (96)
        q8 = ck.rows(f'Q8_{c}', f'Q8_{c}', list(range(1, 19)) + ([96] if r.has(f'Q8_{c}.96') else []) if on else [],
                     allowed=SCALE5 | {99})
        txt = r.has(f'Q8_{c}.96_T')
        if 96 in q8 and not txt:
            ck.err(f'Q8_{c}', 'строка «Другое» отмечена без текста')
        elif txt and 96 not in q8:
            ck.warn(f'Q8_{c}', f'текст в строке «Другое» ({r.v(f"Q8_{c}.96_T")!r}) без оценки')
        ck.straightline(f'Q8_{c}', {k: v for k, v in q8.items() if k != 96}, min_rows=18)

        assessed = used | ({JUVEDERM} if c == 1 else set()) if on else set()
        q9 = ck.rows(f'Q9_{c}', f'Q9_{c}', range(1, 19) if on else [], allowed=assessed | {99})
        if on and not assessed and any(v != 99 for v in q9.values()):
            ck.err(f'Q9_{c}', 'нет оцениваемых брендов — во всех строках должно быть 99')

        q10 = ck.rows(f'Q10_{c}', f'Q10_{c}', assessed, allowed={1, 2, 3, 4, 99})
        grow = {b for b, v in q10.items() if v == 1}
        ck.same_set(f'Q11_{c}', 'итерации цикла (бренды с «Увеличится» в Q10)', r.loop_codes(f'Q11_{c}'), grow)
        for b in grow:
            ck.multi(f'Q11_{c} [{b}]', f'Q11_{c}_{b}.{b}', max_n=3, other=14)

        q12 = ck.multi(f'Q12_{c}', f'Q12_{c}', cond=on, allowed=(brands - used) | {96, 97})
        ck.multi(f'Q13_{c}', f'Q13_{c}', cond=bool(q12) and 97 not in q12, max_n=3, exclusive=())

    # --- Раздел 3 ---
    q14 = ck.rows('Q14', 'Q14', active, allowed={1, 2, 3, 99} if len(active) > 1 else {1, 3, 99})
    from_rows = [c for c, v in q14.items() if v == 2]
    q141 = ck.rows('Q14_1', 'Q14_1', from_rows, allowed=set(active))
    for c, v in q141.items():
        if v == c:
            ck.err('Q14_1', f'строка {c}: выбрана та же категория')
    for c in CATS:
        same = q14.get(c) == 1
        f = ck.single(f'Q15_{c}_FROM', f'Q15_{c}_FROM', cond=same, allowed=set(build.BRANDS[c]) | {96}, other=96)
        t = ck.single(f'Q15_{c}_TO', f'Q15_{c}_TO', cond=same, allowed=set(build.BRANDS[c]) | {96}, other=96)
        if f is not None and f == t:
            ck.err(f'Q15_{c}_TO', 'бренд «на который» совпадает с исходным')
        ck.multi(f'Q16_{c}', f'Q16_{c}', cond=q14.get(c) in (1, 2), max_n=3, exclusive=())
    ck.multi('Q17', 'Q17')
    for c in CATS:
        q18 = r.table(f'Q18_{c}')
        ck.shown_if(f'Q18_{c}', c in active, bool(q18))
        if q18 and 1 not in q18:
            ck.err(f'Q18_{c}', 'не заполнено первое поле')
    q19 = ck.rows('Q19', 'Q19', CATS)
    for c, t in q19.items():
        if len(str(t).strip()) < 3:
            ck.err('Q19', f'категория {c}: ответ короче 3 символов')
    _texts(ck, 'Q19', q19)

    # --- Раздел 4 ---
    q20 = r.table('Q20')
    if 1 not in q20:
        ck.err('Q20', 'не заполнено первое упоминание')
    q21 = ck.multi('Q21', 'Q21', allowed=set(build.COMPANIES) | {96, 97})
    companies = q21 - {97}
    q22 = ck.rows('Q22', 'Q22', {ALLERGAN} | companies, num_range=(0, 99))
    for k, v in q22.items():
        if isinstance(v, float):
            must = k != ALLERGAN or ALLERGAN in q21
            if must and v < 1:
                ck.err('Q22', f'компания {k}: {v:g} взаимодействий, хотя отмечена в Q21 (нужно ≥ 1)')
            if v > 12:
                ck.warn('Q22', f'компания {k}: {v:g} взаимодействий за 3 месяца (> 12)')
    met = {k for k, v in q22.items() if isinstance(v, float) and v >= 1}
    ck.same_set('Q23', 'итерации цикла (компании с Q22 ≥ 1)', r.loop_codes('Q23'), met)
    ck.same_set('Q24', 'итерации цикла (компании с Q22 ≥ 1)', r.loop_codes('Q24'), met)
    for k in sorted(met):
        q23 = ck.rows(f'Q23 [{k}]', f'Q23_{k}.{k}', range(1, 12), allowed=SCALE5 | {99})
        ck.straightline(f'Q23 [{k}]', q23, min_rows=11)
        ck.multi(f'Q24 [{k}]', f'Q24_{k}.{k}', exclusive=())

    q25 = ck.multi('Q25', 'Q25', min_n=3, exclusive=())
    ck.ranking('Q25_RANK', 'Q25', q25)
    q26 = ck.rows('Q26', 'Q26', q25, num_range=(1, 99))
    for k, v in q26.items():
        if isinstance(v, float) and v > 12:
            ck.warn('Q26', f'канал {k}: {v:g} за 3 месяца (> 12)')
    q27 = ck.multi('Q27', 'Q27', min_n=3, max_n=5, exclusive=())
    ck.ranking('Q27_RANK', 'Q27', q27)
    ck.multi('Q28', 'Q28', max_n=3, exclusive=())
    q29_companies = {ALLERGAN} | companies
    ck.same_set('Q29', 'итерации цикла (Allergan + компании Q21)', r.loop_codes('Q29'), q29_companies)
    for k in sorted(q29_companies):
        q29 = ck.rows(f'Q29 [{k}]', f'Q29_{k}.{k}', range(1, 9), allowed=SCALE5)
        ck.straightline(f'Q29 [{k}]', q29, min_rows=8)
    ck.multi('Q30', 'Q30', max_n=3)

    # --- Раздел 5 ---
    ck.single('Q31', 'Q31', allowed={1, 2, 3, 4, 5, 99})
    ck.single('Q32', 'Q32', allowed={1, 2, 3, 4, 5, 6, 96}, other=96)
    for c in CATS:
        rows = sorted(q7[c] - {97}) if c in active else []
        pack = ck.rows(f'Q33_PACK_{c}', f'Q33_PACK_{c}', rows)
        lst = ck.rows(f'Q33_LIST_{c}', f'Q33_LIST_{c}', rows, num_range=(0, 99999999))
        net = ck.rows(f'Q33_NET_{c}', f'Q33_NET_{c}', rows, num_range=(0, 99999999))
        pack = r.table(f'Q33_PACK_{c}')  # текст как вписан («0» = не знаю)
        nums = [b for b, t in pack.items() if re.fullmatch(r'\d+([.,]\d+)?', t) and _num(t) != 0]
        if nums:
            ck.warn(f'Q33_PACK_{c}', 'в поле формата упаковки только число (похоже на цену/рейтинг): ' +
                    ', '.join(f'бренд {b} = {pack[b]}' for b in nums))
        hi = [b for b in rows if isinstance(net.get(b), float) and isinstance(lst.get(b), float)
              and net[b] > lst[b] > 0]
        if hi:
            ck.warn(f'Q33_NET_{c}', 'цена нетто выше прейскуранта: ' +
                    ', '.join(f'бренд {b} ({net[b]:g} > {lst[b]:g})' for b in hi))
    q34 = ck.rows('Q34', 'Q34', active, allowed={1, 2, 3, 99})
    for qn, kinds in (('Q35', (1, 3)), ('Q36', (2, 3))):
        cats = [c for c in active if q34.get(c) in kinds]
        vals = ck.rows(qn, qn, [c * 10 + k for c in cats for k in (1, 2, 3)], num_range=(0, 99999999))
        for c in cats:
            seq = [vals.get(c * 10 + k) for k in (1, 2, 3)]
            seq = [v for v in seq if isinstance(v, float) and v > 0]
            if any(b <= a for a, b in zip(seq, seq[1:])):
                ck.err(qn, f'категория {c}: не выполнено мин < сред < макс ({", ".join(f"{v:g}" for v in seq)})')
    q37 = ck.rows('Q37', 'Q37', list(range(1, 7)) + ([96] if r.has('Q37.96') else []), num_range=(0, 100))
    ck.sum_eq('Q37', q37)
    other37 = isinstance(q37.get(96), float) and q37[96] > 0
    if other37 and not r.has('Q37.96T'):
        ck.err('Q37', 'в «Другое» указана доля, но канал не вписан')
    elif r.has('Q37.96T') and not other37:
        ck.warn('Q37', f'вписан канал «Другое» ({r.v("Q37.96T")!r}) с долей 0')
    ck.rows('Q38', 'Q38', [k for k, v in q37.items() if isinstance(v, float) and v > 0], allowed={1, 2, 3})
    ck.multi('Q39', 'Q39', max_n=3, exclusive=())
    ck.single('Q40', 'Q40', allowed={1, 2, 3, 4, 5, 99})
    q41 = ck.multi('Q41', 'Q41', min_n=3, max_n=3, exclusive=())
    ck.ranking('Q41_RANK', 'Q41', q41)
    for q in ('Q42', 'Q43'):
        if not r.has(q):
            ck.err(q, 'нет ответа')
        _texts(ck, q, {0: r.v(q)})

    # --- AE скрыт (AE_ENABLED = False) ---
    if not build.AE_ENABLED:
        stray = r.all_empty(r'AE\d+')
        if stray:
            ck.err('AE', 'блок НЯ скрыт, но есть ответы: ' + ', '.join(stray))
    else:
        r.all_empty(r'AE\d+')  # блок включён — правила не написаны, только отмечаем колонки проверенными
    return 'полное'


def _texts(ck, q, texts):
    """ВНИМАНИЕ: открытый ответ без букв или «не понимаю вопрос»."""
    for k, t in texts.items():
        if t is None:
            continue
        s = str(t).strip()
        where = f'строка {k}: ' if k else ''
        if not re.search(r'[A-Za-zА-Яа-яЁё]', s):
            ck.warn(q, f'{where}ответ без букв: {s!r}')
        elif re.search(r'не\s*понят|не\s*понима', s, re.I):
            ck.warn(q, f'{where}респондент не понял вопрос: {s[:80]!r}')


def _touch_all(r):
    """Для отсеянных/незавершённых проверяем только отсев — остальные колонки считаем просмотренными."""
    r.touched.update(r.cols.names)


def main():
    global MIN_DUR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('export', help='выгрузка .xlsx или .sav')
    ap.add_argument('--out', help='сохранить отчёт в .xlsx')
    ap.add_argument('--min-dur', type=float, default=MIN_DUR, help='порог «слишком быстро», мин (по умолчанию 15)')
    a = ap.parse_args()
    MIN_DUR = a.min_dur
    rep = run(a.export, check, out_xlsx=a.out)
    sys.exit(1 if rep.count('ОШИБКА') else 0)


if __name__ == '__main__':
    main()
