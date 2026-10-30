#!/usr/bin/env python3
"""Сверка выгрузки анкеты из SURVEYSTUDIO с JSON, собранным build.py.

    python3 tools/compare_export.py surveys/<проект>/<проект>.json <выгрузка из системы>.json [--functions]

Печатает различающиеся поля (REPO — репозиторий, SYS — система) без шума от значений по умолчанию,
которые система добавляет при выгрузке (DisplayMode, ButtonStartPlacement и т.п.).
Раздел «Функции» не сравнивается построчно: проверяется только, что все функции библиотеки,
вызываемые в скриптах вопросов, в системе определены (сам раздел при правках вручную не обновляется).
--functions — дополнительно построчный diff «Функций» (например, после ручной правки одной функции в системе).
"""
import difflib
import json
import re
import sys

# Поля, которые система выгружает со значениями по умолчанию, а сборщик не пишет
# (ImageAlignment, *TemplateSeparator, MultipleChoiceExportMode — в формате выгрузки с 30.10.2026)
NOISE = ('AllowedAttachmentsType', 'AnswersSumControlMode', 'ButtonStartPlacement', 'DisplayMode',
         'ImageSize', 'Placement', 'ImageAlignment', 'TemplateSeparator', 'MultipleChoiceExportMode')
EMPTY = (False, None, '', 'None', 'Default', 0)


def plain(text):
    """Текст без оформления: теги, &nbsp;, пробелы — чтобы отличать правки слов от правок вёрстки."""
    text = re.sub(r'<[^>]+>', ' ', text.replace('&nbsp;', ' '))
    return ' '.join(text.split())


def flatten(data):
    out = {}

    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                if k != 'OrderIdx':
                    walk(v, path + (k,))
        elif isinstance(x, list):
            for i, v in enumerate(x):
                key = v.get('Number', v.get('Name', v.get('Code', i))) if isinstance(v, dict) else i
                walk(v, path + (str(key),))
        elif x not in EMPTY:
            out[path] = x

    walk(data, ())
    return out


def missing_functions(repo, sys_):
    """Функции библиотеки, которые вызываются в скриптах системы, но не определены в её разделе «Функции»."""
    lib = set(re.findall(r'function (\w+)\s*\(', repo.get('ScriptGlobalFunctions') or ''))
    defined = set(re.findall(r'function (\w+)\s*\(', sys_.get('ScriptGlobalFunctions') or ''))
    scripts = [sys_.get('ScriptPreProcessing') or '']
    scripts += [v for q in sys_['Questions'] for k, v in q.items() if k.startswith('Script') and v]
    called = {f for s in scripts for f in re.findall(r'\b([a-zA-Z_]\w*)\s*\(', s)}
    return sorted((called & lib) - defined)


def main(repo_path, sys_path, functions=False):
    repo, sys_ = json.load(open(repo_path)), json.load(open(sys_path))
    a, b = flatten(repo), flatten(sys_)
    found = 0
    for k in sorted(set(a) | set(b), key=str):
        if k[0] == 'ScriptGlobalFunctions' or a.get(k) == b.get(k):
            continue
        if k[-1].endswith(NOISE) and k not in a:
            continue
        found += 1
        va, vb = a.get(k), b.get(k)
        if isinstance(va, str) and isinstance(vb, str) and plain(va) == plain(vb):
            print('/'.join(k), '— только оформление (теги, &nbsp;, пробелы)')
            continue
        print('/'.join(k))
        print('  REPO:', repr(a.get(k))[:1500])
        print('  SYS :', repr(b.get(k))[:1500])
    if functions:
        fa = (repo.get('ScriptGlobalFunctions') or '').replace('\r', '').splitlines()
        fb = (sys_.get('ScriptGlobalFunctions') or '').replace('\r', '').splitlines()
        for line in difflib.unified_diff(fa, fb, 'REPO', 'SYS', lineterm='', n=1):
            print('  ' + line)
    missing = missing_functions(repo, sys_)
    if missing:
        print('!!! В разделе «Функции» системы нет вызываемых функций:', ', '.join(missing))
    print(f'Различий: {found}' + ('' if repo.get('ScriptGlobalFunctions') == sys_.get('ScriptGlobalFunctions')
                                  else ' (раздел «Функции» отличается — см. проверку вызовов выше)'))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--functions']
    if len(args) != 2:
        sys.exit(__doc__)
    main(args[0], args[1], functions='--functions' in sys.argv)
