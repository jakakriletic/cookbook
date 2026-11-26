"""Osveži kazalo in polja v knjigi DOCX z LibreOfficom ter izvozi PDF.

Nadomestek za scripts/osvezi-knjigo.ps1, kadar Word ni na voljo (Linux,
oblačno okolje). Uporaba:

    python3 scripts/osvezi-knjigo-lo.py outputs/moj-kuharski-zvezek.docx

Pisavi knjige sta Calibri in Cambria; v Linuxu ju nadomestita metrično enaki
Carlito in Caladea, zato je prelom strani enak kot v Wordu.
"""
import subprocess, sys, time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    p = PropertyValue(); p.Name = name; p.Value = value
    return p


def main(path):
    docx = Path(path).resolve()
    pdf = docx.with_suffix('.pdf')
    office = subprocess.Popen(['soffice', '--headless', '--invisible', '--nologo', '--norestore',
                               '--accept=socket,host=localhost,port=2002;urp;'])
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
        for _ in range(60):
            try:
                ctx = resolver.resolve('uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext')
                break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError('LibreOffice se ni zagnal.')
        desktop = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)
        doc = desktop.loadComponentFromURL(docx.as_uri(), '_blank', 0, (prop('Hidden', True),))
        # Kazalo v dveh stolpcih (strnjeno); LibreOffice stolpce odseka iz DOCX pri kazalu ne upošteva.
        indexes = doc.getDocumentIndexes()
        for i in range(indexes.getCount()):
            index = indexes.getByIndex(i)
            if index.supportsService('com.sun.star.text.ContentIndex'):
                cols = index.TextColumns
                cols.setColumnCount(2)
                cols.AutomaticDistance = 800  # 8 mm
                index.TextColumns = cols
        # Dva prehoda: po prvem kazalo spremeni obseg in s tem številke strani.
        for _ in range(2):
            indexes = doc.getDocumentIndexes()
            for i in range(indexes.getCount()):
                indexes.getByIndex(i).update()
            doc.getTextFields().refresh()
            doc.refresh()
        pages = doc.getCurrentController().getPropertyValue('PageCount')
        doc.storeToURL(docx.as_uri(), (prop('FilterName', 'MS Word 2007 XML'),))
        filter_data = uno.Any('[]com.sun.star.beans.PropertyValue', tuple([
            prop('ExportBookmarks', True), prop('UseTaggedPDF', True),
            prop('ExportLinksRelativeFsys', False), prop('ConvertOOoTargetToPDFTarget', True),
            prop('ExportNotes', False), prop('Quality', 90)]))
        uno.invoke(doc, 'storeToURL', (pdf.as_uri(), (prop('FilterName', 'writer_pdf_Export'),
                                                     prop('FilterData', filter_data))))
        doc.close(True)
        print(f'Shranjena DOCX in PDF. Strani: {pages}.')
    finally:
        try:
            desktop.terminate()
        except Exception:
            pass
        office.terminate()


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'outputs/moj-kuharski-zvezek.docx')
