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

INK, MUTED, GREEN, COPPER, PAPER, BOX = '1F211C', '5E625A', '2F5B52', 'A26A35', 'FFFFFF', 'F3EEE4'
RULE = 'D6CFC2'
# Pisavi z metrično enakovrednima nadomestkoma (Carlito, Caladea), da sta prelom v Wordu in v PDF enaka.
BODY, HEAD = 'Calibri', 'Cambria'
LEFT_W = 64  # mm: stolpec s sestavinami

# Poglavja: najprej sladko (1–6), nato slano (7–12), na koncu Jules Cooking (13).
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
    (13, 'Jules Cooking'),
]
PARTS = {1: 'SLADKO', 7: 'SLANO', 13: 'FINE DINING'}

# Pregledne strani podpoglavij: kateri razdelki gredo v tisk.
OVERVIEWS = {
    '5.1': ('01-09-moussi.md', ['Kateri mousse za kaj', 'Kako razumeti različne postopke', 'Natančnost, ki odloča o rezultatu']),
    '9.1': ('04-04-maticne-in-izpeljane-omake.md', []),
    '10.2': ('05-04-pireji-in-kreme.md', ['Skupna pravila', 'Predstavitev']),
}

# Recepti z glavnim mestom drugje, ki jih je smiselno najti tudi v tem poglavju.
SEE_ALSO = {9: ['R0048'], 11: ['R0049', 'R0054', 'R0055', 'R0056', 'R0063', 'R0164']}

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
by_id = {r['id']: r for r in records}

order = {key: i for i, (key, _) in enumerate(CHAPTERS)}
missing = {int(r['num'].split('.')[0]) for r in records} - set(order)
assert not missing, f'Poglavja brez imena v CHAPTERS: {missing}'
for pos, r in enumerate(records):
    r['pos'] = pos
records.sort(key=lambda r: (order[int(r['num'].split('.')[0])], int(r['num'].split('.')[1]), r['pos']))

# Prikazne številke: zaporedna poglavja in podpoglavja.
recipe_chapters = {int(r['num'].split('.')[0]) for r in records}
active_chapters = [ch for ch, _ in CHAPTERS if ch in recipe_chapters or ch in SEE_ALSO]
chapter_no = {ch: number for number, ch in enumerate(active_chapters, 1)}
sub_no = {}
for r in records:
    ch = int(r['num'].split('.')[0])
    if r['num'] not in sub_no:
        sub_no[r['num']] = f"{chapter_no[ch]}.{sum(1 for k in sub_no if k.split('.')[0] == str(ch)) + 1}"

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
sec.top_margin, sec.bottom_margin = Mm(17), Mm(17)
sec.left_margin, sec.right_margin = Mm(18), Mm(18)
sec.header_distance, sec.footer_distance = Mm(8), Mm(8)
TEXT_W = 210 - 18 - 18

styles = doc.styles
normal = styles['Normal']
normal.font.name = BODY
normal.font.size = Pt(11)
normal.font.color.rgb = RGBColor.from_string(INK)
normal.paragraph_format.line_spacing = 1.2
normal.paragraph_format.space_after = Pt(4)

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

set_style('Title', HEAD, 40, '000000', False, False, 0, 12, True)
set_style('Heading 1', HEAD, 26, '000000', False, False, 0, 4, False)
set_style('Heading 2', HEAD, 14, GREEN, True, False, 16, 6, True)
set_style('Heading 3', HEAD, 16, '000000', True, False, 14, 2, True)
set_style('Eyebrow', BODY, 8.5, COPPER, True, None, 0, 2, True)
set_style('Lead', BODY, 10.5, MUTED, None, True, 0, 4, True)
set_style('Facts', BODY, 10, INK, None, None, 2, 6, True)
set_style('Section', BODY, 8.5, GREEN, True, None, 6, 2, False)
set_style('Component', BODY, 10.5, INK, True, None, 4, 1, False)
set_style('Ingredient', BODY, 10.5, INK, None, None, 0, 1.5)
set_style('Step', BODY, 11, INK, None, None, 0, 3.5)
set_style('Bullet', BODY, 10.5, INK, None, None, 0, 2)
set_style('Small', BODY, 9, MUTED, None, None, 0, 2)
set_style('Overview Item', BODY, 10.5, INK, None, None, 0, 3)

