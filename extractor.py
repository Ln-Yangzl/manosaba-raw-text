import os
import re
import json
import csv
import argparse

ENCODINGS = ['utf-8', 'utf-8-sig', 'utf-16', 'utf-16le', 'utf-16be', 'gbk', 'latin-1']

def read_text_try(path):
    b = open(path, 'rb').read()
    for e in ENCODINGS:
        try:
            return b.decode(e), e
        except Exception:
            continue
    return None, None

def make_header_re(name: str):
    return re.compile(r'^#\s*(?P<id>.+_' + re.escape(name) + r'\d+)\b', re.IGNORECASE)

def extract_from_text(text, name: str):
    lines = text.splitlines()
    results = []
    i = 0
    header_re = make_header_re(name)
    while i < len(lines):
        m = header_re.match(lines[i])
        if m:
            block_id = m.group('id').strip()
            start = i
            i += 1
            block_lines = []
            while i < len(lines) and not lines[i].startswith('# '):
                block_lines.append(lines[i])
                i += 1
            # classify lines: commented (orig) vs translation (non-comment)
            orig_lines_raw = [ln.lstrip('; ').rstrip() for ln in block_lines if ln.strip().startswith(';')]
            # remove redundant id marker lines from orig e.g. "> Name: |#<id>|"
            marker_re = re.compile(r"\|\s*#\s*" + re.escape(block_id) + r"\s*\|")
            orig_lines = [ln for ln in orig_lines_raw if not marker_re.search(ln)]
            trans_lines = [ln.rstrip() for ln in block_lines if not ln.strip().startswith(';') and ln.strip()!='']
            results.append({
                'id': block_id,
                'orig': '\n'.join(orig_lines).strip(),
                'trans': '\n'.join(trans_lines).strip(),
            })
        else:
            i += 1
    return results

def walk_and_extract(root, name: str):
    out = []
    for dirpath, dirs, files in os.walk(root):
        # skip common VCS/build dirs quickly
        if any(skip in dirpath.lower() for skip in ['\\.git', '\\debug', '\\system', '\\build']):
            continue
        for fn in files:
            if not fn.lower().endswith(('.bytes', '.txt', '.script', '.csv', '.json')) and '.' in fn:
                # try only likely text files, but still allow common ext
                continue
            path = os.path.join(dirpath, fn)
            text, enc = read_text_try(path)
            if text is None:
                continue
            for item in extract_from_text(text, name):
                # only keep entries that have some translation text
                if item['trans'] or item['orig']:
                    out.append(item)
    return out

def save_jsonl(items, path):
    with open(path, 'w', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')

def save_csv(items, path):
    keys = ['id','orig','trans']
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for it in items:
            w.writerow({k: it.get(k,'') for k in keys})

def main():
    p = argparse.ArgumentParser(description='Extract dialogue blocks by name')
    p.add_argument('--root', action='append', default=None, help='root dir to scan; can be provided multiple times')
    p.add_argument('--name', default='Sherry', help='character name appearing in IDs (e.g., Sherry)')
    p.add_argument('--out-jsonl', default=None, help='output jsonl path; defaults to <name>_extracts.jsonl')
    p.add_argument('--out-csv', default=None, help='output csv path; defaults to <name>_extracts.csv')
    p.add_argument('--out-dir', default=None, help='directory to place outputs; created if missing')
    args = p.parse_args()

    roots = args.root or ['.']
    # aggregate items from all specified roots
    items = []
    for r in roots:
        items.extend(walk_and_extract(r, args.name))

    # determine output paths
    out_jsonl = args.out_jsonl or f"{args.name.lower()}_extracts.jsonl"
    out_csv = args.out_csv or f"{args.name.lower()}_extracts.csv"
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        out_jsonl = os.path.join(args.out_dir, os.path.basename(out_jsonl))
        out_csv = os.path.join(args.out_dir, os.path.basename(out_csv))

    save_jsonl(items, out_jsonl)
    save_csv(items, out_csv)
    print(f'done: {len(items)} entries for name="{args.name}" -> {out_jsonl}, {out_csv}')

if __name__ == '__main__':
    main()