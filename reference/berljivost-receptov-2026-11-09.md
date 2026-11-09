# Berljivost receptov — raziskava in nova postavitev, 9. 11. 2026

Uporabnik je ob sliki vaniljeve omake opozoril, da so tabele težko berljive, in naročil raziskati primernejši format ter ga uporabiti v knjigi. Ta odločitev nadomešča prejšnje pravilo o sestavini na levi in desno poravnani količini v široki tabeli.

## Pregledani viri

1. [University of Nevada, Reno Extension: Recipe Development / All About Recipes Part I](https://extension.unr.edu/publication.aspx?PubID=4643). Priporoča vsako sestavino v svoji vrstici, smiselno zaporedje in jasne podatke o delitvi sestavin. Pri količinah in načinu priprave opozarja, da premik besed lahko spremeni pomen. Uporabljeno za strukturo seznamov, ne za spreminjanje receptur.
2. [UK Government Communication Service: Accessibility standards, Clear print](https://www.communications.gov.uk/publication/accessibility-standards/), objavljeno 3. 9. 2025. Priporoča najmanj 12-točkovno glavno besedilo, levo poravnavo, jasne naslove, dobro razlikovanje od ozadja in zmerno uporabo poudarkov. To so splošne smernice za tisk, ne preskus konkretne kuharske knjige.
3. [Savour: Creating and editing recipes, Ingredients and quantities](https://savour.page/en/guide-edit-recipes). Kot primer uporabe v kuharskem orodju navaja eno sestavino na vrstico, količino na začetku in odebeljeno številko. To je priporočilo ponudnika izdelka, ne neodvisna primerjalna raziskava.
4. [British Dyslexia Association: Dyslexia Style Guide 2023](https://cdn.bdadyslexia.org.uk/uploads/documents/Advice/style-guide/BDA-Style-Guide-2023.pdf). Iskalni izvleček priporoča 12–14 pt, več prostora in odebelitev namesto dolgih ležečih poudarkov. Neposredni prenos PDF je bil zavrnjen (403), zato odločitev sloni predvsem na neposredno dostopnih virih 1 in 2.

Viri pregledani 9. 11. 2026. Zadetka Virginia Tech »How to Write a Recipe« nismo uporabili kot odločilni vir: neposredno odprta stran sporoča, da publikacija ni več na voljo, čeprav iskalni izvleček še kaže njeno starejšo vsebino.

## Kaj je ugotovitev in kaj oblikovna odločitev

Pregled ne potrjuje enega znanstveno dokazanega »najboljšega« formata za vse kuharje. Smernice pa podpirajo večjo pisavo, jasne razdelke, eno sestavino na vrstico in povezano informacijo o količini ter sestavini. Uporabnik je konkretno težavo pokazal pri širokem razmiku med imenom in količino. Iz tega smo izbrali spodnjo postavitev za njegovo zbirko.

- Vsaka sestavina je navaden urejevalni odstavek: **170 ml** — Mleko. Količina je odebeljena, ime stoji tik ob njej. Pomišljaj loči podatkovni oznaki in omogoča ohranitev izvornega imena brez samodejnega pregibanja.
- Glavno besedilo, sestavine in koraki so **12 pt**, levo poravnani, z razmikom vrstic **1,2** ter prostorom med sestavinami. Podrobni viri ostanejo manjši sekundarni tisk.
- Opomba za podpičjem v količini, npr. »masa za dopolnitev«, je v svoji vrstici neposredno pod sestavino; ostaja enako velika in povezana s sestavino pri prelomu strani.
- Odstranjene so mreže, barvne glave in izmenično senčenje vseh 63 izvornih tabel. Primerjalni pregledi so razdeljeni na kratke označene sklope. Matrike variant so preurejene po različicah z lastnimi seznami; vsaka izvorna količina ostane povezana s pravim okusom/čokolado.
- Pri treh stolpcih tuiles je vsak stolpec svoja različica znotraj istega recepta. Pri sadnih penah in treh čokoladah je vsaka vrstica svoja različica. Ni novih trajnih ID in ni podvajanja celotnih receptov.
- Pomišljaj, ki v matriki tuiles označuje odsotno sestavino, ne postane nova sestavina v seznamu. Ta vrstica je iz seznama ustrezne različice izpuščena; npr. kakava ni med sestavinami osnovnih tuiles.
- Samo v izvozu je »izberi stolpec/vrstico« nadomeščeno z »izberi različico«, ker v izdaji ni več tabel. Izvorni Markdown recepti ostanejo nespremenjeni.
- Naslovi, krem podlaga, temno zeleni in bakreni poudarki ostajajo v dogovorjenem slogu. Nadnaslovne kategorije niso več v celoti zapisane z velikimi črkami.

## Sledljivost in preverjanje

Spremenjen je sestavljalnik `scripts/sestavi_knjigo.py`, ponovno sta sestavljena obstoječa DOCX in PDF. Izvirna prva izdaja je dosegljiva v zgodovini Git; lokalna varnostna kopija za primerjavo je v `work/berljivost/`.

Končni DOCX in PDF imata **94 fizičnih strani**, tri strani kazala in zadnjo vidno številko 93. Vseh 94 strani je bilo odprtih in vizualno pregledanih v izrisu: brez odrezanega besedila, prekrivanja, manjkajočih šumnikov ali praznih strani. Pri zadnjem popravku primerjalnega pregleda pirejev je bila ponovno pregledana spremenjena stran; preostali izrisi so bili preverjeno enaki že pregledanim.

Preverjanje potrjuje vseh 47 receptov, njihove dejanske začetne strani v kazalu, 188 notranjih povezav z obstoječimi cilji ter ohranitev besedila in količin iz vseh 63 izvornih tabel. V Wordu ni tabel ali slik celih strani; besedilo ostaja urejevalno. Licence in pomembne oznake nejasnosti so ohranjene. Novi recepti ali ID niso dodani. Vmesne slike, manifest podatkov ter preverjanja ostanejo v `work/`.

## Poznejši umik recepta

Po zaključku te spremembe je uporabnik naročil umik R0046 in ohranitev Karimovih makronov R0026. Aktualna izdaja ima zato 46 receptov, 91 strani, 184 notranjih povezav in 62 pretvorjenih podatkovnih skupin. Slog ostaja enak. Zgornji podatki o 47 receptih in 94 straneh opisujejo predhodno različico. Preverjanje nove izdaje je v `izdaja-2026-11-09.md`.
