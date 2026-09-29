"""Шаблон новой анкеты. Скопируйте папку: surveys/_template -> surveys/<проект>.

Запуск:  python3 surveys/<проект>/build.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from ss_builder import Questionnaire, screen_if, refuse_if, OTHER_TXT, BLOCKING  # noqa: E402

qnr = Questionnaire('Новая анкета')
q, alist = qnr.q, qnr.alist

# --- Скринер -----------------------------------------------------------------
q(1, 'SingleChoice', 'Согласны ли вы принять участие в опросе?', name='S0',
  AnswerList=alist('Да/Нет', {1: 'Да', 2: 'Нет'}),
  after=refuse_if([2]))

q(2, 'Numeric', 'Сколько вам полных лет?', name='S1', AnswerNumberFrom=0, AnswerNumberTo=120,
  after='if (Q.openValueInt < 18) return screenOut();')

# --- Основная часть ----------------------------------------------------------
q(10, 'MultipleChoice', 'Какими брендами вы пользуетесь?', name='Q1',
  comment='Выберите все подходящие варианты',
  AnswerList=alist('Бренды', {1: 'Бренд 1', 2: 'Бренд 2', 96: 'Другое (укажите)', 99: 'Никакими'},
                   {96: OTHER_TXT, 99: BLOCKING}),
  flags={'RandomizeAnswers': True})

# Функции этой анкеты (общие функции из tools/ss_lib.js добавляются автоматически)
qnr.global_functions = ''
# Скрипт «Подготовка» (циклы, порядок вопросов)
qnr.preprocessing = ''

qnr.save(os.path.join(HERE, 'survey.json'))
