#!/usr/bin/env python3
"""Персональные ссылки на веб-опрос (CAWI) + файл базы контактов для SURVEYSTUDIO.

    python3 tools/make_links.py https://sst.gl/algln1026 5000 out/links.xlsx
    python3 tools/make_links.py https://sst.gl/algsh1026 7000 out/links.xlsx --types 1:3500,2:3500

Каждой ссылке — простой номер Rid (1..N, чтобы быстро найти интервью) и случайный ID (extid), который
не подобрать. С --types добавляется столбец type (диапазонами Rid: сначала все ссылки типа 1, потом 2 …).
Один файл xlsx служит и списком ссылок для рассылки, и базой контактов для загрузки:
  Rid      — «Поле с данными» (в анкете: contact.data['Rid'] -> скрытый вопрос Rid)
  type     — «Поле с данными» (в анкете: contact.data['type'] -> скрытый вопрос Type), если есть
  ID       — «Внешний ключ»
  Телефон  — «Телефон» (фиктивный, система требует телефон: 10000 + Rid)
  Ссылка   — «Пропустить»
Повторный запуск создаёт НОВЫЕ ID — уже разосланные ссылки перестанут совпадать с базой.
"""
import argparse
import secrets

from openpyxl import Workbook
from openpyxl.styles import Font

ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'  # без похожих символов: 0/o, 1/l/i
ID_LEN = 10                                     # 31^10 ≈ 8·10^14 вариантов


def make_ids(n):
    ids = set()
    while len(ids) < n:
        ids.add(''.join(secrets.choice(ALPHABET) for _ in range(ID_LEN)))
    return list(ids)


def parse_types(spec, n):
    """'1:3500,2:3500' -> [1]*3500 + [2]*3500 (сумма должна быть равна n)."""
    types = []
    for part in spec.split(','):
        code, count = part.split(':')
        types += [int(code)] * int(count)
    assert len(types) == n, f'сумма по типам {len(types)} != {n}'
    return types


def main(base_url, n, out, types_spec=None):
    sep = '&' if '?' in base_url else '?'
    types = parse_types(types_spec, n) if types_spec else None
    wb = Workbook()
    ws = wb.active
    ws.title = 'Ссылки'
    head = ['Rid'] + (['type'] if types else []) + ['ID', 'Телефон', 'Ссылка']
    ws.append(head)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for rid, extid in enumerate(make_ids(n), 1):
        ws.append([rid] + ([types[rid - 1]] if types else []) +
                  [extid, str(10000 + rid), f'{base_url}{sep}extid={extid}'])
    for col, width in zip('ABCDEF', [8] + ([6] if types else []) + [14, 10, 50]):
        ws.column_dimensions[col].width = width
    wb.save(out)
    print(f'{out}: {n} ссылок' + (f', типы {types_spec}' if types else ''))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('base_url')
    ap.add_argument('n', type=int)
    ap.add_argument('out')
    ap.add_argument('--types', help='коды типов и число ссылок: 1:3500,2:3500')
    a = ap.parse_args()
    main(a.base_url, a.n, a.out, a.types)
