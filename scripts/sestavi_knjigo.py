"""Sestavi berljivo knjigo DOCX iz registra receptov.

Izvorne datoteke Markdown ostanejo nespremenjene. Za tisk skripta odstrani
uredniške opombe, oznake virov, »za dopolnitev« in trajne ID ter vire zbere
v kratek seznam na koncu. Kazalo, številke strani in PDF ustvari Word prek
scripts/osvezi-knjigo.ps1.
"""
from pathlib import Path
from collections import defaultdict
from datetime import date
import re, json

from docx import Document
from docx.shared import Mm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_BREAK
from docx.enum.section import WD_SECTION_START
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/moj-kuharski-zvezek.docx'
DUMP = ROOT / 'work/knjiga-besedilo.txt'

INK, MUTED, GREEN, COPPER, PAPER, BOX = '23261F', '676B62', '2F5B52', 'A26A35', 'FBF8F2', 'F1EBDF'

# Poglavja: najprej sladko (1–6), nato slano (7–12), na koncu Julius fine dining (13).
# Številke so enake v registru in v knjigi. Vrstni red receptov znotraj
# podpoglavja je vrstni red vrstic v registru.
CHAPTERS = [
    (1, 'Kreme in polnila'),
    (2, 'Testa'),
    (3, 'Biskviti'),
    (4, 'Meringe in hrustljavi dodatki'),
    (5, 'Moussi'),
    (6, 'Sladice in pecivo'),
    (7, 'Kuharske osnove'),
    (8, 'Okisovanje'),
    (9, 'Omake'),
    (10, 'Priloge'),
    (11, 'Glavne jedi'),
    (12, 'Tuja kulinarika'),
    (13, 'Julius fine dining'),
]
PARTS = {1: 'SLADKO', 7: 'SLANO', 13: 'FINE DINING'}

# Pregledne strani podpoglavij: kateri razdelki gredo v tisk.
OVERVIEWS = {
    '5.1': ('01-09-moussi.md', ['Kateri mousse za kaj', 'Kako razumeti različne postopke', 'Natančnost, ki odloča o rezultatu']),
    '9.1': ('04-04-maticne-in-izpeljane-omake.md', []),
    '10.2': ('05-04-pireji-in-kreme.md', ['Skupna pravila', 'Predstavitev']),
}

# Recepti z glavnim mestom drugje, ki jih je smiselno najti tudi v tem poglavju.
SEE_ALSO = {9: ['R0048'], 11: ['R0049', 'R0054', 'R0055', 'R0056']}

# Razdelki receptov: preimenovanje za tisk ali izpust (None).
SECTION_MAP = {
    'Posebna oprema': None, 'Vir in licenca': None, 'Zapiski z vaj': None,
    'Sladkor v testu: tradicija in priporočilo': None, 'Natančnost mer': None, 'Natančnost': None,
    'Kritične točke in triki': 'Nasveti', 'Kritične točke': 'Nasveti', 'Kritična točka': 'Nasveti',
    'Kritične točke — uredniška razlaga': 'Nasveti',
    'Serviranje in povezani recepti': 'Serviranje in povezave', 'Povezani recepti': 'Povezani recepti',
    'Variante iz videa': 'Variante', 'Varianta iz videa': 'Variante',
    'Razmerje iz videa Fallow o razmerjih': 'Razmerje',
}

# Ciljni popravki besedila za tisk, kjer splošna pravila ne zadoščajo.
PRINT_FIX = [
    ('Čebula, v prikazu sladka čebula Roscoff', 'Čebula, po možnosti sladka (Roscoff)'),
    ('Voda | približno 100 ml za avtorjevo nedoločeno količino omake', 'Voda | približno 100 ml'),
    ('Avtorjeva spletna stran dopušča zamrzovanje kreme', 'Kremo lahko zamrzneš'),
    ('Avtor jo v posodi, primerni za mikrovalovno pečico, segreje 20 sekund pri polovični moči.',
     'Lahko jo segreješ 20 sekund v mikrovalovni pečici pri polovični moči.'),
    ('Avtor uporabi približno 20 % smetane.', 'Izhodišče je približno 20 % smetane.'),
    ('Opis navaja trak širine 1 cm za eklerje.', 'Za eklerje brizgaj trak širine 1 cm.'),
    ('V videu avtor predlaga približno 5 minut v hladilniku in nato ponovno stepanje.',
     'Daj jo za približno 5 minut v hladilnik in ponovno stepi.'),
    ('Sirup prilivaj previdno; spletni nasvet predpisuje nizko hitrost zaradi škropljenja.',
     'Sirup prilivaj previdno in pri nizki hitrosti, da ne škropi.'),
    ('Dodatek knjige navaja **12–24 ur**; velikost in debelina kosov nista navedeni.',
     'Traja **12–24 ur**, odvisno od velikosti in debeline.'),
    ('Po viru več sladkorja da tršo meringo. Razmerje sladkor : beljaki je **1,5–2 : 1**.',
     'Več sladkorja da tršo meringo.'),
    ('Avtor omeni tudi dodatek gorčice za omako k piščančjim prsim.',
     'Za omako k piščančjim prsim vmešaj malo gorčice.'),
    ('Avtor omeni prečiščeno maslo, sam pa zagovarja uporabo vsega stopljenega masla z mlečnimi delci zaradi okusa.',
     'Namesto prečiščenega masla lahko uporabiš vse stopljeno maslo z mlečnimi delci, ki da več okusa.'),
    ('V videu: ob rombu (turbot) s slanino in kapljicami olja.', 'Postrezi ob rombu (turbot) s slanino in kapljicami olja.'),
]

