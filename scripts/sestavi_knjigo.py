"""Sestavi urejevalni DOCX iz registra; izris in osvežitev polj opravi Word."""
from pathlib import Path
import re, json
from collections import defaultdict
from docx import Document
from docx.shared import Mm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.section import WD_SECTION_START
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/moj-kuharski-zvezek-2026-11-09.docx'
INK, GREEN, COPPER, PAPER, LINE = '252822', '2F5B52', 'A26A35', 'F7F3EB', 'DEDAD1'
chapters = {1:'Slaščičarske osnove',2:'Sladice',3:'Slane kuharske osnove',4:'Fondi juhe in omake',5:'Zelenjava gobe in priloge',7:'Ribe in morski sadeži',8:'Meso perutnina in divjačina'}
records = []
for line in (ROOT/'recepti/REGISTER.md').read_text(encoding='utf-8').splitlines():
    if not re.match(r'\| \[R\d{4}\]', line): continue
    cells = [c.strip() for c in line.strip('|').split('|')]
    rid, filename = re.match(r'\[(R\d+)\]\(([^)]+)\)', cells[0]).groups()
    num, sub = cells[2].split(' ', 1)
    source = (ROOT/'recepti'/filename).read_text(encoding='utf-8')
    _, rawmeta, body = source.split('---',2)
    meta = {}
    for item in rawmeta.strip().splitlines():
        k,v = item.split(':',1); meta[k] = v.strip().strip('"')
    body = re.sub(r'^\s*# [^\n]+\n', '', body, count=1).strip()
    parts = re.split(r'^## Uredniška evidenca\s*$', body, maxsplit=1, flags=re.M)
    records.append(dict(id=rid,file=filename,title=cells[1],num=num,sub=sub,meta=meta,body=parts[0].strip(),notes=parts[1].strip() if len(parts)>1 else ''))
assert len(records)==47
records.sort(key=lambda r: (*map(int,r['num'].split('.')),int(r['id'][1:])))
bookmarks = {r['file']:r['id'] for r in records}
bookmarks.update({'01-09-moussi.md':'SUB1_9','05-04-pireji-in-kreme.md':'SUB5_4','04-04-maticne-in-izpeljane-omake.md':'SUB4_4','02-06-drobno-pecivo.md':'SUB2_6','01-slascicarske-osnove.md':'CH1','REGISTER.md':'KAZALO'})

doc = Document()
sec = doc.sections[0]
sec.page_width,sec.page_height = Mm(210),Mm(297)
sec.top_margin,sec.bottom_margin = Mm(19),Mm(19)
sec.left_margin,sec.right_margin = Mm(22),Mm(19)
sec.header_distance,sec.footer_distance = Mm(8),Mm(9)
styles=doc.styles
normal=styles['Normal']; normal.font.name='Aptos'; normal.font.size=Pt(10.5); normal.font.color.rgb=RGBColor.from_string(INK)
normal.paragraph_format.line_spacing=1.10; normal.paragraph_format.space_after=Pt(4)
for name, font, size, color in [('Title','Georgia',43,'000000'),('Subtitle','Aptos',15,GREEN),('Heading 1','Georgia',31,'000000'),('Heading 2','Georgia',18,'000000'),('Heading 3','Georgia',25,'000000')]:
    s=styles[name]; s.font.name=font; s.font.size=Pt(size); s.font.color.rgb=RGBColor.from_string(color)
    s.paragraph_format.space_before=Pt(10 if name!='Title' else 0); s.paragraph_format.space_after=Pt(10)
    s.paragraph_format.keep_with_next=True
for name,size,color in [('Eyebrow',8.5,COPPER),('Recipe Section',11,GREEN),('Recipe Subsection',10.5,INK),('Source Note',9.5,'676B63'),('Source Heading',12,GREEN),('Book Bullet',10.5,INK),('Book Step',10.5,INK)]:
    s=styles.add_style(name,1); s.base_style=normal; s.font.size=Pt(size); s.font.color.rgb=RGBColor.from_string(color)
    if name in ['Recipe Section','Recipe Subsection','Source Heading','Eyebrow']:
        s.font.bold=True; s.paragraph_format.keep_with_next=True
    if name in ['Recipe Section','Source Heading']: s.paragraph_format.space_before=Pt(11)
