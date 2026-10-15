#!/usr/bin/env python3
"""Персональные ссылки на веб-опрос (CAWI) + файл базы контактов для SURVEYSTUDIO.

    python3 tools/make_links.py https://sst.gl/algln1026 5000 out/links.xlsx

Каждой ссылке — простой номер Rid (1..N, чтобы быстро найти интервью) и случайный ID (extid), который
не подобрать. Один файл xlsx служит и списком ссылок для рассылки, и базой контактов для загрузки:
  Rid      — «Поле с данными» (в анкете: contact.data['Rid'] -> скрытый вопрос Rid)
  ID       — «Внешний ключ»
  Телефон  — «Телефон» (фиктивный, система требует телефон: 10000 + Rid)
  Ссылка   — «Пропустить»
Повторный запуск создаёт НОВЫЕ ID — уже разосланные ссылки перестанут совпадать с базой.
"""
import secrets
import sys

from openpyxl import Workbook
from openpyxl.styles import Font

ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'  # без похожих символов: 0/o, 1/l/i
ID_LEN = 10                                     # 31^10 ≈ 8·10^14 вариантов


def make_ids(n):
    ids = set()
    while len(ids) < n:
        ids.add(''.join(secrets.choice(ALPHABET) for _ in range(ID_LEN)))
    return list(ids)


def main(base_url, n, out):
    sep = '&' if '?' in base_url else '?'
    wb = Workbook()
    ws = wb.active
    ws.title = 'Ссылки'
    ws.append(['Rid', 'ID', 'Телефон', 'Ссылка'])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for rid, extid in enumerate(make_ids(n), 1):
        ws.append([rid, extid, str(10000 + rid), f'{base_url}{sep}extid={extid}'])
    for col, width in zip('ABCD', (8, 14, 10, 50)):
        ws.column_dimensions[col].width = width
    wb.save(out)
    print(f'{out}: {n} ссылок')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3])
