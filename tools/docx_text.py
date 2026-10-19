#!/usr/bin/env python3
"""Текст ТЗ из docx в порядке документа: абзацы и строки таблиц (ячейки через « | »).

Использование:
    python3 -I tools/docx_text.py ТЗ.docx [out.txt]

Без out.txt печатает в stdout. Две версии ТЗ удобно сравнить: извлечь обе и `diff old.txt new.txt`.
Файлы заказчика и извлечённый текст не коммитим (конфиденциально) — класть в scratchpad.
Нужен пакет python-docx.
"""
import sys

import docx
from docx.oxml.ns import qn


def docx_lines(path):
    body = docx.Document(path).element.body
    lines = []
    for el in body.iterchildren():
        if el.tag == qn('w:p'):
            text = ''.join(t.text or '' for t in el.iter(qn('w:t')))
            if text.strip():
                lines.append(text)
        elif el.tag == qn('w:tbl'):
            for tr in el.iter(qn('w:tr')):
                cells = [''.join(t.text or '' for t in tc.iter(qn('w:t'))) for tc in tr.iter(qn('w:tc'))]
                lines.append(' | '.join(cells))
    return lines


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    text = '\n'.join(docx_lines(sys.argv[1])) + '\n'
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'w', encoding='utf-8') as f:
            f.write(text)
    else:
        sys.stdout.write(text)