# Popravki že očiščenega besedila: v tisku ni tabel, zato ni vrstic in stolpcev.
POST_FIX = [
    (r'\ben stolpec\b', 'eno različico'), (r'\beno vrstico\b', 'eno različico'),
    (r'\bvsako vrstico\b', 'vsako različico'), (r'\bizbrane vrstice\b', 'izbrane različice'),
    (r'\bizbrani vrstici\b', 'izbrani različici'), (r'\bizbrano vrstico\b', 'izbrano različico'),
]

# Šibke oznake: del stavka brez številk s takšno besedo ne sodi v tisk.
META = re.compile(
    r'za dopolnitev|za preverbo|uredniš|Uredniš|izvirn|Izvirn|preizkuš|King Arthur|pretvorben|licenc|Licenc|'
    r'podnapis|opis videa|evidenc|registr|\bvir\b|\bVir\b|\bvira\b|\bviru\b|\bvirom\b|\bviri\b|\bviroma\b|'
    r'ni podan|niso podan|ni naveden|ni navedena|ni določen|ni del te|niso del te|nista vključeni|'
    r'v prikazu|V prikazu|prikazan|v videu|V videu|videa|avtor|Avtor|samodejn|govorjen|uporabnik|Uporabnik|'
    r'Učni viri|[Pp]odlaga:|ni izmišljen|ne ocenjuj|sledljiv|trajni ID|glavno mesto|ni podatek|ni izdelan|'
    r'nista določen|ni določen|Recept ne vključuje|niso zagotovila|Pred vajo preveri|učna količina|'
    r'ni predstavljena|ločeno vajo|potrditev|ohranjen\w*|vrstic|Pregled:|Prilagoditev temelji|FDA|nepopoln|'
    r'Byatt pravi|nista navedeni|knjig|ni izmerjen|praktično preverjen|Zapis vaje', re.I)
# Močne oznake: kar jih po čiščenju še vsebuje, ne gre v tisk, tudi s številkami.
STRONG = re.compile(
    r'avtor|Avtor|izvirn|Izvirn|uredniš|Uredniš|\bvir\b|\bVir\b|\bviru\b|\bvira\b|\bvirom\b|za dopolnitev|'
    r'za preverbo|preizkuš|[Vv] videu|[Vv] prikazu|prikazan|evidenc|licenc|podnapis|ni podatek|pretvorben|'
    r'\b[Vv]ide[oa]\b|\bvideu\b|dodan[ao]? \d|dopisan|[Ss]klic|Opis navaja|prikaza|knjig|v tem zapisu|'
    r'spletni nasvet|Pregled:|v pregledu|glavno mesto', re.I)
# Rešljive oblike: pretvori v navodilo, preden se oceni, ali je del stavka opomba.
SALVAGE = [
    (r'\s*\((?:Fallow|Byatt)(?:, [^)]*)?\)', ''),
    (r'\s*\((?:izvirno|v videu|po viru|vir|iz videa)[^)]*\)', ''),
    (r'\(opis: ', '('),
    (r',\s*v opisu najmanj ', ', lahko tudi '),
    (r'\bPo opisu\s+', ''),
    (r'\*\*([^*]+?) po viru:\*\*', r'**\1:**'),
    (r'\b[Vv] videu (?:je (?:\w+ )?)?postrežen\w*,? ', 'Postrezi '),
    (r'^V (?:videu|prikazu) so ', 'Primer: '),
    (r'^(?:V prikazu |V videu )?(?:je )?[Aa]vtor (?:izrecno |tudi |pa )?(?:poudari|opozori|svetuje|priporoča|pravi|zagovarja|predlaga)(?:,)? da ', ''),
    (r'^Avtor (?:pri prikazani količini )?omeni ', ''),
    (r'^Uredniška dopolnitev:\s*|^Uredniško:\s*', ''),
    (r'\*\*(Izplen|Količina|Priprava|Počivanje) po viru:\*\*', r'**\1:**'),
]
# Čiščenje delov stavkov, ki ostanejo zaradi številk.
TRIM = [
    (r'\s*\((?:izvirno|v videu|po viru|vir)[^)]*\)', ''),
    (r',?\s*kot (?:določa|navaja|predpisuje) (?:izvirnik|vir)', ''),
    (r'\b[Vv]ir (?:predpisuje|določa|uporablja|zapiše|podaja|navaja)\s+', ''),
    (r'(?:,\s*)?(?:po viru|navaja vir|v viru)\b\s*', ' '),
    (r'^(?:V prikazu|V videu),? (?:avtor )?(?:omeni |navaja |pokaže )?', ''),
    (r'\b[Vv] (?:videu|prikazu)\s+', ''),
    (r'\s*[—-]\s*uredniš\w+ [^.;]*$', ''),
]

