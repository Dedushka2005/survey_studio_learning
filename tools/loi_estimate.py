"""Оценка длительности заполнения анкеты (LOI) по JSON-файлу SURVEYSTUDIO.

Идея: для каждого показанного экрана время = чтение текста + действия респондента.
Какие строки/ответы видит респондент, зависит от логики, поэтому для вопросов с фильтрами
задаётся «сценарий» — сколько строк/ответов показано и сколько действий нужно.

Использование из кода:
    from loi_estimate import estimate, NORMS
    total, rows = estimate('survey.json', scenario={130: {'rows': 8}, 8000: {'skip': True}},
                           loops={80: 3, 90: 3})
"""
import json
import re

# Нормативы, секунд (типичные значения для веб-опросов, респондент-специалист)
NORMS = {
    'read_word': 0.30,        # чтение текста вопроса/инструкции, на слово (~200 слов/мин)
    'scan_word': 0.12,        # просмотр текста вариантов ответа/строк, на слово
    'long_text_share': 0.30,  # какую долю длинных текстов (> 300 слов, согласия) реально читают
    'page': 3.0,              # переход на следующий экран, загрузка
    'click': 2.5,             # выбор варианта в простом вопросе
    'row_choice': 4.0,        # выбор в строке таблицы (шкала, NPS)
    'dropdown': 5.0,          # выбор в выпадающем списке
    'number_simple': 5.0,     # ввод простого числа (возраст, кол-во)
    'number_estimate': 9.0,   # ввод оценки, требующей подумать (%, мл, цена)
    'text_short': 15.0,       # короткий открытый ответ (название марки, «другое»)
    'text_long': 35.0,        # развёрнутый открытый ответ (причина)
}

CHOICE = {'SingleChoice', 'Dropdown_SingleChoice'}
MULTI = {'MultipleChoice', 'Dropdown_MultipleChoice'}
TABLE_CHOICE = {'Table_SingleChoice', 'Table_MultipleChoice', 'Table_Rating'}


def words(html):
    text = re.sub(r'<[^>]+>', ' ', html or '')
    text = re.sub(r'\{[^}]*\}', 'категория', text)
    return len(re.findall(r'\w+', text))


def estimate(path, scenario=None, loops=None, norms=None):
    """scenario: {номер: {'skip': True, 'rows': N, 'answers': N, 'picks': N, 'number': 'simple'|'estimate',
    'text': 'short'|'long', 'repeat': N}}; loops: {номер исходного вопроса цикла: число итераций}."""
    n = dict(NORMS, **(norms or {}))
    scenario = scenario or {}
    loops = loops or {}
    data = json.load(open(path, encoding='utf-8'))
    lists = {a['Name']: a['AnswerItems'] for a in data['AnswerLists']}
    result = []
    for x in data['Questions']:
        sc = scenario.get(x['Number'], {})
        if sc.get('skip'):
            continue
        qtype = x['QuestionType']
        repeat = sc.get('repeat', loops.get(x['Number'], 1))
        answers = lists.get(x.get('AnswerList'), [])
        rows = lists.get(x.get('RowList'), [])
        n_rows = sc.get('rows', len(rows))
        n_ans = sc.get('answers', len(answers))
        # чтение
        w = words(x['Text']) + words(x.get('Comment'))
        read = w * n['read_word']
        if w > 300:
            read *= n['long_text_share']
        avg_ans_words = (sum(words(a['Text']) for a in answers) / len(answers)) if answers else 0
        avg_row_words = (sum(words(r['Text']) for r in rows) / len(rows)) if rows else 0
        scan = (n_ans * avg_ans_words + n_rows * avg_row_words) * n['scan_word']
        # действия
        num = n['number_' + sc.get('number', 'estimate')]
        txt = n['text_' + sc.get('text', 'short')]
        if qtype in CHOICE:
            act = n['click'] + sc.get('extra', 0)
        elif qtype in MULTI:
            act = n['click'] * sc.get('picks', 2)
        elif qtype in TABLE_CHOICE:
            act = n['row_choice'] * n_rows * sc.get('picks', 1)
        elif qtype == 'Table_Dropdown_SingleChoice':
            act = n['dropdown'] * n_rows
        elif qtype == 'Table_Numeric':
            act = num * n_rows
        elif qtype == 'Numeric':
            act = num
        elif qtype == 'Table_Text':
            act = txt * n_rows
        elif qtype in ('Text', 'Phone', 'Email'):
            act = txt
        else:  # Information, WelcomeScreen
            act = 0
        sec = (read + scan + act + n['page']) * repeat
        result.append((x['Number'], x.get('OutputColumnTemplate', ''), qtype, repeat, round(sec)))
    total = sum(r[4] for r in result)
    return total, result
