from supabase import Client
from .config import Settings
from .retrieval import SupabaseRetriever
from .llm import LLMClient

def answer(question:str,settings:Settings|None=None,db_client:Client|None=None):
    s=settings or Settings();r=SupabaseRetriever(s,db_client);llm=LLMClient(s);ev=r.search(question,s.top_k)
    context="\n\n".join(f"[S{i}] {e.text}" for i,e in enumerate(ev,1));return llm.complete("Réponds avec le contexte et cite les sources.",f"Question: {question}\nContexte:\n{context}"),ev