def has_digits(s):
    s = re.sub(r'\]\([^)]*\)', ']', s)  # številke v ciljih povezav ne štejejo
    return bool(re.search(r'\d', s))

def cap(s):
    m = re.match(r'^(\W*)(\w)', s)
    return s if not m else s[:m.end(1)] + m.group(2).upper() + s[m.end():]

def clean_sentence(s):
    for pat, rep in SALVAGE:
        s = re.sub(pat, rep, s)
    kept = []
    for n, c in enumerate(re.split(r';\s+', s.strip())):
        if META.search(c) and not has_digits(c.replace('**', '')):
            if n == 0:
                return ''  # brez glavnega dela stavka ostanek nima smisla
            continue
        for pat, rep in TRIM:
            c = re.sub(pat, rep, c)
        c = re.sub(r'\s{2,}', ' ', c).strip(' ,')
        if not c or STRONG.search(c):
            if n == 0:
                return ''
            continue
        kept.append(c)
    if not kept:
        return ''
    out = '; '.join(kept).strip()
    if re.fullmatch(r'\*\*[^*]+:\*\*\.?', out):  # ostala je samo oznaka, npr. »Izplen:«
        return ''
    if s.rstrip().endswith('.') and not out.endswith(('.', '!', '?', ':')):
        out += '.'
    return cap(out)

SENT_SPLIT = re.compile(r'(?:(?<=[.!?])|(?<=[.!?]\*\*))\s+(?=[A-ZČŠŽÀ-Ý*\[(»])')

def clean_text(text):
    if not text:
        return ''
    sentences = [clean_sentence(x) for x in SENT_SPLIT.split(text.strip())]
    out = ' '.join(x for x in sentences if x).strip()
    for pat, rep in POST_FIX:
        out = re.sub(pat, rep, out)
    return out

# --- Branje registra -------------------------------------------------------
records = []
for line in (ROOT / 'recepti/REGISTER.md').read_text(encoding='utf-8').splitlines():
    if not re.match(r'\| \[R\d{4}\]', line):
        continue
    cells = [c.strip() for c in line.strip('|').split('|')]
    rid, filename = re.match(r'\[(R\d+)\]\(([^)]+)\)', cells[0]).groups()
    num, sub = cells[2].split(' ', 1)
    source = (ROOT / 'recepti' / filename).read_text(encoding='utf-8')
    _, rawmeta, body = source.split('---', 2)
    meta = {}
    for item in rawmeta.strip().splitlines():
        k, v = item.split(':', 1)
        meta[k] = v.strip().strip('"')
    title = re.search(r'^# (.+)$', body, flags=re.M).group(1).strip()
    body = re.sub(r'^\s*# [^\n]+\n', '', body, count=1).strip()
    body = re.split(r'^## Uredniška evidenca\s*$', body, maxsplit=1, flags=re.M)[0].strip()
    lic = re.search(r'^## Vir in licenca\s*\n(.+?)(?=^## |\Z)', body, flags=re.M | re.S)
    for a, b in PRINT_FIX:
        body = body.replace(a, b)
    records.append(dict(id=rid, file=filename, title=title, num=num, sub=sub, meta=meta, body=body,
                        license=lic.group(1).strip() if lic else ''))
assert records and 'R0046' not in {r['id'] for r in records}
titles = {r['id']: r['title'] for r in records}
files = {r['file']: r['id'] for r in records}

order = {key: i for i, (key, _) in enumerate(CHAPTERS)}
missing = {int(r['num'].split('.')[0]) for r in records} - set(order)
assert not missing, f'Poglavja brez imena v CHAPTERS: {missing}'
for pos, r in enumerate(records):
    r['pos'] = pos
records.sort(key=lambda r: (order[int(r['num'].split('.')[0])], int(r['num'].split('.')[1]), r['pos']))

# Prikazne številke: zaporedna poglavja in podpoglavja.
display = {}
chapter_no, sub_no = {}, {}
for r in records:
    ch = int(r['num'].split('.')[0])
    if ch not in chapter_no:
        chapter_no[ch] = len(chapter_no) + 1
    if r['num'] not in sub_no:
        sub_no[r['num']] = f"{chapter_no[ch]}.{sum(1 for k in sub_no if k.split('.')[0] == str(ch)) + 1}"
    display[r['id']] = sub_no[r['num']]

