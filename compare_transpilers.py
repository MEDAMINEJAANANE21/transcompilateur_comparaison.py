#!/usr/bin/env python3
import argparse
import csv
import difflib
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path

CLASS_RE = re.compile(r'\b(class|interface|struct|record|enum)\s+([A-Za-z_][A-Za-z0-9_]*)')
METHOD_RE = re.compile(r'\b(public|private|protected|internal|static|virtual|override|abstract|sealed|async|extern|new|partial)\b')
SIGNATURE_RE = re.compile(
    r'(?P<indent>\s*)(?P<mods>(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|extern|new|partial)\s+)*)'
    r'(?P<ret>[A-Za-z_][A-Za-z0-9_<>,\[\]\.? ]*?)\s+'
    r'(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<params>[^\)]*)\)\s*(?P<tail>(?:{|=>|where|:).*)?$'
)
PROPERTY_RE = re.compile(
    r'(?P<mods>(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|new|partial)\s+)*)'
    r'(?P<type>[A-Za-z_][A-Za-z0-9_<>,\[\]\.? ]*?)\s+'
    r'(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{'
)
COMMENT_LINE_RE = re.compile(r'//.*?$|/\*.*?\*/', re.MULTILINE | re.DOTALL)
WS_RE = re.compile(r'\s+')

CONTROL_KEYWORDS = ['if', 'for', 'foreach', 'while', 'switch', 'catch', 'using', 'lock', 'return']
LOGIC_PATTERNS = {
    'try/catch': re.compile(r'\btry\b|\bcatch\b'),
    'throw': re.compile(r'\bthrow\b'),
    'LINQ': re.compile(r'\bSelect\b|\bWhere\b|\bOrderBy\b|\bGroupBy\b|\bFirstOrDefault\b|\bAny\b|\bAll\b'),
    'async/await': re.compile(r'\basync\b|\bawait\b'),
    'reflection': re.compile(r'\bType\.GetType\b|\bGetMethod\b|\bInvoke\b'),
    'interop': re.compile(r'\bDllImport\b|\bMarshal\b|\bComVisible\b|\bInterop\b'),
    'ui-events': re.compile(r'\bClick\b|\bLoad\b|\bTextChanged\b|\bCheckedChanged\b'),
    'casts': re.compile(r'\((?:int|string|bool|double|float|decimal|object)\)|\bas\b|\bis\b'),
    'null-handling': re.compile(r'\?\.|\?\?|\bnull\b'),
}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return path.read_text(encoding='latin-1', errors='ignore')


def strip_comments_and_ws(text: str) -> str:
    text = COMMENT_LINE_RE.sub('', text)
    text = WS_RE.sub(' ', text)
    return text.strip()


def file_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def find_matching_files(old_dir: Path, new_dir: Path):
    old_files = {p.relative_to(old_dir).as_posix(): p for p in old_dir.rglob('*.cs')}
    new_files = {p.relative_to(new_dir).as_posix(): p for p in new_dir.rglob('*.cs')}
    keys = sorted(set(old_files) | set(new_files))
    return keys, old_files, new_files


def extract_blocks(text: str):
    lines = text.splitlines()
    classes, methods, properties = {}, {}, {}
    current_class = None

    for i, line in enumerate(lines):
        c = CLASS_RE.search(line)
        if c:
            current_class = c.group(2)
            classes[current_class] = {'line': i + 1, 'signature': line.strip()}

        s = SIGNATURE_RE.match(line)
        if s:
            name = s.group('name')
            if name.lower() in CONTROL_KEYWORDS:
                continue
            sig = line.strip()
            key = f"{current_class or '<global>'}::{name}({normalize_params(s.group('params'))})"
            methods[key] = {'line': i + 1, 'signature': sig}
            continue

        p = PROPERTY_RE.match(line.strip())
        if p:
            name = p.group('name')
            key = f"{current_class or '<global>'}::{name}"
            properties[key] = {'line': i + 1, 'signature': line.strip()}

    return classes, methods, properties


def normalize_params(params: str) -> str:
    params = WS_RE.sub(' ', params.strip())
    params = re.sub(r'\s*=\s*[^,]+', '', params)
    return params


def compare_sets(old_map, new_map, file_rel, kind):
    rows = []
    old_keys = set(old_map)
    new_keys = set(new_map)
    for k in sorted(old_keys - new_keys):
        rows.append([file_rel, kind, 'removed', k, old_map[k]['line'], '', old_map[k]['signature'], '', ''])
    for k in sorted(new_keys - old_keys):
        rows.append([file_rel, kind, 'added', k, '', new_map[k]['line'], '', new_map[k]['signature'], ''])
    for k in sorted(old_keys & new_keys):
        osig = old_map[k]['signature']
        nsig = new_map[k]['signature']
        if strip_comments_and_ws(osig) != strip_comments_and_ws(nsig):
            rows.append([file_rel, kind, 'modified-signature', k, old_map[k]['line'], new_map[k]['line'], osig, nsig, 'signature changed'])
    return rows


def logic_metrics(text: str):
    metrics = {
        'if': len(re.findall(r'\bif\b', text)),
        'for': len(re.findall(r'\bfor\b', text)),
        'foreach': len(re.findall(r'\bforeach\b', text)),
        'while': len(re.findall(r'\bwhile\b', text)),
        'switch': len(re.findall(r'\bswitch\b', text)),
        'try': len(re.findall(r'\btry\b', text)),
        'catch': len(re.findall(r'\bcatch\b', text)),
        'throw': len(re.findall(r'\bthrow\b', text)),
        'return': len(re.findall(r'\breturn\b', text)),
        'async': len(re.findall(r'\basync\b', text)),
        'await': len(re.findall(r'\bawait\b', text)),
    }
    return metrics


