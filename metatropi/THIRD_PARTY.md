# Componenti di terze parti

Metatropi include o usa questi programmi open source. Tutto gira in locale.

| Componente | Uso | Licenza | Sorgenti |
|---|---|---|---|
| FFmpeg (build statica di ffmpeg-static) | audio, video, immagini, sottotitoli | GPL v3 | https://ffmpeg.org · https://github.com/eugeneware/ffmpeg-static |
| pandoc | documenti (Word, ODT, Markdown, EPUB, LaTeX…) | GPL v2 o successiva | https://github.com/jgm/pandoc |
| Electron / Chromium | interfaccia, stampa in PDF | MIT / BSD | https://github.com/electron/electron |
| Python (python-build-standalone) | esecuzione degli strumenti PDF | PSF | https://github.com/astral-sh/python-build-standalone |
| pdf2docx | PDF → Word | MIT | https://github.com/ArtifexSoftware/pdf2docx |
| PyMuPDF / MuPDF | lettura dei PDF, tabelle | AGPL v3 | https://github.com/pymupdf/PyMuPDF |
| OpenCV, NumPy, python-docx, lxml, fontTools | dipendenze di pdf2docx | Apache 2.0 / BSD / MIT | https://pypi.org |
| PDF.js | lettura e rendering dei PDF | Apache 2.0 | https://github.com/mozilla/pdf.js |
| SheetJS Community Edition | Excel, ODS, Numbers, CSV | Apache 2.0 | https://git.sheetjs.com/sheetjs/sheetjs |
| js-yaml | YAML | MIT | https://github.com/nodeca/js-yaml |

Su macOS vengono usati anche gli strumenti di sistema `sips` (HEIC, RAW, PSD),
`textutil` (Word 97 .doc) e il framework Vision per il riconoscimento del testo (OCR). Se LibreOffice è installato, viene usato per
PowerPoint, Keynote, Pages e per PDF più fedeli all'originale.