def strip_ids(text):
    """Odstrani trajne ID iz besedila; povezave dobijo naslov recepta."""
    def link_label(m):
        label, target = m.group(1), m.group(2)
        rid = files.get(Path(target.split('#')[0]).name)
        label = re.sub(r'^R\d{4}\s*', '', label).strip()
        if not label and rid:
            label = titles[rid]
        if not rid and not re.match(r'https?://', target):
            return label  # povezava na pregled, register ali evidenco: samo besedilo
        return f'[{label}]({target})'
    text = re.sub(r'\[([^\]]*)\]\(([^)]+)\)', link_label, text)
    parts = re.split(r'(\[[^\]]*\]\([^)]+\))', text)  # ID zamenjaj samo zunaj povezav
    for i in range(0, len(parts), 2):
        s = re.sub(r',\s*R\d{4}\b', '', parts[i])
        s = re.sub(r'\s*\(R\d{4}\)', '', s)
        parts[i] = re.sub(r'\bR\d{4}\b', lambda m: titles.get(m.group(0), ''), s)
    return ''.join(parts)

# --- Dokument in slogi -----------------------------------------------------
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Mm(210), Mm(297)
sec.top_margin, sec.bottom_margin = Mm(20), Mm(20)
sec.left_margin, sec.right_margin = Mm(22), Mm(20)
sec.header_distance, sec.footer_distance = Mm(8), Mm(10)
TEXT_W = 210 - 22 - 20

styles = doc.styles
normal = styles['Normal']
normal.font.name = 'Aptos'
normal.font.size = Pt(12)
normal.font.color.rgb = RGBColor.from_string(INK)
normal.paragraph_format.line_spacing = 1.25
normal.paragraph_format.space_after = Pt(6)

def set_style(name, font=None, size=None, color=None, bold=None, italic=None, before=None, after=None, keep=None, base=True):
    if name not in styles:
        s = styles.add_style(name, 1)
        if base:
            s.base_style = normal
    s = styles[name]
    if font: s.font.name = font
    if size: s.font.size = Pt(size)
    if color: s.font.color.rgb = RGBColor.from_string(color)
    if bold is not None: s.font.bold = bold
    if italic is not None: s.font.italic = italic
    if before is not None: s.paragraph_format.space_before = Pt(before)
    if after is not None: s.paragraph_format.space_after = Pt(after)
    if keep is not None: s.paragraph_format.keep_with_next = keep
    return s

set_style('Title', 'Georgia', 46, '000000', False, False, 0, 14, True)
set_style('Heading 1', 'Georgia', 34, '000000', False, False, 0, 6, True)
set_style('Heading 2', 'Georgia', 17, GREEN, False, False, 6, 18, True)
set_style('Heading 3', 'Georgia', 26, '000000', False, False, 0, 6, True)
set_style('Eyebrow', 'Aptos', 9.5, COPPER, True, None, 0, 3, True)
set_style('Lead', 'Aptos', 12, MUTED, None, True, 0, 10)
set_style('Facts', 'Aptos', 11.5, INK, None, None, 2, 14)
set_style('Section', 'Aptos', 10.5, GREEN, True, None, 14, 6, True)
set_style('Component', 'Aptos', 12, INK, True, None, 8, 3, True)
set_style('Ingredient', 'Aptos', 12, INK, None, None, 0, 3)
set_style('Step', 'Aptos', 12, INK, None, None, 0, 7)
set_style('Bullet', 'Aptos', 12, INK, None, None, 0, 5)
set_style('Small', 'Aptos', 10, MUTED, None, None, 0, 3)
set_style('Overview Item', 'Aptos', 12, INK, None, None, 0, 7)

ING_QTY, ING_NAME = 30, 35  # mm: desni rob količine in začetek imena
for s in ('Ingredient',):
    pf = styles[s].paragraph_format
    pf.left_indent, pf.first_line_indent = Mm(ING_NAME), Mm(-ING_NAME)
    pf.tab_stops.add_tab_stop(Mm(ING_QTY), WD_TAB_ALIGNMENT.RIGHT)
    pf.tab_stops.add_tab_stop(Mm(ING_NAME))
    pf.keep_together = True
for s, ind in (('Step', 8), ('Bullet', 5)):
    pf = styles[s].paragraph_format
    pf.left_indent, pf.first_line_indent = Mm(ind), Mm(-ind)
    pf.tab_stops.add_tab_stop(Mm(ind))
styles['Small'].paragraph_format.line_spacing = 1.15
styles['Facts'].paragraph_format.line_spacing = 1.3

for name, size, indent, bold in (('TOC 1', 12.5, 0, True), ('TOC 2', 11, 5, False), ('TOC 3', 11, 10, False)):
    s = set_style(name, 'Aptos', size, GREEN if name == 'TOC 2' else INK, bold)
    s.paragraph_format.left_indent = Mm(indent)
    s.paragraph_format.space_before = Pt(9 if name == 'TOC 1' else 0)
    s.paragraph_format.space_after = Pt(2)
    s.paragraph_format.line_spacing = 1.1

