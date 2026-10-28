"""Unpack original Service Box / SEDRE discs and the factory databases. Nothing is decoded, converted or verified."""
from collections import Counter
from pathlib import Path
import argparse
import os
import re
import shutil
import subprocess
import sys
import zlib

CODE = Path(__file__).resolve().parents[2]
INPUT = CODE / 'input-media'
WORK = CODE / 'work' / 'export'
BRANDS = ('peugeot', 'citroen')


def seven_zip():
    candidates = [shutil.which('7z'), shutil.which('7za')]
    for variable in ('ProgramFiles', 'ProgramFiles(x86)'):
        if os.environ.get(variable):
            candidates.append(str(Path(os.environ[variable]) / '7-Zip/7z.exe'))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit('7-Zip was not found. Install 7-Zip, then restart.')


def find_discs(brand):
    folder = INPUT / brand
    folder.mkdir(parents=True, exist_ok=True)
    discs = {}
    for path in sorted(folder.rglob('*.iso')):
        match = re.search(r'dvd[ _-]*([123])', path.name.lower())
        if match:
            discs.setdefault(int(match.group(1)), path)
    return discs


def run(command):
    if subprocess.run(command).returncode:
        raise SystemExit('Failed: ' + ' '.join(str(part) for part in command[:3]))


def list_files(tool, iso):
    text = subprocess.run([tool, 'l', '-slt', '-sccUTF-8', '--', str(iso)], capture_output=True,
                          text=True, encoding='utf-8', errors='replace').stdout
    files = []
    for block in re.split(r'\r?\n\r?\n', text.partition('----------')[2].strip()):
        fields = dict(line.split(' = ', 1) for line in block.splitlines() if ' = ' in line)
        if 'Path' in fields and fields.get('Folder') != '+' and not fields.get('Attributes', '').startswith('D'):
            files.append((fields['Path'], int(fields.get('Size') or 0)))
    return files


def extract_disc(tool, iso, target, jobs):
    done = target / '.done'
    if done.is_file():
        print('  already extracted: ' + target.name)
        return
    target.mkdir(parents=True, exist_ok=True)
    files = list_files(tool, iso)
    jobs = max(1, min(jobs, len(files)))
    print(f'  extracting {iso.name}: {len(files):,} files on {jobs} processes', flush=True)
    chunks = [[] for _ in range(jobs)]
    loads = [0] * jobs
    for path, size in sorted(files, key=lambda item: -item[1]):
        index = loads.index(min(loads))
        chunks[index].append(path)
        loads[index] += size + 4096
    tmp = WORK / 'tmp'
    tmp.mkdir(parents=True, exist_ok=True)
    processes = []
    for index, chunk in enumerate(chunks):
        listing = tmp / f'{target.parent.name}-{target.name}-{index}.txt'
        listing.write_text('\n'.join(chunk) + '\n', encoding='utf-8-sig')
        processes.append(subprocess.Popen([tool, 'x', '-y', '-bso0', '-bsp0', '-spd', '-scsUTF-8',
                                           '-o' + str(target), str(iso), '@' + str(listing)]))
    codes = [process.wait() for process in processes]
    if any(codes):
        raise SystemExit('Extraction failed: ' + iso.name)
    done.write_text('ok')
    print('  finished ' + iso.name, flush=True)


def compile_helper():
    helper = WORK / 'tools'
    helper.mkdir(parents=True, exist_ok=True)
    source = helper / 'SafeIzExtract.java'
    shutil.copyfile(CODE / 'pipeline/data_extraction/java/SafeIzExtract.java', source)
    run(['javac', '--release', '17', '-encoding', 'UTF-8', '-d', str(helper), str(source)])


def extract_installer(base):
    output = base / 'sedre'
    database = output / 'Firebird' / 'SDR.FDB'
    if (output / '.done').is_file():
        print('  SEDRE installer already extracted')
        return database
    helper = WORK / 'tools'
    jar = base / 'DVD1/InstallFiles/sedre_backup_installer.jar'
    tmp = WORK / 'tmp' / base.name
    tmp.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=True)
    print('  extracting SEDRE installer', flush=True)
    run(['java', '-Djava.io.tmpdir=' + str(tmp), '-cp', str(helper) + os.pathsep + str(jar), 'SafeIzExtract',
         str(jar), str(output), str(base / 'installer-files.tsv'), str(WORK)])
    (output / '.done').write_text('ok')
    return database


