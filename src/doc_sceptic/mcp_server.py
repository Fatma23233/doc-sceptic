from fastmcp import FastMCP
from .retrieval import SupabaseRetriever
mcp=FastMCP("Doc-Sceptic Supabase")
_service=None
def service():
 global _service
 if _service is None:_service=SupabaseRetriever()
 return _service
@mcp.tool
def search_docs(query:str,top_k:int=6)->list[dict]:return [x.model_dump() for x in service().search(query,top_k)]
@mcp.tool
def compare_options(subject:str,option1:str,option2:str,top_k:int=4)->dict:
 out=service().compare(subject,option1,option2,top_k);return {k:[x.model_dump() for x in v] for k,v in out.items()}
@mcp.tool
def get_source(source_id:str)->dict:return service().get_source(source_id).model_dump()
if __name__=="__main__":mcp.run()
