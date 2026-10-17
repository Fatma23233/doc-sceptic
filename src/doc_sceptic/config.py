from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    root: Path = Path(__file__).resolve().parents[2]
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    reranker_model: str = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    top_k: int = int(os.getenv("TOP_K", "6"))
    min_evidence_score: float = float(os.getenv("MIN_EVIDENCE_SCORE", "0.35"))
    ingest_batch_size: int = int(os.getenv("INGEST_BATCH_SIZE", "50"))

    @property
    def corpus_path(self) -> Path:
        return self.root / os.getenv("CORPUS_PATH", "data/raw/fabric-docs/docs")

    def validate_supabase(self, service: bool=False):
        if not self.supabase_url: raise RuntimeError("SUPABASE_URL absent du fichier .env")
        key=self.supabase_service_role_key if service else self.supabase_anon_key
        if not key: raise RuntimeError("Clé Supabase absente du fichier .env")
