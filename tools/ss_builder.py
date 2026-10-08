"""Библиотека для сборки анкет SURVEYSTUDIO в JSON (формат SS2EQN 2.4).

Пример:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
    from ss_builder import Questionnaire, screen_if, OTHER_TXT

    qnr = Questionnaire('Моя анкета', screen_text='Спасибо, вы не подходите.')
    q, alist = qnr.q, qnr.alist
    q(1, 'SingleChoice', 'Ваш пол?', name='S1',
      AnswerList=alist('Пол', {1: 'Мужской', 2: 'Женский'}))
    q(2, 'Numeric', 'Ваш возраст?', name='S2', AnswerNumberFrom=0, AnswerNumberTo=120,
      after='if (Q.openValueInt < 18) return screenOut();')
    qnr.save('my_survey.json')

Общие JS-функции (screenOut, refuseOut, numRow, showRowsWhere, …) лежат в tools/ss_lib.js
и автоматически добавляются в раздел «Функции» анкеты.
"""
import json
import os
import shutil
import subprocess
import tempfile

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
JS_LIB = os.path.join(TOOLS_DIR, 'ss_lib.js')

DEFAULT_SCREEN_TEXT = ('Благодарим вас за уделенное время! К сожалению, по условиям исследования '
                       'вы не можете принять в нем участие.')
DEFAULT_REFUSE_TEXT = 'Благодарим вас за уделенное время! До свидания.'

# Часто используемые наборы флагов варианта ответа / строки
OTHER_TXT = {'OpenValueTxt': True}                    # «Другое (укажите)»
OTHER_NUM = {'OpenValueNum': True}                    # поле для числа
BLOCKING = {'Blocking': True}                         # исключающий («Затрудняюсь ответить»)
FIXED = {'DisableReordering': True}                   # не перемешивать
NO_LOOP = {'DisableRepeat': True}                     # не использовать в циклах
OPT_ROW = {'CustomRowValidation': True}               # строка таблицы необязательна
OTHER_ROW = {'OpenValueTxt': True, 'AllowEmptyOpenValue': True, 'DisableReordering': True}


def js_str(text):
    """Строка Python -> строковый литерал JavaScript."""
    return json.dumps(text, ensure_ascii=False)


def _checked_any(codes):
    return ' || '.join(f'Q.isChecked({c})' for c in codes)


def screen_if(codes):
    """Скрипт после ответа: скринаут («Скрининг»), если выбран один из кодов."""
    return f'if ({_checked_any(codes)}) return screenOut();'


def refuse_if(codes):
    """Скрипт после ответа: завершение при отказе («Завершено»), если выбран один из кодов."""
    return f'if ({_checked_any(codes)}) return refuseOut();'


def action(atype, condition=None, n1=None, t1=None, n2=None, t2=None):
    """Действие перед показом / после ответа (ActionType см. в шпаргалке)."""
    a = {'ActionType': atype}
    if condition:
        a['Condition'] = condition
    for key, value in (('ActionVarLong1', n1), ('ActionVarTxt1', t1),
                       ('ActionVarLong2', n2), ('ActionVarTxt2', t2)):
        if value is not None:
            a[key] = value
    return a


def common_functions(screen_text=DEFAULT_SCREEN_TEXT, refuse_text=DEFAULT_REFUSE_TEXT):
    """Текст общей JS-библиотеки с подставленными текстами завершения."""
    with open(JS_LIB, encoding='utf-8') as f:
        js = f.read()
    return js.replace('__SCREEN_TEXT__', js_str(screen_text)).replace('__REFUSE_TEXT__', js_str(refuse_text))


