"""Оценка длительности анкеты Aesthetics RU по трём сценариям респондента."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from loi_estimate import estimate  # noqa: E402

BRANDS = {1: 18, 2: 9, 3: 7}          # марок в списке категории
AREAS = {1: 11, 2: 12, 3: 11}         # областей в списке категории
BASES = {1: 130, 2: 210, 3: 290}


def scenario(cats, used, areas_used, aware, mentions, both_prices, low_scores, q1b_rows):
    """cats — активные категории; used/areas_used/aware/mentions — число на категорию."""
    k = len(cats)
    s = {
        41: {'skip': True}, 8000: {'skip': True}, 8500: {'skip': True},  # служебные
        5003: {'number': 'simple'},
        5012: {'rows': 5, 'text': 'short'},
        5016: {'picks': 3},
        10: {'number': 'simple'}, 11: {'rows': q1b_rows},
        30: {'rows': k}, 31: {'rows': k}, 40: {'rows': k}, 50: {'rows': k},
        60: {'rows': 3 * k}, 61: {'rows': 2 * k},
        70: {'rows': 5},
    }
    avg = lambda d: sum(d[c] for c in cats) / k  # noqa: E731
    s[80] = {'rows': avg(mentions), 'repeat': k}
    s[90] = {'answers': avg(BRANDS) + 2, 'picks': avg(aware), 'repeat': k}
    s[100] = {'rows': avg(aware), 'repeat': k}
    # Q11 — марки с оценкой 0-6; Q12 — они же + Ювидерм (считаем, что Ювидерм оценён на 7-10)
    s[110] = {'text': 'long', 'repeat': low_scores} if low_scores else {'skip': True}
    s[120] = {'picks': 2, 'repeat': low_scores + 1}
    for c in (1, 2, 3):
        b = BASES[c]
        if c not in cats:
            for d in range(0, 80, 10):
                s[b + d] = {'skip': True}
            continue
        zeros = (BRANDS[c] + 1 - used[c]) * 0.25    # ввод «0» в неиспользуемых строках — быстро
        s[b] = {'rows': used[c] + zeros}
        s[b + 10] = {'rows': used[c]}
        s[b + 20] = {'rows': areas_used[c] + (AREAS[c] + 1 - areas_used[c]) * 0.25}
        s[b + 30] = {'rows': areas_used[c]}
        s[b + 40] = {'rows': 8}
        s[b + 60] = {}
        s[b + 70] = {} if both_prices else {'skip': True}
    return s


SCENARIOS = {
    'Минимум (1 категория, мало марок)': scenario(
        cats=[1], used={1: 2}, areas_used={1: 3}, aware={1: 4}, mentions={1: 2},
        both_prices=False, low_scores=0, q1b_rows=3),
    'Типичный (3 категории)': scenario(
        cats=[1, 2, 3], used={1: 4, 2: 3, 3: 2}, areas_used={1: 6, 2: 5, 3: 4},
        aware={1: 8, 2: 5, 3: 4}, mentions={1: 3, 2: 3, 3: 2},
        both_prices=False, low_scores=2, q1b_rows=5),
    'Максимум (3 категории, много марок)': scenario(
        cats=[1, 2, 3], used={1: 7, 2: 5, 3: 4}, areas_used={1: 9, 2: 9, 3: 8},
        aware={1: 14, 2: 8, 3: 6}, mentions={1: 5, 2: 5, 3: 5},
        both_prices=True, low_scores=6, q1b_rows=6),
}

SECTIONS = [('Скринер и согласия', lambda n: 5000 <= n <= 5999),
            ('Раздел 1 (Q1–Q7)', lambda n: 10 <= n <= 79),
            ('Раздел 2 (Q8–Q12)', lambda n: 80 <= n <= 120 or n == 8001),
            ('Раздел 3 (Q13–Q36)', lambda n: 130 <= n <= 360)]

if __name__ == '__main__':
    path = os.path.join(HERE, 'aesthetics_ru.json')
    for name, sc in SCENARIOS.items():
        total, rows = estimate(path, sc)
        parts = []
        for title, in_section in SECTIONS:
            sec = sum(r[4] for r in rows if in_section(r[0]))
            parts.append(f'{title}: {sec / 60:.1f}')
        print(f'{name}: {total / 60:.0f} мин  ({"; ".join(parts)})')