# Brez tematskih pisav in okrasnih obrob iz privzete predloge.
for s in styles:
    if not hasattr(s, 'font'):
        continue
    for border in list(s.element.xpath('./w:pPr/w:pBdr')):
        border.getparent().remove(border)
    rpr = s.element.get_or_add_rPr()
    fonts = rpr.find(qn('w:rFonts'))
    if fonts is not None:
        for attr in list(fonts.attrib):
            if 'Theme' in attr:
                del fonts.attrib[attr]
    if s.font.name:
        if fonts is None:
            fonts = OxmlElement('w:rFonts'); rpr.insert(0, fonts)
        for attr in ['ascii', 'hAnsi', 'eastAsia', 'cs']:
            fonts.set(qn('w:' + attr), s.font.name)
styles['Footer'].paragraph_format.tab_stops.clear_all()

# Razmik črk za majhne naslove razdelkov.
for name in ('Section', 'Eyebrow'):
    sp = OxmlElement('w:spacing'); sp.set(qn('w:val'), '14')
    styles[name].element.get_or_add_rPr().append(sp)

bg = OxmlElement('w:background'); bg.set(qn('w:color'), PAPER); doc._element.insert(0, bg)
doc.settings.element.append(OxmlElement('w:displayBackgroundShape'))
upd = OxmlElement('w:updateFields'); upd.set(qn('w:val'), 'true'); doc.settings.element.append(upd)
lang = OxmlElement('w:lang'); lang.set(qn('w:val'), 'sl-SI'); normal.element.get_or_add_rPr().append(lang)
doc.core_properties.title = 'Moj kuharski zvezek'
doc.core_properties.subject = 'Osebna kuharska knjiga za pripravo na MasterChef'
doc.core_properties.author = 'Jaka'

def shade(p, fill=BOX, border=COPPER):
    ppr = p._p.get_or_add_pPr()
    shd = OxmlElement('w:shd'); shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), fill)
    bdr = OxmlElement('w:pBdr')
    for side in ('top', 'left', 'bottom', 'right'):
        e = OxmlElement(f'w:{side}')
        if side == 'left':
            e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), '18'); e.set(qn('w:color'), border); e.set(qn('w:space'), '8')
        else:
            e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), '4'); e.set(qn('w:color'), fill); e.set(qn('w:space'), '5')
        bdr.append(e)
    ppr.append(bdr); ppr.append(shd)

bid = 0
def bookmark(p, name):
    global bid
    bid += 1
    start = OxmlElement('w:bookmarkStart'); start.set(qn('w:id'), str(bid)); start.set(qn('w:name'), name)
    end = OxmlElement('w:bookmarkEnd'); end.set(qn('w:id'), str(bid))
    p._p.insert(0, start); p._p.append(end)

dump = []
def link(p, label, target, color=GREEN):
    h = OxmlElement('w:hyperlink')
    if re.match(r'https?://', target):
        h.set(qn('r:id'), p.part.relate_to(target, RT.HYPERLINK, is_external=True))
    else:
        rid = files.get(Path(target.split('#')[0]).name)
        if not rid:
            p.add_run(label); return
        h.set(qn('w:anchor'), rid)
    r = OxmlElement('w:r'); pr = OxmlElement('w:rPr'); co = OxmlElement('w:color'); co.set(qn('w:val'), color); pr.append(co)
    r.append(pr); t = OxmlElement('w:t'); t.text = label; t.set(qn('xml:space'), 'preserve'); r.append(t); h.append(r); p._p.append(h)

TOKENS = re.compile(r'(\[[^\]]+\]\([^)\s]+\)|\*\*.+?\*\*|`[^`]+`|(?<![\*\w])\*[^*\n]+\*(?!\*))')
def inline(p, text, bold=False, color=None, size=None):
    for token in TOKENS.split(text):
        if not token:
            continue
        m = re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)', token)
        if m:
            link(p, m[1], m[2]); continue
        plain = token[2:-2] if token.startswith('**') else token.strip('`') if token.startswith('`') else token[1:-1] if token.startswith('*') and token.endswith('*') and len(token) > 1 else token
        r = p.add_run(plain)
        if bold or token.startswith('**'): r.bold = True
        if token.startswith('*') and not token.startswith('**') and len(token) > 1: r.italic = True
        if color: r.font.color.rgb = RGBColor.from_string(color)
        if size: r.font.size = Pt(size)

def para(text, style=None, **kw):
    p = doc.add_paragraph(style=style)
    inline(p, text, **kw)
    dump.append(re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text).replace('**', ''))
    return p

