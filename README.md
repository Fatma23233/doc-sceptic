# 🔎 Doc-Sceptic

### Evidence-grounded Microsoft Fabric Architecture Advisor

Doc-Sceptic est un assistant RAG orienté Microsoft Fabric qui aide à choisir une architecture à partir de documentation technique indexée.

L'objectif n'est pas simplement de générer une réponse plausible.

Doc-Sceptic cherche d'abord des preuves, les évalue, puis choisit entre trois comportements :

- ✅ recommander ;
- ❓ demander une clarification ;
- 🛑 s'abstenir lorsque les preuves sont insuffisantes.

---

## 🎯 Pourquoi ce projet ?

Une recommandation d'architecture générée par un LLM peut sembler crédible tout en étant mal documentée.

Doc-Sceptic ajoute une couche de contrôle entre la recherche documentaire et la génération :

Question utilisateur  
→ extraction des contraintes  
→ recherche documentaire  
→ reranking  
→ validation des preuves  
→ décision  
→ réponse sourcée.

L'agent peut donc refuser de répondre lorsque les documents récupérés ne permettent pas de soutenir suffisamment la recommandation.

---

## ✨ Fonctionnalités

### 🔍 RAG documentaire

La documentation Microsoft Fabric est découpée en chunks, vectorisée puis stockée dans Supabase avec pgvector.

### 🧠 Recherche et reranking

Le pipeline récupère plusieurs passages candidats avant de conserver les preuves les plus pertinentes.

### 🧭 Détection du contexte

Doc-Sceptic reconnaît notamment :

- Warehouse / Lakehouse
- Data Engineering
- Spark / PySpark
- Data Factory
- Power BI / Direct Lake
- architecture Medallion
- SQL Database / OLTP

### 🛡️ Abstention

L'agent peut retourner une abstention plutôt que produire une réponse insuffisamment documentée.

### ❓ Clarification

Lorsque la question ne contient pas assez de contraintes pour effectuer un choix architectural, Doc-Sceptic demande les informations manquantes.

### 📚 Citations

Les affirmations techniques sont reliées aux passages récupérés :

[S1] [S2] [S3]

Les références sont ensuite présentées avec leurs sources.

### 💬 Conversation naturelle

Les messages conversationnels simples sont traités sans déclencher inutilement le RAG.

Exemples :

"Bonjour"

"Comment allez-vous ?"

"Merci"

"Que peux-tu faire ?"

---

## 🏗️ Architecture

```mermaid
flowchart TD
    U[Utilisateur] --> UI[Interface Streamlit]

    UI --> A[LangGraph Agent]

    A --> C{Type de message}

    C -->|Conversation| CHAT[Réponse locale]
    C -->|Question Fabric| ANALYZE[Analyse des contraintes]

    ANALYZE --> RETRIEVE[Recherche documentaire]

    RETRIEVE --> DB[(Supabase + pgvector)]

    DB --> RERANK[Reranking]

    RERANK --> ASSESS{Validation des preuves}

    ASSESS -->|Insuffisantes| ABSTAIN[Abstention]
    ASSESS -->|Question ambiguë| CLARIFY[Clarification]
    ASSESS -->|Suffisantes| LLM[LLM]

    LLM --> CITE[Validation / normalisation des citations]
    CITE --> ANSWER[Réponse sourcée]