styles['Book Bullet'].paragraph_format.left_indent=Mm(3)
styles['Book Bullet'].paragraph_format.first_line_indent=Mm(-3)
styles['Book Step'].paragraph_format.left_indent=Mm(5)
styles['Book Step'].paragraph_format.first_line_indent=Mm(-5)
for name in ['TOC 1','TOC 2','TOC 3']:
    if name not in styles: styles.add_style(name,1)
    s=styles[name]; s.base_style=normal; s.font.name='Aptos'; s.font.size=Pt(10 if name=='TOC 3' else 11)
    s.font.color.rgb=RGBColor.from_string(INK)
    s.paragraph_format.space_after=Pt(3 if name=='TOC 3' else 6)
    s.paragraph_format.left_indent=Mm({'TOC 1':0,'TOC 2':4,'TOC 3':9}[name])
    if name=='TOC 1': s.font.bold=True; s.paragraph_format.space_before=Pt(8)

# Odstrani tematske pisave in okrasne obrobe v Wordovi privzeti predlogi.
for s in styles:
    if not hasattr(s,'font'): continue
    for border in list(s.element.xpath('./w:pPr/w:pBdr')): border.getparent().remove(border)
    rpr=s.element.get_or_add_rPr()
    fonts=rpr.find(qn('w:rFonts'))
    if fonts is not None:
        for attr in list(fonts.attrib):
            if 'Theme' in attr: del fonts.attrib[attr]
    if s.font.name:
        if fonts is None: fonts=OxmlElement('w:rFonts'); rpr.insert(0,fonts)
        for attr in ['ascii','hAnsi','eastAsia','cs']: fonts.set(qn('w:'+attr),s.font.name)
styles['Footer'].paragraph_format.tab_stops.clear_all()

bg=OxmlElement('w:background'); bg.set(qn('w:color'),PAPER); doc._element.insert(0,bg)
display=OxmlElement('w:displayBackgroundShape'); doc.settings.element.append(display)
upd=OxmlElement('w:updateFields'); upd.set(qn('w:val'),'true'); doc.settings.element.append(upd)
lang=OxmlElement('w:lang'); lang.set(qn('w:val'),'sl-SI'); normal.element.get_or_add_rPr().append(lang)
doc.core_properties.title='Moj kuharski zvezek'
doc.core_properties.subject='Osebna kuharska knjiga za pripravo na MasterChef'
doc.core_properties.author='Jaka'
doc.core_properties.keywords='kuharska knjiga, recepti, MasterChef'
bid=0
def bookmark(p,name):
    global bid
    bid+=1
    start=OxmlElement('w:bookmarkStart'); start.set(qn('w:id'),str(bid)); start.set(qn('w:name'),name)
    end=OxmlElement('w:bookmarkEnd'); end.set(qn('w:id'),str(bid))
    p._p.insert(0,start); p._p.append(end)

current=''
def link(p,label,target):
    h=OxmlElement('w:hyperlink')
    if re.match(r'https?://',target): h.set(qn('r:id'),p.part.relate_to(target,RT.HYPERLINK,is_external=True))
    else:
        anchor=bookmarks.get(Path(target.split('#')[0]).name,'OP_'+current if current else 'VIRI')
        h.set(qn('w:anchor'),anchor)
    r=OxmlElement('w:r'); pr=OxmlElement('w:rPr'); co=OxmlElement('w:color'); co.set(qn('w:val'),GREEN); pr.append(co); r.append(pr)
    t=OxmlElement('w:t'); t.text=label; r.append(t); h.append(r); p._p.append(h)

def inline(p,text):
    pattern=r'(\[[^\]]+\]\([^\n]*?\)(?=[\s.,;:!?]|$)|\*\*.+?\*\*|`[^`]+`|(?<!\*)\*[^*]+\*)'
    for token in re.split(pattern,text):
        if not token: continue
        m=re.fullmatch(r'\[([^\]]+)\]\((.*)\)',token)
        if m: link(p,m[1],m[2]); continue
        r=p.add_run(token.strip('*`') if token.startswith(('**','`','*')) else token)
        if token.startswith('**'): r.bold=True
        elif token.startswith('*'): r.italic=True

def para(text,style=None):
    p=doc.add_paragraph(style=style); inline(p,text); return p

