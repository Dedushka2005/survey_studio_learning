"""Скачивает базу знаний SURVEYSTUDIO (kb.surveystudio.ru) в текстовые .md файлы.

Запуск: python3 tools/fetch_kb.py [папка]  (по умолчанию ./kb)
"""
import re, sys, os, urllib.request, html
from html.parser import HTMLParser
SITEMAP='https://kb.surveystudio.ru/sitemap.xml'
urls=re.findall(r'<loc>([^<]+)</loc>', urllib.request.urlopen(SITEMAP,timeout=30).read().decode())
urls=[u for u in urls if '/tags' not in u and '/page/' not in u and not u.endswith('/archive')]
out=sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(__file__),'..','kb')
os.makedirs(out,exist_ok=True)
BLOCK={'p','div','li','tr','h1','h2','h3','h4','h5','h6','pre','br','table','ul','ol','blockquote','dt','dd'}
class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.depth=0; s.inmain=False; s.buf=[]; s.pre=0; s.skip=0; s.title=''; s.intitle=False
    def handle_starttag(s,t,a):
        a=dict(a)
        if t=='title': s.intitle=True
        cls=a.get('class') or ''
        if not s.inmain and t=='div' and 'theme-doc-markdown' in cls or (not s.inmain and t=='article'):
            s.inmain=True; s.depth=0
        if not s.inmain: return
        if t=='div' or t=='article': s.depth+=1
        if t in ('button','svg'): s.skip+=1
        if t=='pre': s.pre+=1; s.buf.append('\n```\n')
        if t in ('h1','h2','h3','h4'): s.buf.append('\n\n'+'#'*int(t[1])+' ')
        elif t=='li': s.buf.append('\n- ')
        elif t in ('td','th'): s.buf.append(' | ')
        elif t in BLOCK: s.buf.append('\n')
        if t=='code' and not s.pre: s.buf.append('`')
        if t=='img' and a.get('alt'): s.buf.append('[img: %s]'%a['alt'])
    def handle_endtag(s,t):
        if t=='title': s.intitle=False
        if not s.inmain: return
        if t in ('button','svg'): s.skip=max(0,s.skip-1)
        if t=='code' and not s.pre: s.buf.append('`')
        if t=='pre': s.pre-=1; s.buf.append('\n```\n')
        if t in BLOCK: s.buf.append('\n')
        if t=='div' or t=='article':
            s.depth-=1
            if s.depth<=0: s.inmain=False
    def handle_data(s,d):
        if s.intitle: s.title+=d
        if s.inmain and not s.skip:
            s.buf.append(d if s.pre else re.sub(r'\s+',' ',d))
for u in urls:
    name=u.replace('https://kb.surveystudio.ru/','').strip('/').replace('/','_') or 'index'
    try:
        h=urllib.request.urlopen(u,timeout=30).read().decode('utf-8','replace')
    except Exception as e:
        print('ERR',u,e); continue
    p=P(); p.feed(h)
    txt=''.join(p.buf); txt=re.sub(r'[ \t]+\n','\n',txt); txt=re.sub(r'\n{3,}','\n\n',txt)
    txt=re.sub(r'```\n(.*?)\n```',lambda m:'```\n'+re.sub(r'\n\s*\n','\n',m.group(1).strip('\n'))+'\n```',txt,flags=re.S)
    open(os.path.join(out,name+'.md'),'w').write('<!-- source: %s -->\n# %s\n%s\n'%(u,p.title.strip(),txt.strip()))
    print(name,len(txt))