# Uporabnikova izjema: 7.3 je kratek priročnik, štiri kartice na stran.
# Sestavine ostanejo urejevalno besedilo v strnjenem odstavku.
set_style('Compact Title', HEAD, 16, '000000', False, False, 7, 3, True)
styles['Compact Title'].base_style = styles['Heading 3']
compact_outline = OxmlElement('w:outlineLvl'); compact_outline.set(qn('w:val'), '2')
styles['Compact Title'].element.get_or_add_pPr().append(compact_outline)
set_style('Compact Facts', BODY, 10.5, COPPER, False, False, 0, 3, True)
set_style('Compact Body', BODY, 12, INK, False, False, 0, 3, True)
set_style('Compact Method', BODY, 12, INK, False, False, 0, 6, False)
for name in ('Compact Body', 'Compact Method', 'Compact Facts', 'Compact Title'):
    styles[name].paragraph_format.line_spacing = 1.05
    styles[name].paragraph_format.keep_together = True

ING_QTY, ING_NAME = 18, 20  # mm: desni rob količine in začetek imena
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
styles['Small'].paragraph_format.line_spacing = 1.1
styles['Facts'].paragraph_format.line_spacing = 1.2
styles['Ingredient'].paragraph_format.line_spacing = 1.1
styles['Bullet'].paragraph_format.line_spacing = 1.15
styles['Lead'].paragraph_format.line_spacing = 1.15

for name, size, indent, bold in (('TOC 1', 10.5, 0, True), ('TOC 2', 9.5, 3, True), ('TOC 3', 9.5, 6, False)):
    s = set_style(name, BODY, size, GREEN if name == 'TOC 2' else INK, bold)
    s.paragraph_format.left_indent = Mm(indent)
    s.paragraph_format.space_before = Pt(7 if name == 'TOC 1' else (3 if name == 'TOC 2' else 0))
    s.paragraph_format.space_after = Pt(0.5)
    s.paragraph_format.line_spacing = 1.05

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

# Bela podlaga za največji kontrast; samodejno deljenje besed v ozkih stolpcih.
hyph = OxmlElement('w:autoHyphenation'); hyph.set(qn('w:val'), 'true'); doc.settings.element.append(hyph)
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

CUR = None        # celica tabele, v katero se trenutno piše; None = telo dokumenta
CUR_FRESH = False
def use(cell):
    global CUR, CUR_FRESH
    CUR, CUR_FRESH = cell, cell is not None

def add_p(style=None):
    global CUR_FRESH
    if CUR is None:
        return doc.add_paragraph(style=style)
    if CUR_FRESH:
        CUR_FRESH = False
        p = CUR.paragraphs[0]
        if style:
            p.style = style
        return p
    return CUR.add_paragraph(style=style)

def rule(p):
    ppr = p._p.get_or_add_pPr()
    bdr = OxmlElement('w:pBdr'); top = OxmlElement('w:top')
    top.set(qn('w:val'), 'single'); top.set(qn('w:sz'), '6'); top.set(qn('w:color'), RULE); top.set(qn('w:space'), '8')
    bdr.append(top); ppr.append(bdr)

def cell_props(cell, width_mm, fill=None, left=0, right=0, top=60, bottom=60):
    cell.width = Mm(width_mm)
    tcPr = cell._tc.get_or_add_tcPr()
    if fill:  # vrstni red po shemi: tcW, shd, tcMar
        shd = OxmlElement('w:shd'); shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), fill)
        tcPr.append(shd)
    mar = OxmlElement('w:tcMar')
    for side, val in (('top', top), ('left', left), ('bottom', bottom), ('right', right)):
        e = OxmlElement(f'w:{side}'); e.set(qn('w:w'), str(val)); e.set(qn('w:type'), 'dxa'); mar.append(e)
    tcPr.append(mar)