def table(rows,small=False):
    cols=len(rows[0]); t=doc.add_table(rows=0,cols=cols); t.autofit=False
    widths=([109,60] if cols==2 else [72]+[(169-72)/(cols-1)]*(cols-1))
    for col,width in zip(t.columns,widths): col.width=Mm(width)
    pr=t._tbl.tblPr
    borders=OxmlElement('w:tblBorders')
    for edge in ['top','left','bottom','right','insideH','insideV']:
        e=OxmlElement('w:'+edge); e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'4'); e.set(qn('w:color'),LINE); borders.append(e)
    pr.append(borders)
    margins=OxmlElement('w:tblCellMar')
    for name,value in [('top','65'),('bottom','65'),('left','100'),('right','100')]:
        e=OxmlElement('w:'+name); e.set(qn('w:w'),value); e.set(qn('w:type'),'dxa'); margins.append(e)
    pr.append(margins)
    for rowidx,data in enumerate(rows):
        row=t.add_row(); trpr=row._tr.get_or_add_trPr(); cant=OxmlElement('w:cantSplit'); trpr.append(cant)
        if rowidx==0: repeat=OxmlElement('w:tblHeader'); trpr.append(repeat)
        for i,cell in enumerate(row.cells):
            cell.width=Mm(widths[i]); cell.vertical_alignment=1
            sh=OxmlElement('w:shd'); sh.set(qn('w:fill'),GREEN if rowidx==0 else ('FFFFFF' if rowidx%2 else 'F1F0E9')); cell._tc.get_or_add_tcPr().append(sh)
            p=cell.paragraphs[0]; p.paragraph_format.space_after=Pt(0); p.paragraph_format.space_before=Pt(0); p.paragraph_format.line_spacing=1.05
            if i>0 and cols==2: p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
            inline(p,data[i] if i<len(data) else '')
            for r in p.runs:
                r.font.size=Pt(9.5 if cols>2 else 10)
                if rowidx==0: r.bold=True; r.font.color.rgb=RGBColor(255,255,255)
    doc.add_paragraph().paragraph_format.space_after=Pt(0)

def markdown(text,notes=False):
    lines=text.splitlines(); i=0; license_section=False
    while i<len(lines):
        line=lines[i].strip(); i+=1
        if not line: continue
        if line.startswith('|'):
            rows=[]
            while True:
                cells=[x.strip() for x in line.strip('|').split('|')]
                if not all(re.match(r'^:?-+:?$',c.replace(' ','')) for c in cells): rows.append(cells)
                if i>=len(lines) or not lines[i].strip().startswith('|'): break
                line=lines[i].strip(); i+=1
            if rows: table(rows,notes)
            continue
        if re.match(r'^#{2,6} ',line):
            level=len(line.split(' ')[0]); heading=line[level+1:]; license_section=heading=='Vir in licenca'
            if license_section: continue
            para(heading, 'Source Heading' if notes else ('Recipe Section' if level==2 else 'Recipe Subsection')); continue
        if line.startswith('# '): continue
        if line in ['---','***']: continue
        if line.startswith('- '): para('• '+line[2:],'Source Note' if notes else 'Book Bullet'); continue
        if re.match(r'^\d+\. ',line): para(line,'Source Note' if notes else 'Book Step'); continue
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#{1,6} |\||- |\d+\. )',lines[i].strip()):
            line+=' '+lines[i].strip(); i+=1
        p=para(('**Vir in licenca.** '+line) if license_section else line,'Source Note' if notes or license_section else None)
        if license_section: p.paragraph_format.keep_together=True

# Naslovnica.
p=para('OSEBNA ZBIRKA ZA PRIPRAVO NA MASTERCHEF','Eyebrow'); p.paragraph_format.space_before=Mm(38)
p=doc.add_paragraph('Moj kuharski\nzvezek','Title'); p.paragraph_format.space_after=Mm(9)
para('Osnove, tehnike in recepti za kuharsko vajo','Subtitle')
p=para('Zbirka za ponavljanje kuharskih postopkov, primerjavo receptur in beleženje izkušenj v domači kuhinji.'); p.paragraph_format.space_before=Mm(13); p.paragraph_format.right_indent=Mm(20)
p=para('47 RECEPTOV  ·  7 POGLAVIJ','Eyebrow'); p.paragraph_format.space_before=Mm(38)
para('Prva pregledna izdaja\n9. november 2026','Source Note')

# Nov odsek: številčenje se začne s kazalom, naslovnica brez noge.
sec=doc.add_section(WD_SECTION_START.NEW_PAGE)
sec.footer.is_linked_to_previous=False
pg=OxmlElement('w:pgNumType'); pg.set(qn('w:start'),'1'); sec._sectPr.append(pg)
foot=sec.footer.paragraphs[0]; foot.paragraph_format.tab_stops.clear_all(); foot.paragraph_format.tab_stops.add_tab_stop(Mm(169),WD_ALIGN_PARAGRAPH.RIGHT)
rr=foot.add_run('MOJ KUHARSKI ZVEZEK'); rr.font.size=Pt(8); rr.font.color.rgb=RGBColor.from_string('74776F')
foot.add_run('\t')
fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); foot._p.append(fld)
p=doc.add_paragraph('Kazalo','Title'); p.runs[0].font.size=Pt(31); bookmark(p,'KAZALO')
para('Poglavja, osnove in posamezni recepti','Source Note')
p=doc.add_paragraph()
field=OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'TOC \\o "1-3" \\h \\z \\u'); p._p.append(field)