# --- Markdown v bloke ------------------------------------------------------
def blocks(text):
    """Razbij Markdown na (vrsta, vsebina) bloke."""
    lines = text.splitlines(); i = 0; out = []
    while i < len(lines):
        line = lines[i].strip(); i += 1
        if not line or line in ('---', '***'):
            continue
        if line.startswith('|'):
            rows = []
            while True:
                cells = [x.strip() for x in line.strip('|').split('|')]
                if not all(re.match(r'^:?-+:?$', c.replace(' ', '')) for c in cells):
                    rows.append(cells)
                if i >= len(lines) or not lines[i].strip().startswith('|'):
                    break
                line = lines[i].strip(); i += 1
            out.append(('table', rows)); continue
        m = re.match(r'^(#{2,6}) (.+)$', line)
        if m:
            out.append(('h2' if len(m.group(1)) == 2 else 'h3', m.group(2).strip())); continue
        if line.startswith('# '):
            continue
        if line.startswith('- '):
            out.append(('bullet', line[2:])); continue
        if re.match(r'^\d+\. ', line):
            out.append(('step', re.sub(r'^\d+\.\s+', '', line))); continue
        while i < len(lines) and lines[i].strip() and not re.match(r'^(#{1,6} |\||- |\d+\. )', lines[i].strip()):
            line += ' ' + lines[i].strip(); i += 1
        out.append(('p', line))
    return out

def sections(bl):
    """Razdeli bloke po razdelkih ## ; prvi razdelek je uvod (None)."""
    out = [[None, []]]
    for kind, val in bl:
        if kind == 'h2':
            out.append([val, []])
        else:
            out[-1][1].append((kind, val))
    return out

def clean_heading(h):
    if h.startswith('Uredniška prilagoditev'):
        return 'Varnost'
    h = re.sub(r'\s*\((?:uredniš|izvirn)[^)]*\)', '', h)
    h = re.sub(r'\s*[—-]\s*(?:uredniš|iz drugega vira).*$', '', h)
    return h.strip()

def trim_label(s):
    """Odstrani oznake virov iz imen in količin sestavin."""
    s = re.sub(r'\s*\((?:v videu|v prikazu|po viru|izvirno|iz videa)[^)]*\)', '', s)
    s = re.sub(r',\s*\b(?:v videu|v prikazu|po viru)\b\s*', ', ', s)
    s = re.sub(r'\s*\b(?:v videu|v prikazu|po viru)\b\s*', ' ', s)
    s = re.sub(r'\s*za prikazano količino osnove', '', s)
    s = re.sub(r'^(\d+),?\s+(približno .+)$', r'\1 (\2)', s)
    return re.sub(r'\s{2,}', ' ', s).strip(' ,')

UNITS = [(r'(?:merilne )?jedilne žlice', 'žlice'), (r'(?:merilna )?jedilna žlica', 'žlica'),
         (r'čajni žlički', 'žlički'), (r'čajna(?= do)', 'žlička'),
         (r'(?:merilne )?čajne žličke', 'žličke'), (r'(?:merilna )?čajna žlička', 'žlička'),
         (r'(?:merilnih )?čajnih žličk', 'žličk'), (r'(?:merilnih )?jedilnih žlic', 'žlic')]

def short_units(s):
    for a, b in UNITS:
        s = re.sub(a, b, s)
    return s

def clean_qty(q):
    q = short_units(trim_label(q.strip()))
    if q in ('—', '-'):
        return None, ''
    amount, sep, note = q.partition(';')
    amount = amount.strip()
    if META.search(amount) and not has_digits(amount):
        amount = ''
    amount = re.sub(r'\s*(?:natančn\w+ )?(?:masa|količina|vrsta)(?: in količina)? za dopolnitev', '', amount).strip(' ,;')
    return amount, clean_text(strip_ids(note.strip())) if sep else ''

def ingredient(name, qty):
    amount, note = clean_qty(qty)
    if amount is None:
        return
    name = trim_label(strip_ids(name))
    name = clean_text(name).rstrip('.') or name
    p = doc.add_paragraph(style='Ingredient')
    long_amount = len(re.sub(r'\*', '', amount)) > 16
    if amount and not long_amount:
        p.add_run('\t'); r = p.add_run(amount); r.bold = True; p.add_run('\t')
        inline(p, name)
    else:
        p.add_run('\t\t'); inline(p, name)
        if amount:
            inline(p, '  ' + amount, color=MUTED)
    if note:
        raw_note = qty.partition(';')[2].strip()
        if raw_note[:1].islower():
            note = note[0].lower() + note[1:]
        inline(p, '  ' + note.rstrip('.'), color=MUTED, size=10.5)
    dump.append(f'  {amount:>14} | {name}' + (f'  ({note})' if note else ''))

def table(rows):
    headers = rows[0]; cols = len(headers)
    h0 = headers[0].lower()
    if cols == 2 and h0 == 'sestavina':
        for name, qty in rows[1:]:
            ingredient(name, qty)
    elif cols > 2 and h0 == 'sestavina':
        for col in range(1, cols):
            para(clean_text(headers[col]), 'Component')
            for row in rows[1:]:
                ingredient(row[0], row[col])
    else:
        for row in rows[1:]:
            if h0.startswith('različica') or (h0 == 'pire' and any('želatina' in h.lower() for h in headers[1:])):
                para(strip_ids(row[0]), 'Component')
                for label, value in zip(headers[1:], row[1:]):
                    ingredient(label, value)
            else:
                # Pregledna vrstica: ime krepko, opis v isti alineji.
                p = doc.add_paragraph(style='Overview Item')
                inline(p, strip_ids(row[0]), bold=True)
                rest = ' · '.join(clean_text(strip_ids(v)) for v in row[1:] if clean_text(strip_ids(v)))
                if rest:
                    p.add_run().add_break()
                    inline(p, rest, color=MUTED, size=11)
                dump.append('  ' + strip_ids(row[0]) + ' — ' + rest)