def two_columns():
    """Nevidna postavitvena tabela. Zgornja vrstica (čez oba stolpca) nosi naslov, opis in
    podatke, spodnja ima levo sestavine in desno postopek. Naslov je v isti tabeli, ker
    LibreOffice odstavek »ohrani z naslednjim« pred tabelo drži skupaj s celo tabelo."""
    t = doc.add_table(rows=2, cols=2)
    t.autofit = False
    tw = t._tbl.tblPr.find(qn('w:tblW'))
    tw.set(qn('w:w'), str(int(TEXT_W * 56.7))); tw.set(qn('w:type'), 'dxa')
    for col, wmm in zip(t.columns, (LEFT_W, TEXT_W - LEFT_W)):
        col.width = Mm(wmm)
    head = t.cell(0, 0).merge(t.cell(0, 1))
    trPr = t.rows[0]._tr.get_or_add_trPr(); trPr.append(OxmlElement('w:cantSplit'))
    hm = OxmlElement('w:tcMar')
    for side, val in (('top', 0), ('left', 0), ('bottom', 60), ('right', 0)):
        e = OxmlElement(f'w:{side}'); e.set(qn('w:w'), str(val)); e.set(qn('w:type'), 'dxa'); hm.append(e)
    head._tc.get_or_add_tcPr().append(hm)
    left, right = t.rows[1].cells
    cell_props(left, LEFT_W, BOX, left=120, right=140, top=90, bottom=90)
    cell_props(right, TEXT_W - LEFT_W, None, left=260, right=0, top=40, bottom=40)
    return head, left, right

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
    p = add_p(style)
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
    p = add_p('Ingredient')
    long_amount = len(re.sub(r'\*', '', amount)) > 10
    if amount and not long_amount:
        p.add_run('\t'); r = p.add_run(amount); r.bold = True; p.add_run('\t')
        inline(p, name)
    else:
        p.add_run('\t\t'); inline(p, name)
        if amount:
            inline(p, ' ' + amount, bold=True)
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
                p = add_p('Overview Item')
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
                para(h, 'Component').paragraph_format.keep_with_next = CUR is None
            n = 0; continue
        text = clean_text(strip_ids(val))
        if not text:
            continue
        if kind == 'step':
            n += 1
            p = add_p(step_style)
            r = p.add_run(f'{n}.'); r.bold = True; r.font.color.rgb = RGBColor.from_string(GREEN)
            p.add_run('\t'); inline(p, text)
            dump.append(f'{n}. {text}')
        elif kind == 'bullet':
            lead_in = re.match(r'^\*\*([^*]+)\*\*', val)
            if lead_in and not text.startswith('**'):
                continue  # uvodna oznaka je bila opomba, ostanek nima smisla
            p = add_p('Bullet')
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
    # V celicah tabele LibreOffice ob »ohrani z naslednjim« ne razdeli vrstice; zunaj tabel naslov drži z vsebino.
    p.paragraph_format.keep_with_next = CUR is None
    return p

# --- Naslovnica ------------------------------------------------------------
n_ch = len(chapter_no)
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
p.style = styles['Title']; p.runs[0].font.size = Pt(30)

def set_columns(section, num, space_mm=8):
    sp = section._sectPr
    for old in sp.findall(qn('w:cols')):
        sp.remove(old)
    cols = OxmlElement('w:cols'); cols.set(qn('w:num'), str(num)); cols.set(qn('w:space'), str(int(space_mm * 56.7)))
    sp.append(cols)

def drop_restart(section):
    for e in section._sectPr.findall(qn('w:pgNumType')):
        section._sectPr.remove(e)

