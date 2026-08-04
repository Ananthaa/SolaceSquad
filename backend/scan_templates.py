import os, re, sys

template_dir = r'C:/Anantha/Projects/Soul Squad/backend/templates'
files_with_issues = {}

for root, dirs, files in os.walk(template_dir):
    dirs[:] = [d for d in dirs if not d.startswith('.')]
    for fname in files:
        if not fname.endswith('.html'):
            continue
        path = os.path.join(root, fname)
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines, 1):
            stripped = re.sub(r'\{[{%].*?[}%]\}', '', line)
            stripped = re.sub(r'&[a-zA-Z0-9#]+;', '', stripped)
            stripped = re.sub(r'https?://\S+', '', stripped)
            stripped = re.sub(r'\w\s*\?\s*[\w\(]', '', stripped)
            stripped = re.sub(r"confirm\('", '', stripped)
            if re.search(r'\?\?|\?(?!\w)', stripped):
                rel = path.replace(template_dir.replace('/', os.sep), '').replace('\\', '/')
                if rel not in files_with_issues:
                    files_with_issues[rel] = []
                files_with_issues[rel].append((i, line.strip()[:120]))

outlines = []
for f, hits in sorted(files_with_issues.items()):
    outlines.append('FILE: ' + f)
    for lineno, txt in hits[:10]:
        outlines.append('  LINE %d: %s' % (lineno, txt))
    outlines.append('')

result = '\n'.join(outlines)
print(result)

with open(r'C:/Anantha/Projects/Soul Squad/backend/scan_out.txt', 'w', encoding='utf-8') as f:
    f.write(result)
print('Written to scan_out.txt')
