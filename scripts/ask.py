import sys
from doc_sceptic.agent import DataArchitectureAgent
if len(sys.argv)<2:raise SystemExit('Usage: python scripts/ask.py "question"')
print(DataArchitectureAgent().ask(' '.join(sys.argv[1:])).model_dump_json(indent=2))