p=para('Kako uporabljati knjigo','Recipe Section'); p.paragraph_format.page_break_before=True
para('Pri receptih so zbrani trenutno znani podatki. Oznaka »za dopolnitev« pomeni, da izvirni vir ne poda vseh količin ali pogojev priprave. Recepture še niso praktično preizkušene; ob vaji beleži uporabljene sestavine, dejanske čase in rezultat.')
para('Kazalo vodi do vsakega recepta. Oznake R0001–R0047 ostajajo trajne, prikazne številke poglavij in receptov pa sledijo sedanji razvrstitvi. Povezave med recepti so klikljive.')
para('Osnovne kreme, fondi, omake in pireji imajo vsak svoje mesto. Sestavljene jedi se nanje sklicujejo. Francoska maslena krema je samostojna osnova; pri makronih je povezava do nje.')
para('Viri in uredniške opombe so zbrani na koncu knjige. Licenčni pripisi odprto objavljenih receptur so ohranjeni tudi ob receptih.')
para('Sladko in slano','Recipe Section')
para('Najprej so slaščičarske osnove in sladice, nato slane osnove, fondi in omake, zelenjavne priloge ter ribje in mesne jedi. Prikazana so samo poglavja, ki že vsebujejo recepte.')

group=defaultdict(list)
for r in records: group[r['num']].append(r)
overviews={'1.9':'01-09-moussi.md','4.4':'04-04-maticne-in-izpeljane-omake.md','5.4':'05-04-pireji-in-kreme.md'}
lastch=None
manifest=[]
for subnum,items in group.items():
    ch=int(subnum.split('.')[0]); current=''
    if ch!=lastch:
        p=doc.add_paragraph(f'{ch} {chapters[ch]}','Heading 1'); p.paragraph_format.page_break_before=True; bookmark(p,'CH'+str(ch)); lastch=ch
        p=doc.add_paragraph(f'{subnum} {items[0]["sub"]}','Heading 2')
    else:
        p=doc.add_paragraph(f'{subnum} {items[0]["sub"]}','Heading 2'); p.paragraph_format.page_break_before=True
    bookmark(p,'SUB'+subnum.replace('.','_'))
    overview=subnum in overviews
    if overview:
        source=(ROOT/'recepti'/overviews[subnum]).read_text(encoding='utf-8')
        source=re.split(r'^## Uredniška evidenca',source,flags=re.M)[0]
        # Izpusti načrtovalni del pregleda; konkretni sklici so v receptih.
        source=re.split(r'^## (Sklici iz drugih podpoglavij|Povezane osnove in meje sklopa)',source,flags=re.M)[0]
        markdown(source)
    for idx,r in enumerate(items,1):
        current=r['id']
        eyebrow=para(f'{subnum}.{idx}  ·  {r["sub"].upper()}  ·  {current}','Eyebrow')
        if idx>1 or overview: eyebrow.paragraph_format.page_break_before=True
        p=doc.add_paragraph(r['title'],'Heading 3'); bookmark(p,current)
        markdown(r['body'].replace('Licenčni pripis ohrani tudi v končni knjigi.','').replace('Pripis ohrani tudi v končni knjigi.',''))
        manifest.append({'id':current,'title':r['title'],'number':f'{subnum}.{idx}','source':r['file']})

current=''
p=doc.add_paragraph('Viri in uredniške opombe','Heading 1'); p.paragraph_format.page_break_before=True; bookmark(p,'VIRI')
para('Pripisi avtorjem, različice virov in odprta vprašanja so zbrani po trajnih oznakah receptov. Količine in postopki v glavnem delu knjige ostajajo povezani s konkretnim navedenim virom. Posamezne licence veljajo za označene recepture, ne samodejno za celotno zbirko.','Source Note')
for r in records:
    current=r['id']; p=para(f'{current}  {r["title"]}','Source Heading'); bookmark(p,'OP_'+current)
    para('Izvor: '+r['meta'].get('izvor',''),'Source Note')
    if r['meta'].get('vir'): p=doc.add_paragraph(style='Source Note'); link(p,'Odpri izvirni vir',r['meta']['vir'])
    markdown(r['notes'],notes=True)

OUT.parent.mkdir(exist_ok=True)
doc.save(OUT)
(ROOT/'work/knjiga-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Ustvarjeno: {OUT}; {len(records)} receptov; {len(doc.tables)} tabel.')