def render(bl, step_style='Step'):
    n = 0
    for kind, val in bl:
        if kind == 'table':
            table(val); continue
        if kind == 'h3':
            h = clean_heading(clean_text(val) or val)
            if h:
                para(h, 'Component')
            n = 0; continue
        text = clean_text(strip_ids(val))
        if not text:
            continue
        if kind == 'step':
            n += 1
            p = doc.add_paragraph(style=step_style)
            r = p.add_run(f'{n}.'); r.bold = True; r.font.color.rgb = RGBColor.from_string(GREEN)
            p.add_run('\t'); inline(p, text)
            dump.append(f'{n}. {text}')
        elif kind == 'bullet':
            lead_in = re.match(r'^\*\*([^*]+)\*\*', val)
            if lead_in and not text.startswith('**'):
                continue  # uvodna oznaka je bila opomba, ostanek nima smisla
            p = doc.add_paragraph(style='Bullet')
            r = p.add_run('•'); r.font.color.rgb = RGBColor.from_string(GREEN)
            p.add_run('\t'); inline(p, text)
            dump.append('• ' + text)
        else:
            para(text)

def has_content(bl):
    for kind, val in bl:
        if kind == 'table':
            return True
        if kind == 'h3':
            continue
        text = clean_text(strip_ids(val))
        if kind == 'bullet' and re.match(r'^\*\*', val) and not text.startswith('**'):
            continue  # alineja brez uvodne oznake se ne izpiše
        if text:
            return True
    return False

def section_title(name):
    p = para(name.upper(), 'Section')
    return p

# --- Naslovnica ------------------------------------------------------------
n_ch = len({int(r['num'].split('.')[0]) for r in records})
p = para('OSEBNA KUHARSKA KNJIGA', 'Eyebrow'); p.paragraph_format.space_before = Mm(55)
p = doc.add_paragraph('Moj kuharski\nzvezek', 'Title')
para('Osnove, tehnike in recepti za kuharsko vajo', 'Lead')
p = para(f'{len(records)} receptov  ·  {n_ch} poglavij', 'Small'); p.paragraph_format.space_before = Mm(70)
mesci = ['januar', 'februar', 'marec', 'april', 'maj', 'junij', 'julij', 'avgust', 'september', 'oktober', 'november', 'december']
d = date.today()
para(f'{d.day}. {mesci[d.month - 1]} {d.year}', 'Small')

# --- Kazalo ----------------------------------------------------------------
sec = doc.add_section(WD_SECTION_START.NEW_PAGE)
sec.footer.is_linked_to_previous = False
pg = OxmlElement('w:pgNumType'); pg.set(qn('w:start'), '1'); sec._sectPr.append(pg)
foot = sec.footer.paragraphs[0]
foot.paragraph_format.tab_stops.clear_all()
foot.paragraph_format.tab_stops.add_tab_stop(Mm(TEXT_W), WD_TAB_ALIGNMENT.RIGHT)
rr = foot.add_run('Moj kuharski zvezek'); rr.font.size = Pt(8.5); rr.font.color.rgb = RGBColor.from_string(MUTED)
foot.add_run('\t')
fld = OxmlElement('w:fldSimple'); fld.set(qn('w:instr'), 'PAGE')
fr = OxmlElement('w:r'); frp = OxmlElement('w:rPr'); fsz = OxmlElement('w:sz'); fsz.set(qn('w:val'), '19'); frp.append(fsz); fr.append(frp)
ft = OxmlElement('w:t'); ft.text = '1'; fr.append(ft); fld.append(fr); foot._p.append(fld)
p = doc.add_paragraph('Kazalo', 'Heading 1')
p.style = styles['Title']; p.runs[0].font.size = Pt(34)
p = doc.add_paragraph()
field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'TOC \\o "1-3" \\h \\z \\u'); p._p.append(field)

# --- Recepti ---------------------------------------------------------------
group = defaultdict(list)
for r in records:
    group[r['num']].append(r)