def unified_diff_sample(old_text: str, new_text: str, limit=80):
    diff = list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm=''))
    return '\n'.join(diff[:limit])


def summarize_logic_changes(old_text: str, new_text: str):
    out = []
    oldm = logic_metrics(old_text)
    newm = logic_metrics(new_text)
    for k in oldm:
        if oldm[k] != newm[k]:
            out.append(f"{k}: {oldm[k]} -> {newm[k]}")
    for label, pattern in LOGIC_PATTERNS.items():
        o = bool(pattern.search(old_text))
        n = bool(pattern.search(new_text))
        if o != n:
            out.append(f"pattern {label}: {'present' if o else 'absent'} -> {'present' if n else 'absent'}")
    return '; '.join(out)


def compare_file(old_path: Path | None, new_path: Path | None, rel: str):
    rows = []
    if old_path is None:
        text = read_text(new_path)
        rows.append([rel, 'file', 'added', rel, '', 1, '', '', f'new file hash={file_hash(strip_comments_and_ws(text))}'])
        return rows, 'added', ''
    if new_path is None:
        text = read_text(old_path)
        rows.append([rel, 'file', 'removed', rel, 1, '', '', '', f'old file hash={file_hash(strip_comments_and_ws(text))}'])
        return rows, 'removed', ''

    old_text = read_text(old_path)
    new_text = read_text(new_path)
    old_norm = strip_comments_and_ws(old_text)
    new_norm = strip_comments_and_ws(new_text)

    if old_norm == new_norm:
        return rows, 'unchanged', ''

    old_classes, old_methods, old_props = extract_blocks(old_text)
    new_classes, new_methods, new_props = extract_blocks(new_text)

    rows.extend(compare_sets(old_classes, new_classes, rel, 'class'))
    rows.extend(compare_sets(old_methods, new_methods, rel, 'method'))
    rows.extend(compare_sets(old_props, new_props, rel, 'property'))

    logic_summary = summarize_logic_changes(old_text, new_text)
    if logic_summary:
        rows.append([rel, 'logic', 'metrics-change', rel, '', '', '', '', logic_summary])

    if not rows:
        rows.append([rel, 'file', 'text-changed', rel, '', '', '', '', 'normalized text differs but no entity-level diff was detected'])

    sample = unified_diff_sample(old_text, new_text)
    return rows, 'changed', sample


def main():
    parser = argparse.ArgumentParser(description='Compare two C# output folders from old/new transpilers and export a CSV/JSON/Markdown report.')
    parser.add_argument('--old', required=True, help='Folder containing old transpiler C# output')
    parser.add_argument('--new', required=True, help='Folder containing new transpiler C# output')
    parser.add_argument('--out', default='output/transcompiler_diff', help='Output prefix without extension')
    args = parser.parse_args()

    old_dir = Path(args.old)
    new_dir = Path(args.new)
    out_prefix = Path(args.out)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    keys, old_files, new_files = find_matching_files(old_dir, new_dir)
    all_rows = []
    file_summary = []
    diff_samples = {}

    for rel in keys:
        rows, status, sample = compare_file(old_files.get(rel), new_files.get(rel), rel)
        all_rows.extend(rows)
        file_summary.append({'file': rel, 'status': status, 'differences': len(rows)})
        if sample:
            diff_samples[rel] = sample

    csv_path = out_prefix.with_suffix('.csv')
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['file', 'entity_type', 'change_type', 'entity', 'old_line', 'new_line', 'old_signature', 'new_signature', 'notes'])
        writer.writerows(all_rows)

    json_path = out_prefix.with_suffix('.json')
    json_path.write_text(json.dumps({'summary': file_summary, 'differences': all_rows, 'diff_samples': diff_samples}, indent=2, ensure_ascii=False), encoding='utf-8')

    total_files = len(keys)
    changed_files = sum(1 for x in file_summary if x['status'] == 'changed')
    added_files = sum(1 for x in file_summary if x['status'] == 'added')
    removed_files = sum(1 for x in file_summary if x['status'] == 'removed')
    unchanged_files = sum(1 for x in file_summary if x['status'] == 'unchanged')

    md = []
    md.append('# Rapport de comparaison des sorties C#\n')
    md.append(f'- Dossier ancien: `{old_dir}`\n')
    md.append(f'- Dossier nouveau: `{new_dir}`\n')
    md.append(f'- Fichiers comparés: {total_files}\n')
    md.append(f'- Inchangés: {unchanged_files}\n')
    md.append(f'- Modifiés: {changed_files}\n')
    md.append(f'- Ajoutés: {added_files}\n')
    md.append(f'- Supprimés: {removed_files}\n')
    md.append(f'- Lignes de différences détectées: {len(all_rows)}\n')
    md.append('\n## Résumé par fichier\n')
    md.append('| Fichier | Statut | Nb différences |\n|---|---:|---:|\n')
    for row in file_summary:
        md.append(f"| {row['file']} | {row['status']} | {row['differences']} |\n")
    md.append('\n## Échantillons de diff\n')
    for rel, sample in list(diff_samples.items())[:20]:
        md.append(f'### {rel}\n```diff\n{sample}\n```\n')

    md_path = out_prefix.with_suffix('.md')
    md_path.write_text(''.join(md), encoding='utf-8')

    print(str(csv_path))
    print(str(json_path))
    print(str(md_path))

if __name__ == '__main__':
    main()
