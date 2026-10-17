import json,shutil,subprocess
from doc_sceptic.config import Settings
s=Settings();cfg=json.loads((s.root/'configs/corpus.json').read_text());target=s.root/'data/raw/fabric-docs'
if target.exists():shutil.rmtree(target)
subprocess.run(['git','clone','--depth','1','--branch',cfg['branch'],cfg['repository'],str(target)],check=True)
print('Corpus téléchargé:',target)
