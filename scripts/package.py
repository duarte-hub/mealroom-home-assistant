"""Create a source release, deliberately excluding app/user/analysis data."""
from pathlib import Path
import hashlib
from zipfile import ZipFile, ZIP_DEFLATED

root=Path(__file__).resolve().parents[1]
dist=root/'dist'
dist.mkdir(exist_ok=True)
archive=dist/'mealroom-0.1.0.zip'
files=[]
for name in ['README.md','LICENSE','repository.yaml','compose.yaml','.gitignore']:
    files.append(root/name)
for name in ['meal_planner','tests','docs','scripts','.github']:
    for p in (root/name).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.sqlite3'] and p.name!='.DS_Store':
            files.append(p)
with ZipFile(archive,'w',ZIP_DEFLATED) as z:
    for p in sorted(files):
        z.write(p,Path('mealroom-0.1.0')/p.relative_to(root))
with ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any(any(part in name.split('/') for part in ['data','mise-analysis','.git','.venv']) for name in z.namelist())
    assert 'mealroom-0.1.0/meal_planner/config.yaml' in z.namelist()
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
(dist/(archive.name+'.sha256')).write_text(f'{digest}  {archive.name}\n')
print(f'{archive}\n{len(files)} files · {archive.stat().st_size:,} bytes\nSHA-256 {digest}')