def unpack_database(source, target):
    print('  unpacking ' + target.name, flush=True)
    part = target.with_name(target.name + '.part')
    with source.open('rb') as stream, part.open('wb') as out:
        expected = int.from_bytes(stream.read(8), 'little')
        decoder, done, last = zlib.decompressobj(), 0, -1
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            raw = decoder.decompress(block)
            out.write(raw)
            done += len(raw)
            percent = done * 100 // max(1, expected)
            if percent // 10 != last // 10:
                print(f'  AFDZ.FDB: {percent}%', flush=True)
                last = percent
        tail = decoder.flush()
        out.write(tail)
        done += len(tail)
    if not decoder.eof or done != expected:
        raise SystemExit('The compressed database is incomplete or damaged: ' + source.name)
    part.replace(target)


def summary(base):
    counts = Counter()
    for path in base.glob('DVD*/Static/**/*.7en'):
        counts[Path(path.stem).suffix.lower() or '(none)'] += 1
    lines = [f'{base.name}: databases']
    for name in ('AFDZ.FDB', 'SDR.FDB'):
        path = base / 'db' / name
        lines.append(f'  {name}: ' + (f'{path.stat().st_size / 1048576:,.0f} MB' if path.is_file() else 'MISSING'))
    lines.append(f'{base.name}: encrypted .7en files (not decoded, key not included)')
    lines += [f'  {kind}: {count:,}' for kind, count in sorted(counts.items())] or ['  none found']
    text = '\n'.join(lines)
    (base / 'SUMMARY.txt').write_text(text + '\n', encoding='utf-8')
    return text


def export_brand(tool, brand, discs, jobs):
    print('\n' + brand.upper())
    base = WORK / brand
    (base / 'db').mkdir(parents=True, exist_ok=True)
    extract_disc(tool, discs[1], base / 'DVD1', jobs)
    sedre = extract_installer(base)
    if not (base / 'db/SDR.FDB').is_file():
        part = base / 'db/SDR.FDB.part'
        shutil.copyfile(sedre, part)
        part.replace(base / 'db/SDR.FDB')
    extract_disc(tool, discs[2], base / 'DVD2', jobs)
    extract_disc(tool, discs[3], base / 'DVD3', jobs)
    if not (base / 'db/AFDZ.FDB').is_file():
        unpack_database(base / 'DVD3/InstallFiles/AFDZ.FDB.Z', base / 'db/AFDZ.FDB')
    print('\n' + summary(base))


def main():
    parser = argparse.ArgumentParser(description='Unpack the discs of the brands found in input-media/.')
    parser.add_argument('--brand', choices=('auto', 'peugeot', 'citroen', 'both'), default='auto')
    args = parser.parse_args()
    chosen = BRANDS if args.brand in ('auto', 'both') else (args.brand,)
    found = {brand: find_discs(brand) for brand in chosen}
    ready = {brand: discs for brand, discs in found.items() if len(discs) == 3}
    for brand, discs in found.items():
        if discs and len(discs) != 3:
            print(f'{brand}: found DVD {sorted(discs)}, all three are needed - skipped.')
    if not ready:
        print('No complete disc set found. Copy the three ISO files of a brand into:')
        for brand in chosen:
            print('  ' + str(INPUT / brand))
        return 1
    for name in ('java', 'javac'):
        if not shutil.which(name):
            raise SystemExit('Missing program: ' + name + ' (JDK 17+ is required).')
    tool = seven_zip()
    WORK.mkdir(parents=True, exist_ok=True)
    compile_helper()
    for brand, discs in ready.items():
        export_brand(tool, brand, discs, min(os.cpu_count() or 1, 8))
    print('\nDone. Results: ' + str(WORK))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nInterrupted. Run again to continue; an unfinished disc starts over.')
        sys.exit(130)
