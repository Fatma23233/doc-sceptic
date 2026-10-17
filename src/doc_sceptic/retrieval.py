from __future__ import annotations

import torch

from sentence_transformers import SentenceTransformer, CrossEncoder
from supabase import Client

from .config import Settings
from .schemas import Evidence
from .supabase_store import service_client


class SupabaseRetriever:
    """
    Recherche hybride pour Doc-Sceptic.

    Pipeline :
        question
          ↓
        embedding
          ↓
        Supabase / pgvector
          ↓
        recherche vectorielle + lexicale
          ↓
        candidats
          ↓
        CrossEncoder pour le reranking
          ↓
        Top-K passages

    Important :
    - le CrossEncoder sert uniquement à réordonner les passages ;
    - hybrid_score de Supabase sert de score de preuve ;
    - le seuil d'abstention de l'agent ne dépend donc pas directement
      du score du CrossEncoder.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        client: Client | None = None,
        load_reranker: bool = True,
    ):
        self.s = settings or Settings()

        # Si aucun client n'est fourni, on utilise le client backend
        # avec la clé secrète Supabase.
        self.client = client or service_client(self.s)

        # Modèle d'embedding.
        self.embedder = SentenceTransformer(
            self.s.embedding_model
        )

        # Reranker.
        #
        # Sigmoid permet d'obtenir des scores entre 0 et 1.
        # Ces scores servent uniquement à classer les passages.
        if load_reranker:
            self.reranker = CrossEncoder(
                self.s.reranker_model,
                activation_fn=torch.nn.Sigmoid(),
            )
        else:
            self.reranker = None

    def search(
        self,
        query: str,
        k: int | None = None,
    ) -> list[Evidence]:
        """
        Recherche les passages les plus pertinents.

        1. Création de l'embedding de la question.
        2. Recherche hybride dans Supabase.
        3. Reranking des candidats.
        4. Retour des k meilleures preuves.
        """

        k = k or self.s.top_k

        # ---------------------------------------------------------
        # 1. Embedding de la question
        # ---------------------------------------------------------

        query_embedding = self.embedder.encode(
            query,
            normalize_embeddings=True,
        ).tolist()

        # ---------------------------------------------------------
        # 2. Recherche hybride dans Supabase
        # ---------------------------------------------------------
        #
        # On récupère volontairement plus de résultats que nécessaire.
        # Le CrossEncoder choisira ensuite les meilleurs.
        # ---------------------------------------------------------

        candidate_count = max(k * 4, 20)

        response = self.client.rpc(
            "hybrid_search_documents",
            {
                "query_embedding": query_embedding,
                "query_text": query,
                "match_count": candidate_count,
            },
        ).execute()

        candidates = response.data or []

        if not candidates:
            return []

        # ---------------------------------------------------------
        # 3. Reranking
        # ---------------------------------------------------------

        if self.reranker is not None:

            pairs = [
                (
                    query,
                    row["content"],
                )
                for row in candidates
            ]

            reranker_scores = self.reranker.predict(
                pairs,
                show_progress_bar=False,
            )

            ranked_candidates = sorted(
                zip(candidates, reranker_scores),
                key=lambda item: float(item[1]),
                reverse=True,
            )

            ranked_candidates = ranked_candidates[:k]

            # IMPORTANT :
            #
            # reranker_score sert uniquement au classement.
            #
            # Le score de preuve retourné à LangGraph est le
            # hybrid_score .
            candidates_with_scores = [
                (
                    row,
                    float(
                        row.get(
                            "hybrid_score",
                            0.0,
                        )
                    ),
                )
                for row, _reranker_score
                in ranked_candidates
            ]

        else:

            candidates_with_scores = [
                (
                    row,
                    float(
                        row.get(
                            "hybrid_score",
                            0.0,
                        )
                    ),
                )
                for row in candidates[:k]
            ]

        # ---------------------------------------------------------
        # 4. Conversion vers le modèle Evidence
        # ---------------------------------------------------------

        evidence = []

        for row, evidence_score in candidates_with_scores:

            evidence.append(
                Evidence(
                    source_id=str(row["id"]),
                    title=row["title"],
                    section=row["section"],
                    source_path=row["source_path"],
                    url=row["source_url"],
                    text=row["content"],
                    score=evidence_score,
                )
            )

        return evidence

    def get_source(
        self,
        source_id: str,
    ) -> Evidence:
        """
        Récupère un passage précis à partir de son identifiant.
        """

        response = (
            self.client
            .table("documents")
            .select(
                "id,"
                "title,"
                "section,"
                "source_path,"
                "source_url,"
                "content"
            )
            .eq(
                "id",
                source_id,
            )
            .single()
            .execute()
        )

        row = response.data

        if not row:
            raise ValueError(
                f"Source introuvable : {source_id}"
            )

        return Evidence(
            source_id=str(row["id"]),
            title=row["title"],
            section=row["section"],
            source_path=row["source_path"],
            url=row["source_url"],
            text=row["content"],
            score=1.0,
        )

    def compare(
        self,
        subject: str,
        option1: str,
        option2: str,
        k: int = 4,
    ) -> dict[str, list[Evidence]]:
        """
        Recherche séparément les preuves pour deux options.

        Exemple :
            compare(
                "architecture analytique",
                "Warehouse",
                "Lakehouse",
            )
        """

        option1_results = self.search(
            query=f"{subject} {option1}",
            k=k,
        )

        option2_results = self.search(
            query=f"{subject} {option2}",
            k=k,
        )

        return {
            option1: option1_results,
            option2: option2_results,
        }


# Alias conservé pour éviter de casser les anciens imports
# du projet.
HybridRetriever = SupabaseRetriever