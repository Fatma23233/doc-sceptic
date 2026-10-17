import argparse
from .agent import DataArchitectureAgent
def main():
 p=argparse.ArgumentParser();p.add_argument('question',nargs='+');a=p.parse_args();print(DataArchitectureAgent().ask(' '.join(a.question)).model_dump_json(indent=2))
