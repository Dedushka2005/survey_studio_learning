"""Шаблон проверки выгрузки поля (SPSS .sav) на соответствие логике анкеты (build.py).

Запуск:  python3 surveys/<проект>/check_data.py <выгрузка.sav>
Нужен pyreadstat (pip install pyreadstat). Данные респондентов в репозиторий не кладём (файлы — в scratchpad).

Правила = логика build.py: каждое условие показа, фильтр строк/колонок, число ответов, суммы, «Другое» ↔ текст,
циклы. ERR — нарушение логики, WARN — качество (мягкие предупреждения, «прямолинейные» ответы, странные числа).
Справочники берём импортом из build.py (там save() — под `if __name__ == '__main__'`). Перед проверкой посмотреть
колонки выгрузки (имена зависят от системы). Скрипт проверить на испорченной копии: каждая ошибка должна найтись.
Образцы — surveys/hcp_perception_ru/check_data.py, surveys/aesthetics_ru_v2/check_data.py.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
sys.path.insert(0, HERE)
from ss_check import is_flat, load_links, num, run  # noqa: E402,F401
# from build import BRANDS  # noqa: E402  — справочники анкеты

LINKS = os.path.join(HERE, 'links', '<проект>_links_<N>.xlsx')
MIN_DUR = 15  # мин; быстрее — подозрение на «пролистывание»


def check(R, links):
    if links.get(R.v('RespExtID')) != num(R.v('Rid')):
        R.err(f'Rid {num(R.v("Rid"))} не соответствует extid по базе')
    # скринер: только проходные коды
    R.check_single('S1', allowed={1})
    R.check_single('S2', allowed={1, 2, 96}, other_txt='S2_96T')
    # таблица: ответы ровно в нужных строках
    s3 = R.check_rows('S3', [1, 2, 3], lo=0, hi=9999)
    active = [c for c, v in s3.items() if v > 0]
    # вопрос с условием: asked=False → ответа быть не должно
    R.check_multi('Q1', mx=3, none_code=97, asked=bool(active))
    R.check_other_row('Q2')  # числовая строка «Другое» в таблице
    t = R.table('Q3')
    if is_flat(t):
        R.warn(f'Q3: одинаковый ответ во всех {len(t)} строках')
    if R.has('AE'):
        R.err('AE: есть ответы, а блок скрыт')


if __name__ == '__main__':
    run(sys.argv[1], check, load_links(LINKS), MIN_DUR, '~30')