class Questionnaire:
    def __init__(self, name, screen_text=DEFAULT_SCREEN_TEXT, refuse_text=DEFAULT_REFUSE_TEXT,
                 questionnaire_flags=None, survey_flags=None):
        self.name = name
        self.screen_text = screen_text
        self.refuse_text = refuse_text
        # по умолчанию: автоформирование имён переменных и новый сервис опросов («Запускать опрос в новой веб-дате»)
        self.questionnaire_flags = {'AddSubstitutionsToTemplates': True, 'RunInNewService': True}
        self.questionnaire_flags.update(questionnaire_flags or {})
        # номера вопросов показываем, коды ответов скрываем
        self.survey_flags = {'HideQuestionNumbers': False, 'HideAnswerCodes': True}
        self.survey_flags.update(survey_flags or {})
        self.global_functions = ''   # функции конкретной анкеты (добавляются после общих)
        self.preprocessing = ''      # скрипт «Подготовка»
        self.postprocessing = ''     # скрипт «Обработка»
        self.before_show = ''        # глобальный «Перед показом»
        self.after_answer = ''       # глобальный «После ответа»
        self.css = ''
        self.questions = []
        self.answer_lists = {}

    # ------------------------------------------------------------------ списки
    def alist(self, name, items, flags=None, lst_type='Common'):
        """Список вариантов ответа / строк. Повторный вызов с тем же именем вернёт имя.

        items: dict {код: текст} или список пар; flags: {код: {флаг: True}}.
        """
        if name in self.answer_lists:
            return name
        flags = flags or {}
        pairs = list(items.items()) if isinstance(items, dict) else list(items)
        self.answer_lists[name] = {
            'Name': name,
            'Type': lst_type,
            'AnswerItems': [
                {'OrderIdx': i + 1, 'Code': code, 'Text': text, 'ExportedFlags': flags.get(code, {})}
                for i, (code, text) in enumerate(pairs)
            ],
        }
        return name

    # ----------------------------------------------------------------- вопросы
    def q(self, number, qtype, text, name=None, comment=None, flags=None, survey_flags=None,
          before=None, after=None, before_actions=None, after_actions=None, **props):
        """Добавить вопрос в конец анкеты.

        name — имя переменной в массиве; before/after — скрипты перед показом / после ответа;
        props — любые свойства вопроса из формата файла (AnswerList, RowList, Condition, …).
        """
        item = {
            'OrderIdx': len(self.questions) + 1,
            'Number': number,
            'Text': text,
            'QuestionType': qtype,
            'ExportedQuestionFlags': flags or {},
            'ExportedSurveyFlags': survey_flags or {},
        }
        if name:
            item['OutputColumnTemplate'] = name
        if comment:
            item['Comment'] = comment
        if before:
            item['ScriptBeforeShow'] = before.strip()
        if after:
            item['ScriptAfterAnswer'] = after.strip()
        for key, acts in (('BeforeShowActions', before_actions), ('AfterAnswerActions', after_actions)):
            if acts:
                item[key] = [dict(a, OrderIdx=i + 1) for i, a in enumerate(acts)]
        item.update(props)
        self.questions.append(item)
        return item

    # ------------------------------------------------------------------ сборка
    def to_dict(self):
        functions = common_functions(self.screen_text, self.refuse_text).strip()
        if self.global_functions.strip():
            functions += '\n\n// ===== Функции этой анкеты =====\n\n' + self.global_functions.strip()
        data = {
            'Magic': 'SS2EQN',
            'Version': '2.4',
            'Name': self.name,
            'ExportedQuestionnaireFlags': self.questionnaire_flags,
            'ExportedSurveyFlags': self.survey_flags,
            'ScriptGlobalFunctions': functions,
        }
        for key, value in (('ScriptPreProcessing', self.preprocessing),
                           ('ScriptPostProcessing', self.postprocessing),
                           ('ScriptBeforeShow', self.before_show),
                           ('ScriptAfterAnswer', self.after_answer),
                           ('ScriptCSS', self.css)):
            if value.strip():
                data[key] = value.strip()
        data['Questions'] = self.questions
        data['AnswerLists'] = list(self.answer_lists.values())
        self.resolve_macros(data)
        return data

    @staticmethod
    def resolve_macros(data):
        """Подстановки {ИМЯ.96T} -> {Q<номер>.96T}.

        SURVEYSTUDIO понимает в подстановках только системный номер вопроса ({Q12100.96T}), а не имя шаблона
        (подтверждено на тесте). В текстах можно писать имя — здесь оно заменяется на номер.
        Ссылка {Q<номер>…} на несуществующий вопрос — ошибка.
        """
        import re
        by_name = {x['OutputColumnTemplate']: x['Number'] for x in data['Questions']
                   if x.get('OutputColumnTemplate') and '{' not in x['OutputColumnTemplate']}
        numbers = {x['Number'] for x in data['Questions']}
        problems = []

        def fix(text, where):
            def repl(m):
                name, rest = m.group(1), m.group(2) or ''
                if name in by_name:
                    return '{Q%d%s}' % (by_name[name], rest)
                num = re.fullmatch(r'Q(\d+)', name)
                if num and int(num.group(1)) not in numbers:
                    problems.append(f'{where}: подстановка {{{name}{rest}}} — нет такого вопроса')
                return m.group(0)
            return re.sub(r'\{([A-Za-z]\w*)((?:\.[0-9A-Za-z]+)*)\}', repl, text)

        for x in data['Questions']:
            for key in ('Text', 'Comment'):
                if x.get(key):
                    x[key] = fix(x[key], f"Q{x['Number']} {key}")
        for lst in data['AnswerLists']:
            for item in lst['AnswerItems']:
                if item.get('Text'):
                    item['Text'] = fix(item['Text'], f"список «{lst['Name']}»")
        assert not problems, '\n'.join(problems)

    def validate(self, data):
        numbers = [x['Number'] for x in data['Questions']]
        dup = {n for n in numbers if numbers.count(n) > 1}
        assert not dup, f'повторяются номера вопросов: {sorted(dup)}'
        names = [x['OutputColumnTemplate'].lower() for x in data['Questions'] if x.get('OutputColumnTemplate')]
        dup = {n for n in names if names.count(n) > 1}
        assert not dup, f'повторяются имена переменных: {sorted(dup)}'
        lists = {a['Name'] for a in data['AnswerLists']}
        for x in data['Questions']:
            for key in ('AnswerList', 'RowList', 'ColumnList'):
                if key in x:
                    assert x[key] in lists, f"Q{x['Number']}: нет списка «{x[key]}»"
        for a in data['AnswerLists']:
            codes = [i['Code'] for i in a['AnswerItems']]
            assert len(codes) == len(set(codes)), f"список «{a['Name']}»: повторяются коды"
        self.check_references(data)
        self.check_js_syntax(data)

    @staticmethod
    def check_references(data):
        """Проверить, что вопросы, упомянутые в скриптах и условиях, существуют.

        В скриптах допустимы Q<номер> и имена шаблонов (флаг GenerateQuestionVariableByTemplate),
        в условиях (язык выражений) — только Q<номер>.
        """
        import re
        numbers = {x['Number'] for x in data['Questions']}
        by_name = data.get('ExportedQuestionnaireFlags', {}).get('GenerateQuestionVariableByTemplate')
        names = {x['OutputColumnTemplate'] for x in data['Questions']
                 if by_name and x.get('OutputColumnTemplate') and '{' not in x['OutputColumnTemplate']}
        problems = []

        def known(token):
            if token in names:
                return True
            m = re.fullmatch(r'Q(\d+)', token)
            # номера вопросов циклов создаются при запуске — их не проверить
            return bool(m) and (int(m.group(1)) in numbers or len(m.group(1)) > 6)

        scripts = [('Функции', data.get('ScriptGlobalFunctions', '')),
                   ('Подготовка', data.get('ScriptPreProcessing', '')),
                   ('Обработка', data.get('ScriptPostProcessing', ''))]
        for x in data['Questions']:
            for key in ('ScriptBeforeShow', 'ScriptAfterAnswer'):
                if x.get(key):
                    scripts.append((f"Q{x['Number']} {key}", x[key]))
        for where, code in scripts:
            code = re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`[^`]*`|//[^\n]*", '', code)
            for token in set(re.findall(r'\b([QS]\d\w*)\b', code)):
                if not known(token):
                    problems.append(f'{where}: неизвестный вопрос {token}')
        for x in data['Questions']:
            conds = [x.get('Condition') or '']
            conds += [a.get('Condition') or '' for k in ('BeforeShowActions', 'AfterAnswerActions')
                      for a in x.get(k, [])]
            for cond in conds:
                for num in re.findall(r'\bQ(\d+)', cond):
                    if int(num) not in numbers:
                        problems.append(f"Q{x['Number']} условие: нет вопроса Q{num}")
        assert not problems, '\n'.join(problems)

    @staticmethod
    def check_js_syntax(data):
        """Проверить синтаксис всех скриптов через Node.js (если он установлен)."""
        node = shutil.which('node')
        if not node:
            print('Node.js не найден — синтаксис скриптов не проверен')
            return
        scripts = [('Функции', data.get('ScriptGlobalFunctions', ''), False)]
        for key in ('ScriptPreProcessing', 'ScriptPostProcessing'):
            scripts.append((key, data.get(key, ''), False))
        for key in ('ScriptBeforeShow', 'ScriptAfterAnswer'):
            scripts.append(('глобальный ' + key, data.get(key, ''), True))
        for x in data['Questions']:
            for key in ('ScriptBeforeShow', 'ScriptAfterAnswer'):
                if x.get(key):
                    scripts.append((f"Q{x['Number']} {key}", x[key], True))
        checker = ("const s=JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'));let bad=0;"
                   "for(const [n,b,w] of s){try{new Function(w?'Q':'',b)}catch(e){bad++;"
                   "console.log('Ошибка синтаксиса: '+n+': '+e.message)}}process.exit(bad?1:0)")
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(scripts, f, ensure_ascii=False)
            path = f.name
        try:
            res = subprocess.run([node, '-e', checker, path], capture_output=True, text=True)
        finally:
            os.unlink(path)
        if res.returncode != 0:
            raise AssertionError(res.stdout + res.stderr)

    def save(self, path):
        data = self.to_dict()
        self.validate(data)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f'{path}: {len(self.questions)} вопросов, {len(self.answer_lists)} списков ответов, '
              f'скрипты проверены')
        return data