toc_sec = doc.add_section(WD_SECTION_START.CONTINUOUS); drop_restart(toc_sec); set_columns(toc_sec, 2)
p = doc.add_paragraph()
# Razširjeno polje TOC: Word in LibreOffice ga prepoznata kot kazalo in ga lahko osvežita.
for kind, val in (('begin', None), ('instr', ' TOC \\o "1-3" \\h \\z \\u '), ('separate', None),
                  ('text', 'Kazalo se izpolni ob osvežitvi polj.'), ('end', None)):
    r = OxmlElement('w:r')
    if kind == 'instr':
        it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = val; r.append(it)
    elif kind == 'text':
        tx = OxmlElement('w:t'); tx.text = val; r.append(tx)
    else:
        fc = OxmlElement('w:fldChar'); fc.set(qn('w:fldCharType'), kind); r.append(fc)
    p._p.append(r)
body_sec = doc.add_section(WD_SECTION_START.NEW_PAGE); drop_restart(body_sec); set_columns(body_sec, 1)

# --- Recepti ---------------------------------------------------------------
group = defaultdict(list)
for r in records:
    group[r['num']].append(r)
chapter_names = dict(CHAPTERS)


def chapter_heading(ch):
    if ch in PARTS:
        p = para(PARTS[ch], 'Eyebrow')
        p.paragraph_format.page_break_before = True
    p = doc.add_paragraph(f'{chapter_no[ch]}  {chapter_names[ch]}', 'Heading 1')
    p.paragraph_format.page_break_before = ch not in PARTS
    bookmark(p, f'CH{chapter_no[ch]}')
    dump.append(f'\n\n######## {chapter_no[ch]} {chapter_names[ch]}')


def cross_references(ch, standalone=False):
    references = SEE_ALSO[ch]
    if not standalone:
        p = doc.add_paragraph('Glej tudi: ', style='Small')
    for k, rid in enumerate(references):
        if standalone:
            p = doc.add_paragraph()
        elif k:
            p.add_run(', ')
        recipe = by_id[rid]
        link(p, recipe['title'], recipe['file'])
        other = int(recipe['num'].split('.')[0])
        p.add_run(f' ({chapter_names[other]})')
    dump.append('Glej tudi: ' + ', '.join(titles[rid] for rid in references))


for ch in SEE_ALSO.keys() - recipe_chapters:
    group[f'{ch}.0'] = []

