# Service Box media extractor

A small tool I made to unpack the original Peugeot and/or Citroën Service Box / SEDRE discs and their factory databases into a working folder. That is all it does: nothing is decoded, converted or repaired, and no website is built.

## Run

Brand codes on the discs: `AP` = Peugeot, `AC` = Citroën.

Windows with Python 3.10+ (standard library only), 7-Zip and JDK 17+. Free disk space in addition to the ISOs: roughly 20 GB for Peugeot, 30 GB for Citroën.

1. Double-click `export.bat`. If no discs are found it prints the input folders (`input-media/peugeot`, `input-media/citroen`).
2. Copy the three ISO files of a brand into its folder and run `export.bat` again. Either brand works alone; if both are present, both are processed (`export.bat --brand peugeot` limits it). Discs are unpacked one after another, each by several 7-Zip processes (as many as the CPU has, at most 8).
3. Results are in `work/export/<brand>/`: `DVD1`–`DVD3` (disc contents), `sedre/` (SEDRE installer contents), `db/AFDZ.FDB` and `db/SDR.FDB` (the factory Firebird databases) and `SUMMARY.txt`.

Run again to continue after an interruption: finished discs and databases are skipped, an unfinished disc starts over. The original ISOs are never changed.

## What is encrypted

Most of the documentation content on the discs is stored in `.7en` files, which are compressed and encrypted. The extractor leaves them untouched. The Firebird databases and the installers are not affected and are extracted as they are. The key is not part of this repository.

| Content | Where | State without the key |
|---|---|---|
| Service Box database (`AFDZ.FDB`) | `InstallFiles/AFDZ.FDB.Z` (zlib) | Extracted, readable |
| SEDRE database (`SDR.FDB`) | inside the SEDRE installer | Extracted, readable |
| Installer web applications, properties, XML | installer packages | Extracted, readable |
| Images (`*.jpg.7en`, about 157,000) | `Static/AP/img/` | Encrypted |
| Help pages (`*.html.7en`, many languages) | `Static/AP/aide/` | Encrypted |
| Complex lists (`*.html.7en`) | `Static/AP/listecomplex/` | Encrypted |
| Parts catalog (`*.xls.7en`) | `Static/AP/pecatalog/` | Encrypted |
| SEDRE wiring drawings (`*.svgz.7en`, about 130,000) | `Static/AP/svg/` | Encrypted |
| SEDRE drawing texts (`*.sgm.7en`) | `Static/AP/sgm/` | Encrypted |

Counts are approximate and were taken from one brand. A file-by-file description of the discs, the databases and the processing steps is in [STRUCTURE.md](STRUCTURE.md). `SUMMARY.txt` lists the actual numbers per file type.

## Legal notes

- The discs, the factory databases and the documentation inside them belong to PSA / Stellantis and other rights holders. This repository contains none of it: no disc content, no database, no key, no key-extraction method and no decoder.
- Laws such as the US DMCA section 1201 and the EU Copyright and InfoSec Directives restrict circumventing technical protection and distributing tools or information for it; exceptions (for example interoperability or research) differ by country and are narrow. That is why I left the `.7en` files untouched and wrote nothing here about decrypting them.
- This is an independent project, not affiliated with or endorsed by Peugeot, Citroën or Stellantis; the names are trademarks of their owners. Use it only with media you legitimately own. It comes with no warranty and is not legal advice.
- If a rights holder objects to anything in this repository, I will remove it on request.

## Source discs I used

These are the disc images I worked from (Service Box, 11.2013, three discs per brand). If your files have the same SHA-256, you have the same discs.

```
Citroen_11_2013_DVD_1of3.iso
  size   8123174912
  MD5    cd64b40f02eea1211cc47bcc2d332414
  SHA-1  a952571af5edf5d636940ad3ad886df08f0c899a
  SHA-256 9542fb07a432e12b2c48563a56b1ec44ddc0e96ef2f127a6f8c0cff16036266a

Citroen_11_2013_DVD_2of3.iso
  size   6423697408
  MD5    08334381d7967c4e20d27dc5080731ff
  SHA-1  194ed72f2213605b4336aa38a07ae8b500b16eb9
  SHA-256 155fefd88c2be3eede1fdc9a508b64210fc145d1185bedeff20a8c44a45d9508

Citroen_11_2013_DVD_3of3.iso
  size   7425576960
  MD5    b9bd800d8faabe072c42303bd8d0b517
  SHA-1  dfed55adbe81fcac9f21de260b6c4e32f60a9b02
  SHA-256 7f3b77d0e2eb212b8e828b958e5ca48d0e7c218c351c3c827bffc67f79b47068

Peugeot_11_2013_DVD_1of3.iso
  size   8080539648
  MD5    71148abae0d83b8a44f7bb82a4303fc1
  SHA-1  33a961fb7f801ad831bca01f75ef052def7496e1
  SHA-256 5c3e59b4618f36bee7f9d2b163b5b4d940b3056af386841717c70140cad37f7f

Peugeot_11_2013_DVD_2of3.iso
  size   838891520
  MD5    8680210ffabe04db32852da14944506e
  SHA-1  0ba3282bd261a7c2e3cdd831d66c87d85f0087c9
  SHA-256 c9e5d4417442650a773a899eb582e54ca811a2cf949b56563e02c0264506eef8

Peugeot_11_2013_DVD_3of3.iso
  size   4399697920
  MD5    507b34abbcc4cd1f539770f126bc2bb1
  SHA-1  f5b8478e11cc3d2a14bbfd5f8c056cc829ad7ff2
  SHA-256 5915c770a65c2238e4268a2c2290d965d2bb960ce93437141f330610313af79d
```

## Hints from my own project

Not a walkthrough, only what I found along the way. What is on the discs and in the databases is described in [STRUCTURE.md](STRUCTURE.md).

- **Databases:** open them only on a copy, because the embedded Firebird engine can write to a file even when you only read it. The installers ship Firebird 2.1 (32-bit embedded); a Firebird 2.5 or compatible engine opens the files, version 3 and later does not. The text columns are declared without a character set but contain UTF-8 text, so connect with the character set `NONE` and decode the bytes yourself; otherwise the driver garbles accented letters.
- **Documents:** they are XML with codes instead of text; the words come from the per-language dictionary tables, so one stored document serves every language.
- **Size:** about 300,000 small files per brand are slow to host, so I packed them into roughly 70 uncompressed ZIP packages with an index of where each file sits, and read single files out of the packages by byte range.
- **Viewer:** plain static HTML and JavaScript is enough; the browser assembles the documents, filters by vehicle and does the clickable drawings.

This repository contains no factory media, databases or extracted documentation, and not the website.
