import json
from doc_sceptic.agent import DataArchitectureAgent
from doc_sceptic.config import Settings
s=Settings();p=s.root/'data/evaluation/questions.jsonl';agent=DataArchitectureAgent();out=[]
for line in p.read_text(encoding='utf-8').splitlines():
 q=json.loads(line);r=agent.ask(q['question']);out.append({'id':q['id'],'expected':q['expected_action'],'predicted':r.action,'correct':r.action==q['expected_action']})
(s.root/'reports/evaluation.json').write_text(json.dumps(out,indent=2));print(sum(x['correct'] for x in out)/len(out))
