param([string]$DocxPath)
$ErrorActionPreference = 'Stop'
$bookPath = (Resolve-Path -LiteralPath $DocxPath).Path
$pdfPath = [System.IO.Path]::ChangeExtension($bookPath, '.pdf')
$wordBook = New-Object -ComObject Word.Application
$wordBook.Visible = $false
$wordBook.DisplayAlerts = 0
$previousPrintBackgrounds = $wordBook.Options.PrintBackgrounds
try {
    $wordBook.Options.PrintBackgrounds = $true
    $bookDoc = $wordBook.Documents.Open($bookPath, $false, $false)
    $bookDoc.Repaginate()
    [void]$bookDoc.Fields.Update()
    foreach ($toc in $bookDoc.TablesOfContents) { $toc.Update() }
    $bookDoc.Repaginate()
    foreach ($toc in $bookDoc.TablesOfContents) { $toc.UpdatePageNumbers() }
    $bookDoc.Save()
    $bookDoc.ExportAsFixedFormat($pdfPath, 17, $false, 0, 0, 1, 1, 0, $true, $true, 1, $true, $true, $false)
    $pages = $bookDoc.ComputeStatistics(2)
    Write-Output "Shranjena DOCX in PDF. Strani: $pages. Kazal: $($bookDoc.TablesOfContents.Count)."
    $bookDoc.Close(0)
} finally {
    $wordBook.Options.PrintBackgrounds = $previousPrintBackgrounds
    $wordBook.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordBook)
}