last_ch = None
manifest = []
for subnum in sorted(group, key=lambda number: (order[int(number.split('.')[0])], int(number.split('.')[1]))):
    items = group[subnum]
    ch = int(subnum.split('.')[0])
    if not items:
        chapter_heading(ch)
        cross_references(ch, standalone=True)
        continue
    disp_sub = sub_no[subnum]
    if ch != last_ch:
        chapter_heading(ch)
        if ch in SEE_ALSO:
            cross_references(ch)
        last_ch = ch
    h2_text = f'{disp_sub}  {items[0]["sub"]}'
    dump.append(f'\n==== {disp_sub} {items[0]["sub"]}')
    overview = subnum in OVERVIEWS
    h2_done = False
    if overview or subnum == '7.3':
        add_p('Heading 2').add_run(h2_text); h2_done = True
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
        if subnum == '7.3' and r['meta'].get('postavitev') == 'strnjeno':
            if idx == 1:
                p = para('Moka, jajca, mleko, maslo, smetana, olje, kis, sladkor, sol, poper, kvas, pecilni prašek in voda.', 'Small')
                p.paragraph_format.space_after = Pt(7)
            elif (idx - 1) % 4 == 0:
                p = para(f'{disp_sub}  RECEPTI IZ OSNOVNEGA SORTIMENTA', 'Eyebrow')
                p.paragraph_format.page_break_before = True
            p = doc.add_paragraph(r['title'], 'Compact Title'); bookmark(p, r['id'])
            # Izrecni slog v TOC ohrani vsako kratko kartico v kazalu.
            for name, bl in sections(blocks(r['body'])):
                if name == 'Vir in licenca':
                    continue  # Pripis se ohrani v skupnem razdelku Viri.
                for kind, val in bl:
                    if kind != 'p':
                        raise ValueError(f'Strnjena kartica zahteva odstavke: {r["id"]}')
                    text = clean_text(strip_ids(val))
                    if not text:
                        continue
                    style = 'Compact Facts' if name is None and not val.startswith('**Razmerje') else ('Compact Method' if name == 'Postopek' else 'Compact Body')
                    p = doc.add_paragraph(style=style); inline(p, text)
                    dump.append(text.replace('**', ''))
            manifest.append({'id': r['id'], 'title': r['title'], 'number': disp_sub, 'source': r['file']})
            continue
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
        printable = []
        for name, bl in secs[1:]:
            name = clean_heading(name)
            target = SECTION_MAP.get(name, name)
            if target and target.startswith('Kritičn'):
                target = 'Nasveti'
            elif target and target.startswith('Variant'):
                target = 'Variante'
            if target is None or not has_content(bl):
                continue
            printable.append((name, target, bl))
        ingr = [x for x in printable if x[0].startswith('Sestavine')]
        rest = [x for x in printable if not x[0].startswith('Sestavine')]
        as_table = bool(ingr and rest)
        if as_table:
            head, left, right = two_columns()
            use(head)
        if not h2_done:
            add_p('Heading 2').add_run(h2_text); h2_done = True
        p = add_p('Heading 3'); p.add_run(r['title']); bookmark(p, r['id'])
        if idx > 1 or overview:
            rule(p)
        else:
            p.paragraph_format.space_before = Pt(4)
        last = p
        if lead:
            last = para(lead[0], 'Lead')
        if facts or ratio:
            p = add_p('Facts'); shade(p); last = p
            first = True
            for t in facts + [x for x in ratio if x]:
                if not first:
                    p.add_run().add_break()
                inline(p, t); first = False
                dump.append('[' + t.replace('**', '') + ']')
        if as_table:
            last.paragraph_format.keep_with_next = False
        render(extra)
        if as_table:
            use(left)
            for name, target, bl in ingr:
                section_title(target); render(bl)
            use(right)
            for name, target, bl in rest:
                section_title(target); render(bl)
            use(None)
            # Ločilni odstavek: brez njega se zaporedni tabeli zlijeta v eno.
            sep = doc.add_paragraph(); pf = sep.paragraph_format
            pf.space_before = pf.space_after = Pt(0); pf.line_spacing = Pt(2)
            sep.add_run().font.size = Pt(2)
        else:
            for name, target, bl in printable:
                section_title(target); render(bl)
        manifest.append({'id': r['id'], 'title': r['title'], 'number': disp_sub, 'source': r['file']})

# --- Viri ------------------------------------------------------------------
src_sec = doc.add_section(WD_SECTION_START.NEW_PAGE); drop_restart(src_sec); set_columns(src_sec, 1)
p = doc.add_paragraph('Viri', 'Heading 1'); bookmark(p, 'VIRI')
cols_sec = doc.add_section(WD_SECTION_START.CONTINUOUS); drop_restart(cols_sec); set_columns(cols_sec, 2, 7)
dump.append('\n\n######## Viri')
for subnum, items in group.items():
    for r in items:
        p = doc.add_paragraph(style='Small'); p.paragraph_format.space_after = Pt(3)
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
            inline(p, lic, size=8.5)
        dump.append(f"{r['title']} · {izvor} · {vir}" + (' · ' + r['license'] if r['license'] else ''))

OUT.parent.mkdir(exist_ok=True)
DUMP.parent.mkdir(exist_ok=True)
doc.save(OUT)
DUMP.write_text('\n'.join(dump), encoding='utf-8')
(ROOT / 'work/knjiga-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Ustvarjeno: {OUT.name}; {len(records)} receptov, {n_ch} poglavij; besedilo za pregled: work/{DUMP.name}')
