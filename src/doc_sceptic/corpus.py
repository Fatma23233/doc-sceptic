from __future__ import annotations
import hashlib,re
from dataclasses import dataclass
from pathlib import Path
@dataclass
class Chunk:
 chunk_id:str;title:str;section:str;source_path:str;url:str;text:str
def clean(x):
 x=re.sub(r'^---\s*\n.*?\n---\s*\n','',x,flags=re.S);x=re.sub(r'<!--.*?-->','',x,flags=re.S);x=re.sub(r'\[([^]]+)\]\([^)]+\)',r'\1',x);x=re.sub(r'<[^>]+>',' ',x);return re.sub(r'\s+',' ',x).strip()
def sections(raw,fallback):
 out=[];title=fallback;buf=[]
 for line in raw.splitlines():
  m=re.match(r'^(#{1,6})\s+(.+)',line)
  if m:
   text=clean('\n'.join(buf));
   if text:out.append((title,text))
   title=m.group(2).strip();buf=[]
  else:buf.append(line)
 text=clean('\n'.join(buf));
 if text:out.append((title,text))
 return out
def split(text,size=1500,overlap=200):
 return [text[i:i+size] for i in range(0,len(text),size-overlap) if text[i:i+size].strip()]
def build_chunks(files:list[Path],root:Path):
 out=[]
 for p in files:
  rel=p.relative_to(root).as_posix();raw=p.read_text(encoding='utf-8',errors='replace');secs=sections(raw,p.stem);doc_title=secs[0][0] if secs else p.stem
  for si,(sec,text) in enumerate(secs):
   for ci,piece in enumerate(split(text)):
    cid=hashlib.sha256(f'{rel}:{si}:{ci}:{piece}'.encode()).hexdigest()[:24];url=f'https://github.com/MicrosoftDocs/fabric-docs/blob/main/docs/{rel}';out.append(Chunk(cid,doc_title,sec,rel,url,piece))
 return out