chapter_names = dict(CHAPTERS)
last_ch = None
manifest = []
for subnum, items in group.items():
    ch = int(subnum.split('.')[0])
    disp_sub = sub_no[subnum]
    if ch != last_ch:
        if ch in PARTS:
            p = para(PARTS[ch], 'Eyebrow'); p.paragraph_format.page_break_before = True
            p = doc.add_paragraph(f'{chapter_no[ch]}  {chapter_names[ch]}', 'Heading 1')
        else:
            p = doc.add_paragraph(f'{chapter_no[ch]}  {chapter_names[ch]}', 'Heading 1')
            p.paragraph_format.page_break_before = True
        bookmark(p, f'CH{chapter_no[ch]}'); last_ch = ch
        dump.append(f'\n\n######## {chapter_no[ch]} {chapter_names[ch]}')
        if ch in SEE_ALSO:
            p = doc.add_paragraph(style='Small')
            p.add_run('Glej tudi: ')
            for k, rid in enumerate(SEE_ALSO[ch]):
                if k: p.add_run(', ')
                link(p, titles[rid], next(r['file'] for r in records if r['id'] == rid))
                other = int(next(r['num'] for r in records if r['id'] == rid).split('.')[0])
                p.add_run(f' ({chapter_names[other]})')
            dump.append('Glej tudi: ' + ', '.join(titles[x] for x in SEE_ALSO[ch]))
        p = doc.add_paragraph(f'{disp_sub}  {items[0]["sub"]}', 'Heading 2')
    else:
        p = doc.add_paragraph(f'{disp_sub}  {items[0]["sub"]}', 'Heading 2')
        p.paragraph_format.page_break_before = True
    dump.append(f'\n==== {disp_sub} {items[0]["sub"]}')
    overview = subnum in OVERVIEWS
    if overview:
        fname, keep = OVERVIEWS[subnum]
        src = (ROOT / 'recepti' / fname).read_text(encoding='utf-8')
        src = re.split(r'^## Uredniška evidenca', src, flags=re.M)[0]
        for name, bl in sections(blocks(src)):
            if name is None or name in keep:
                if name and has_content(bl):
                    section_title(name)
                render(bl, 'Step')
    for idx, r in enumerate(items, 1):
        dump.append(f'\n---- {r["title"]}  [{r["id"]}]')
        if idx > 1 or overview:
            eyebrow = para(f'{disp_sub}  ·  {r["sub"].upper()}', 'Eyebrow')
            eyebrow.paragraph_format.page_break_before = True
        p = doc.add_paragraph(r['title'], 'Heading 3'); bookmark(p, r['id'])
        secs = sections(blocks(r['body']))
        # Uvod: opis in ključni podatki.
        intro = secs[0][1]
        facts, ratio, lead, extra = [], [], [], []
        for kind, val in intro:
            if kind != 'p':
                extra.append((kind, val)); continue
            if val.startswith('**Razmerje po masi'):
                ratio.append(clean_text(strip_ids(val)))
            elif val.startswith('**'):
                t = clean_text(strip_ids(val))
                if t: facts.append(t)
            elif not lead:
                t = clean_text(strip_ids(val))
                if t: lead.append(t)
            else:
                extra.append((kind, val))
        if lead:
            para(lead[0], 'Lead')
        if facts or ratio:
            p = doc.add_paragraph(style='Facts'); shade(p)
            first = True
            for t in facts + [x for x in ratio if x]:
                if not first:
                    p.add_run().add_break()
                inline(p, t); first = False
                dump.append('[' + t.replace('**', '') + ']')
        render(extra)
        for name, bl in secs[1:]:
            name = clean_heading(name)
            target = SECTION_MAP.get(name, name)
            if target and target.startswith('Kritičn'):
                target = 'Nasveti'
            elif target and target.startswith('Variant'):
                target = 'Variante'
            if target is None or not has_content(bl):
                continue
            section_title(target)
            render(bl)
        manifest.append({'id': r['id'], 'title': r['title'], 'number': disp_sub, 'source': r['file']})

# --- Viri ------------------------------------------------------------------
p = doc.add_paragraph('Viri', 'Heading 1'); p.paragraph_format.page_break_before = True; bookmark(p, 'VIRI')
dump.append('\n\n######## Viri')
for subnum, items in group.items():
    for r in items:
        p = doc.add_paragraph(style='Small'); p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.keep_together = True
        inline(p, r['title'], bold=True, color=INK)
        izvor = strip_ids(r['meta'].get('izvor', '').strip())
        izvor = re.sub(r'\s*\((?:\s*)\)', '', izvor)
        if izvor:
            inline(p, '  ·  ' + izvor)
        vir = r['meta'].get('vir', '')
        if re.match(r'https?://', vir):
            p.add_run('  ·  '); link(p, 'povezava', vir)
        if r['license']:
            lic = re.sub(r'\s+', ' ', strip_ids(r['license']))
            lic = re.sub(r'\s*(?:Licenčni )?[Pp]ripis ohrani tudi v končni knjigi\.', '', lic).strip()
            p.add_run().add_break()
            inline(p, lic, size=9.5)
        dump.append(f"{r['title']} · {izvor} · {vir}" + (' · ' + r['license'] if r['license'] else ''))

OUT.parent.mkdir(exist_ok=True)
DUMP.parent.mkdir(exist_ok=True)
doc.save(OUT)
DUMP.write_text('\n'.join(dump), encoding='utf-8')
(ROOT / 'work/knjiga-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Ustvarjeno: {OUT.name}; {len(records)} receptov, {n_ch} poglavij; besedilo za pregled: work/{DUMP.name}')
