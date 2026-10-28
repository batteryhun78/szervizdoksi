# What is on the discs

Reference for the 2013 Peugeot / Citroën Service Box (documentation) and SEDRE (wiring diagrams) DVD sets: which file is what, what is encrypted, and what I did with each part. Counts are from the Peugeot set (data version 9C-S / SB95, DocBackup 3.6.17); Citroën has the same layout.

## The three discs

| Disc | Content | Size |
|---|---|---|
| DVD1 | master installer, SEDRE installer, SEDRE drawings 1/2 | ~115,000 files, ~8 GB |
| DVD2 | SEDRE drawings 2/2 | ~17,700 files, ~0.8 GB |
| DVD3 | Service Box installer, documentation database, images, help | ~162,000 files, ~4.2 GB |

## File by file

| What | Where | Encrypted? | What it contains |
|---|---|---|---|
| Service Box database | `DVD3/InstallFiles/AFDZ.FDB.Z` | no (zlib) | Firebird database, ~5.5 GB unpacked. The documents themselves, dictionaries, vehicle and function trees |
| SEDRE database | inside `DVD1/InstallFiles/sedre_backup_installer.jar` | no | Firebird database `SDR.FDB` (~150 MB): drawing index, vehicle families, texts |
| Installers | `*_installer.jar` (IzPack) | no | Application servers, web applications, Firebird engine, properties and XML configuration |
| Images | `DVD3/Static/AP/img/**/*.jpg.7en` (~157,000) | **yes** | Part pictures and information images, in subfolders by number |
| Help pages | `DVD3/Static/AP/aide/AP/<locale>/…/*.html.7en` | **yes** | Help texts in about 24 languages |
| Complex lists | `DVD3/Static/AP/listecomplex/*.html.7en` (~440) | **yes** | Large lookup lists as HTML |
| Parts catalog | `DVD3/Static/AP/pecatalog/*.xls.7en` (~340) | **yes** | Parts catalog spreadsheets |
| SEDRE drawings | `DVD1+2/Static/AP/svg/<family>/*.svgz.7en` (~130,000) | **yes** | Wiring diagrams as compressed SVG, by vehicle family |
| SEDRE drawing texts | `DVD1+2/Static/AP/sgm/<family>/*.sgm.7en` (~2,600) | **yes** | SGML descriptions shown beside the drawings |
| File lists | `lst.Z`, `lst_diff.Z` | no (zlib) | Complete file list with sizes |
| Appearance | `Static/AP/charte`, `css`, `mentions` | no | Style sheets and legal texts |

`.7en` means compressed and encrypted. Everything in the table that is not `.7en` is readable after the extractor has run.

## What is inside the databases

- **Documents:** about 127,000 documents stored as plain XML in BLOB columns. They carry codes, not text.
- **Dictionaries:** the text for those codes lives in separate dictionary tables, one set per language (41 languages for the main sentence dictionary, 111 locale codes in total). A document is turned into readable text by looking its codes up in the chosen language.
- **Metadata:** per document its reference, type, title code, applicability (engine / body variants) and the functions and vehicle lines it belongs to.
- **Parts catalog pictures:** hotspots (clickable areas over an image) are defined inside the document XML.
- **SEDRE:** wiring drawings are SVG groups; clickable wires, connectors and parts are identified by the id prefix of each group and linked through animation elements, so tracing a wire is done in the browser from the SVG itself. Texts come from the SEDRE thesaurus property files, not from the database.

Character encoding: the text columns are stored as raw UTF-8 bytes in columns declared without a character set, so a database driver must be told not to convert them.
