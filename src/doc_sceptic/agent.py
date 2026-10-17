from __future__ import annotations

import re
import unicodedata
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from supabase import Client

from .config import Settings
from .llm import LLMClient
from .retrieval import SupabaseRetriever
from .schemas import AgentAnswer, Evidence, Requirements


class State(TypedDict, total=False):
    question: str
    requirements: Requirements
    query: str
    domain: str
    evidence: list[Evidence]
    accepted_evidence: list[Evidence]
    action: str
    answer: str
    confidence: float
    trace: list[str]


class DataArchitectureAgent:
    """Agent Fabric avec recherche enrichie, validation de couverture et abstention."""

    GREETINGS = {
        "bonjour",
        "bonsoir",
        "salut",
        "hello",
        "hi",
        "hey",
        "coucou",
    }

    IDENTITY_PATTERNS = (
        "qui es-tu",
        "qui es tu",
        "tu es qui",
        "que fais-tu",
        "que fais tu",
        "qu'est-ce que tu fais",
        "qu est ce que tu fais",
        "c'est quoi doc-sceptic",
        "c est quoi doc-sceptic",
        "présente-toi",
        "presente-toi",
        "comment peux-tu m'aider",
        "comment peux tu m aider",
        "à quoi sers-tu",
        "a quoi sers-tu",
    )

    HELP_PATTERNS = (
        "aide",
        "help",
        "exemples de questions",
        "que puis-je demander",
        "que puis je demander",
        "que peux-tu faire",
        "que peux tu faire",
    )

    FRIENDLY_PATTERNS = (
        "comment allez-vous",
        "comment allez vous",
        "comment vas-tu",
        "comment vas tu",
        "ça va",
        "ca va",
        "comment se passe votre journée",
        "comment se passe votre journee",
        "merci",
        "merci beaucoup",
        "je vous remercie",
        "super",
        "parfait",
        "très bien",
        "tres bien",
        "d'accord",
        "d accord",
        "ok",
        "okay",
        "au revoir",
        "à bientôt",
        "a bientot",
        "bonne journée",
        "bonne journee",
        "bonne soirée",
        "bonne soiree",
        "bonne nuit",
    )

    def __init__(
        self,
        settings: Settings | None = None,
        db_client: Client | None = None,
    ):
        self.s = settings or Settings()
        self.retriever = SupabaseRetriever(self.s, db_client)
        self.llm = LLMClient(self.s)
        self.graph = self._build()

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize("NFKD", text.lower())
        text = "".join(
            char
            for char in text
            if not unicodedata.combining(char)
        )
        text = re.sub(r"[-‐‑‒–—]", " ", text)
        text = re.sub(r"[^a-z0-9+.# ]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _normalize_citations(answer: str, source_count: int) -> str:
        """Normalise les citations vers le format [S1], [S2], etc."""
        if not answer:
            return answer

        text = answer.replace(r"\[", "[").replace(r"\]", "]")

        # Normaliser les citations S déjà entourées de crochets.
        text = re.sub(
            r"\[\s*S\s*(\d+)\s*\]",
            lambda match: f"[S{match.group(1)}]",
            text,
            flags=re.IGNORECASE,
        )

        # Supprimer les références parasites T1, [T1], T4], etc.
        text = re.sub(
            r"\[\s*T\s*\d+\s*\]",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(?<!\[)\bT\d+\s*\]",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # Réparer les citations sans crochet ouvrant : S1] -> [S1].
        text = re.sub(
            r"(?<!\[)\bS(\d+)\s*\]",
            lambda match: f"[S{match.group(1)}]",
            text,
            flags=re.IGNORECASE,
        )

        # Supprimer les citations qui ne correspondent à aucune preuve fournie.
        def validate_citation(match: re.Match[str]) -> str:
            index = int(match.group(1))
            if 1 <= index <= source_count:
                return f"[S{index}]"
            return ""

        text = re.sub(
            r"\[S(\d+)\]",
            validate_citation,
            text,
            flags=re.IGNORECASE,
        )

        # Supprimer les répétitions immédiates : [S1][S1] -> [S1].
        text = re.sub(
            r"(\[S\d+\])(?:\s*\1)+",
            r"\1",
            text,
            flags=re.IGNORECASE,
        )

        # Nettoyer uniquement les espaces horizontaux créés par les suppressions.
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    def _casual_answer(self, question: str) -> str | None:
        normalized = self._normalize(question)
        words = set(normalized.split())

        greeting_present = bool(words.intersection(self.GREETINGS))
        friendly_present = any(
            pattern in normalized
            for pattern in map(self._normalize, self.FRIENDLY_PATTERNS)
        )

        wellbeing_patterns = (
            "comment allez vous",
            "comment vas tu",
            "ca va",
            "comment se passe votre journee",
        )
        wellbeing_present = any(
            pattern in normalized
            for pattern in wellbeing_patterns
        )

        # Une salutation ou une petite conversation doit rester locale :
        # aucun appel Supabase, aucun RAG et aucune source affichée.
        if greeting_present and (len(words) <= 3 or friendly_present):
            if wellbeing_present:
                return (
                    "Bonjour 🙂 Merci de demander. Je vais bien et je suis là pour "
                    "t’aider. Tu peux me parler naturellement, me décrire ton projet "
                    "ou me poser une question sur Microsoft Fabric."
                )
            return (
                "Bonjour 🙂 Je suis **Doc-Sceptic**. Je suis là pour t’aider. "
                "Tu peux me parler naturellement ou me poser une question sur "
                "Microsoft Fabric."
            )

        if normalized in self.GREETINGS:
            return (
                "Bonjour 🙂 Je suis **Doc-Sceptic**. Je suis là pour t’aider. "
                "Tu peux me parler naturellement ou me poser une question sur "
                "Microsoft Fabric."
            )

        if any(
            pattern in normalized
            for pattern in map(self._normalize, self.IDENTITY_PATTERNS)
        ):
            return (
                "Je suis **Doc-Sceptic**, un assistant de décision pour Microsoft "
                "Fabric. J’analyse les contraintes de ton projet, je recherche les "
                "passages pertinents dans la documentation indexée, puis je recommande "
                "une architecture seulement lorsque les preuves sont suffisantes."
            )

        if any(
            pattern in normalized
            for pattern in map(self._normalize, self.HELP_PATTERNS)
        ):
            return (
                "Bien sûr 🙂 Tu peux me demander de comparer Warehouse et Lakehouse, "
                "de proposer une architecture medallion, ou d’analyser un scénario "
                "SQL, Spark, Power BI ou Data Factory. Si ta question manque de "
                "contexte, je te demanderai simplement les précisions utiles."
            )

        if friendly_present:
            if "merci" in normalized or "je vous remercie" in normalized:
                return "Avec plaisir 🙂 Je suis là si tu veux continuer."

            if any(
                expression in normalized
                for expression in (
                    "au revoir",
                    "a bientot",
                    "bonne journee",
                    "bonne soiree",
                    "bonne nuit",
                )
            ):
                return "À bientôt 🙂 On reprendra quand tu veux."

            if normalized in {
                "super",
                "parfait",
                "tres bien",
                "ok",
                "okay",
                "d accord",
            }:
                return "D’accord 🙂 On continue quand tu veux."

            if wellbeing_present:
                return (
                    "Merci de demander 🙂 Je vais bien et je suis là pour t’aider. "
                    "Tu peux continuer naturellement ou me poser une question sur "
                    "Microsoft Fabric."
                )

        return None

    @staticmethod
    def _detect_domain(question: str) -> str:
        low = question.lower()

        if "data factory" in low or re.search(r"\badf\b", low):
            return "data_factory"

        if any(term in low for term in ["bronze", "silver", "gold", "medallion"]):
            return "medallion"

        if any(
            term in low
            for term in [
                "oltp",
                "base relationnelle normalisée",
                "base relationnelle normalisee",
                "sql database",
            ]
        ):
            return "fabric_general"

        explicit_warehouse_lakehouse = (
            "warehouse ou lakehouse" in low
            or ("warehouse" in low and "lakehouse" in low)
            or "transaction" in low
            or "multi-table" in low
            or "multi table" in low
            or "plusieurs tables" in low
            or "t-sql" in low
            or "tsql" in low
            or "données structurées" in low
            or "donnees structurees" in low
            or "entrepôt" in low
            or "entrepot" in low
        )
        if explicit_warehouse_lakehouse:
            return "warehouse_lakehouse"

        if any(
            term in low
            for term in ["spark", "pyspark", "notebook", "scala", "data engineering"]
        ):
            return "data_engineering"

        if any(
            term in low
            for term in [
                "direct lake",
                "power bi",
                "semantic model",
                "modèle sémantique",
                "modele semantique",
            ]
        ):
            return "power_bi"

        if "warehouse" in low or "lakehouse" in low:
            return "warehouse_lakehouse"

        return "fabric_general"

    @staticmethod
    def _build_search_query(
        question: str,
        requirements: Requirements,
        domain: str,
    ) -> str:
        """Ajoute le vocabulaire anglais de la documentation sans remplacer la question."""
        additions: list[str] = []

        if requirements.multi_table_transactions:
            additions.extend(
                [
                    "Warehouse",
                    "full multi-table ACID transactions",
                    "SQL engine",
                    "stored procedures",
                ]
            )
        if "T-SQL" in requirements.development_styles:
            additions.extend(["T-SQL", "Warehouse", "SQL-first"])
        if "Spark" in requirements.development_styles:
            additions.extend(
                ["Apache Spark", "PySpark", "Lakehouse", "Data Engineering"]
            )
        if "structured" in requirements.data_types:
            additions.append("structured data")
        if "unstructured" in requirements.data_types or requirements.unstructured_data:
            additions.extend(["unstructured data", "Lakehouse"])
        if requirements.power_bi:
            additions.extend(["Power BI", "Direct Lake", "SQL analytics endpoint"])
        if requirements.streaming:
            additions.extend(
                ["streaming", "Spark Structured Streaming", "Eventstream"]
            )

        domain_terms = {
            "data_factory": [
                "Fabric Data Factory",
                "Azure Data Factory comparison",
                "pipeline",
                "Dataflow Gen2",
                "connections",
                "migration planning",
            ],
            "medallion": [
                "medallion architecture",
                "bronze silver gold",
                "OneLake",
                "Lakehouse",
            ],
            "power_bi": ["Power BI", "Direct Lake", "semantic model"],
            "warehouse_lakehouse": [
                "Warehouse Lakehouse decision guide",
                "multi-table transactions",
            ],
            "data_engineering": ["Fabric Data Engineering", "Lakehouse", "Spark"],
        }
        additions.extend(domain_terms.get(domain, []))

        unique = list(dict.fromkeys(additions))
        return f"{question}\nDocumentation keywords: {'; '.join(unique)}"

    def analyze(self, state: State) -> State:
        question = state["question"].strip()
        casual_answer = self._casual_answer(question)

        if casual_answer:
            return {
                "requirements": Requirements(),
                "domain": "chat",
                "action": "chat",
                "answer": casual_answer,
                "confidence": 1.0,
                "trace": ["Message conversationnel détecté."],
            }

        low = question.lower()

        unsupported_request = any(
            pattern in low
            for pattern in [
                "coûtera exactement",
                "coutera exactement",
                "garantis-moi",
                "garantis moi",
                "n'aura jamais de panne",
                "latence exacte en millisecondes",
            ]
        )
        if unsupported_request:
            return {
                "requirements": Requirements(),
                "domain": self._detect_domain(question),
                "action": "abstain",
                "confidence": 0.0,
                "trace": [
                    "Demande de coût, garantie ou performance exacte non démontrable."
                ],
            }

        requirements = Requirements(
            data_types=[
                item
                for item in [
                    "structured"
                    if any(term in low for term in ["structur", "relationnel", "sql"])
                    else "",
                    "unstructured"
                    if any(
                        term in low
                        for term in [
                            "non structuré",
                            "non structure",
                            "unstructured",
                            "json",
                        ]
                    )
                    else "",
                ]
                if item
            ],
            development_styles=[
                item
                for item in [
                    "T-SQL" if "t-sql" in low or "tsql" in low else "",
                    "Spark"
                    if any(term in low for term in ["spark", "pyspark", "scala"])
                    else "",
                ]
                if item
            ],
            multi_table_transactions=(
                True
                if "transaction" in low
                and any(
                    term in low
                    for term in ["multi-table", "multi table", "plusieurs table"]
                )
                else None
            ),
            power_bi=True if "power bi" in low else None,
            streaming=(
                True
                if any(
                    term in low
                    for term in ["stream", "temps réel", "temps reel", "real-time"]
                )
                else None
            ),
            unstructured_data=(
                True
                if any(
                    term in low
                    for term in ["non structuré", "non structure", "unstructured"]
                )
                else None
            ),
        )

        domain = self._detect_domain(question)

        vague_choice = (
            domain != "medallion"
            and any(
                term in low
                for term in ["warehouse ou lakehouse", "quelle architecture"]
            )
            and not any(
                [
                    requirements.data_types,
                    requirements.development_styles,
                    requirements.multi_table_transactions,
                    requirements.power_bi,
                    requirements.streaming,
                ]
            )
        )

        if vague_choice:
            requirements.missing_constraints = [
                "type de données",
                "style de développement SQL ou Spark",
                "besoin de transactions multi-tables",
                "usage analytique ou Power BI",
            ]

        query = self._build_search_query(question, requirements, domain)

        return {
            "requirements": requirements,
            "domain": domain,
            "query": query,
            "action": "clarify" if requirements.missing_constraints else "search",
            "trace": [f"Contraintes extraites. Domaine : {domain}."],
        }

    def route_analyze(self, state: State) -> str:
        if state["action"] == "chat":
            return "chat"
        if state["action"] == "clarify":
            return "clarify"
        if state["action"] == "abstain":
            return "abstain"
        return "retrieve"

    def chat(self, state: State) -> State:
        return {
            "answer": state["answer"],
            "confidence": 1.0,
            "trace": state["trace"] + ["Réponse conversationnelle générée localement."],
        }

    def clarify(self, state: State) -> State:
        missing = state["requirements"].missing_constraints
        return {
            "answer": "Pour recommander sans deviner, précise : "
            + ", ".join(missing)
            + ".",
            "confidence": 1.0,
            "trace": state["trace"] + ["Clarification demandée."],
        }

    def retrieve(self, state: State) -> State:
        evidence = self.retriever.search(state["query"], max(self.s.top_k, 10))

        deduplicated: dict[str, Evidence] = {}
        for item in evidence:
            key = self._normalize(f"{item.title}|{item.section}|{item.text[:240]}")
            previous = deduplicated.get(key)
            if previous is None or item.score > previous.score:
                deduplicated[key] = item

        final_evidence = sorted(
            deduplicated.values(),
            key=lambda item: item.score,
            reverse=True,
        )[: self.s.top_k]

        return {
            "evidence": final_evidence,
            "trace": state["trace"]
            + [f"{len(final_evidence)} preuves uniques récupérées depuis Supabase."],
        }

    @staticmethod
    def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
        return any(term in text for term in terms)

    def _evidence_supports_requirement(
        self,
        evidence: Evidence,
        requirement_name: str,
    ) -> bool:
        text = self._normalize(
            f"{evidence.title} {evidence.section} {evidence.source_path} {evidence.text}"
        )

        checks = {
            "multi_table_transactions": (
                self._contains_any(
                    text,
                    (
                        "multi table acid transaction",
                        "multi table transaction",
                        "transactions multi tables",
                        "transaction sur plusieurs tables",
                    ),
                )
                and self._contains_any(text, ("warehouse", "entrepot"))
            ),
            "t_sql": self._contains_any(text, ("t sql", "tsql")),
            "spark": self._contains_any(text, ("apache spark", "pyspark", "spark")),
            "structured": self._contains_any(
                text,
                ("structured data", "donnees structurees"),
            ),
            "unstructured": self._contains_any(
                text,
                ("unstructured data", "donnees non structurees"),
            ),
            "power_bi": self._contains_any(text, ("power bi", "direct lake")),
            "streaming": self._contains_any(
                text,
                ("streaming", "eventstream", "write stream"),
            ),
        }
        return bool(checks.get(requirement_name, False))

    @staticmethod
    def _domain_document_matches(domain: str, evidence: Evidence) -> bool:
        haystack = f"{evidence.title} {evidence.source_path} {evidence.section}".lower()
        expected = {
            "data_factory": (
                "data-factory",
                "data factory",
                "pipeline",
                "dataflow",
                "copy activity",
            ),
            "medallion": (
                "medallion",
                "bronze",
                "silver",
                "gold",
                "data-engineering",
                "lakehouse",
                "delta",
            ),
            "power_bi": ("power-bi", "power bi", "direct-lake", "direct lake"),
            "warehouse_lakehouse": (
                "warehouse",
                "lakehouse",
                "decision-guide-data-store",
            ),
            "data_engineering": ("data-engineering", "lakehouse", "spark"),
            "fabric_general": ("fabric",),
        }
        return any(term in haystack for term in expected.get(domain, ()))

    def assess(self, state: State) -> State:
        evidence = state.get("evidence", [])
        requirements = state["requirements"]
        domain = state.get("domain", "fabric_general")

        if not evidence:
            return {
                "accepted_evidence": [],
                "action": "abstain",
                "confidence": 0.0,
                "trace": state["trace"] + ["Aucune preuve récupérée."],
            }

        required_signals: list[str] = []
        if requirements.multi_table_transactions:
            required_signals.append("multi_table_transactions")
        if "T-SQL" in requirements.development_styles:
            required_signals.append("t_sql")
        if "Spark" in requirements.development_styles:
            required_signals.append("spark")
        if "structured" in requirements.data_types:
            required_signals.append("structured")
        if "unstructured" in requirements.data_types or requirements.unstructured_data:
            required_signals.append("unstructured")
        if requirements.power_bi:
            required_signals.append("power_bi")
        if requirements.streaming:
            required_signals.append("streaming")

        directly_supported = {
            signal: any(
                self._evidence_supports_requirement(item, signal)
                for item in evidence
            )
            for signal in required_signals
        }

        coverage = (
            sum(directly_supported.values()) / len(directly_supported)
            if directly_supported
            else 1.0
        )
        best_score = max(item.score for item in evidence)
        domain_match = any(
            self._domain_document_matches(domain, item)
            for item in evidence
        )

        accepted = [
            item
            for item in evidence
            if self._domain_document_matches(domain, item)
            or any(
                self._evidence_supports_requirement(item, signal)
                for signal in required_signals
            )
        ]
        accepted = sorted(
            accepted,
            key=lambda item: item.score,
            reverse=True,
        )[: self.s.top_k]

        direct_transaction_support = directly_supported.get(
            "multi_table_transactions",
            False,
        )

        normal_pass = (
            best_score >= self.s.min_evidence_score
            and coverage >= 0.5
            and domain_match
        )

        transaction_pass = (
            requirements.multi_table_transactions is True
            and direct_transaction_support
            and best_score >= max(0.18, self.s.min_evidence_score * 0.5)
        )

        sufficient = bool(accepted) and (normal_pass or transaction_pass)

        trace = state["trace"] + [
            f"Score max={best_score:.3f}; couverture={coverage:.2f}; "
            f"document du domaine={domain_match}; preuve transactionnelle="
            f"{direct_transaction_support}."
        ]
        trace.append("Preuves suffisantes." if sufficient else "Preuves insuffisantes.")

        return {
            "accepted_evidence": accepted,
            "action": "answer" if sufficient else "abstain",
            "confidence": best_score if sufficient else 0.0,
            "trace": trace,
        }

    def route_assess(self, state: State) -> str:
        return "generate" if state["action"] == "answer" else "abstain"

    def generate(self, state: State) -> State:
        evidence = state.get("accepted_evidence") or state.get("evidence", [])
        context = "\n\n".join(
            f"[S{index}] {item.title} > {item.section}\n{item.text}"
            for index, item in enumerate(evidence, 1)
        )

        prompt = (
            f"QUESTION:\n{state['question']}\n\n"
            f"CONTRAINTES EXTRAITES:\n{state['requirements'].model_dump_json()}\n\n"
            f"PREUVES AUTORISÉES:\n{context}"
        )

        system = (
            "Tu es Doc-Sceptic, un conseiller d'architecture Microsoft Fabric. "
            "Réponds en français uniquement à partir des PREUVES AUTORISÉES. "
            "RÈGLE ABSOLUE : chaque affirmation factuelle ou technique doit être "
            "directement et explicitement présente dans au moins une preuve. "
            "Place une citation immédiatement après chaque affirmation factuelle. "
            "Utilise uniquement le format exact [S1], [S2], [S1][S3], etc. "
            "N'utilise jamais T1, [T1], S1] ou toute autre forme de citation. "
            "N'utilise aucune connaissance externe. "
            "Ne complète jamais les preuves avec tes connaissances générales. "
            "N'invente ni capacité, ni limitation, ni coût, ni performance, "
            "ni garantie, ni procédure. "
            "COUVERTURE DE LA QUESTION : identifie tous les éléments explicitement "
            "demandés. Si les PREUVES AUTORISÉES contiennent des informations sur "
            "ces éléments, traite chacun d'eux dans la réponse. "
            "Ne réponds pas uniquement au premier aspect bien documenté. "
            "Si un élément demandé n'est pas documenté dans les PREUVES AUTORISÉES, "
            "indique explicitement que les preuves sélectionnées ne permettent pas "
            "de répondre à cet élément. "
            "Si une information n'est pas explicitement supportée par les preuves, "
            "ne la mentionne pas. "
            "Structure la réponse avec exactement trois parties : "
            "Faits établis, Recommandation, Limites documentées. "
            "Si aucune limite pertinente n'est explicitement présente dans les preuves, "
            "écris : 'Les preuves sélectionnées ne documentent pas de limite "
            "pertinente pour cette question.' "
            "Reste concis."
        )

        answer = self.llm.complete(system, prompt, temperature=0.0)
        if not answer or not answer.strip():
            raise RuntimeError(
                "Le LLM a retourné une réponse vide alors que "
                "les preuves avaient été validées."
            )

        answer = self._normalize_citations(
            answer,
            source_count=len(evidence),
        )

        return {
            "answer": answer,
            "evidence": evidence,
            "confidence": state.get("confidence", 0.0),
            "trace": state["trace"]
            + ["Réponse produite à partir des preuves filtrées."],
        }

    def abstain(self, state: State) -> State:
        return {
            "answer": (
                "Je ne dispose pas de preuves documentaires suffisamment directes "
                "pour répondre sans risque d’inventer. Précise le workload Fabric, "
                "les outils utilisés et la contrainte principale."
            ),
            "confidence": 0.0,
            "trace": state["trace"] + ["Abstention déclenchée."],
        }

    def _build(self):
        graph = StateGraph(State)
        for name, function in [
            ("analyze", self.analyze),
            ("chat", self.chat),
            ("clarify", self.clarify),
            ("retrieve", self.retrieve),
            ("assess", self.assess),
            ("generate", self.generate),
            ("abstain", self.abstain),
        ]:
            graph.add_node(name, function)

        graph.add_edge(START, "analyze")
        graph.add_conditional_edges(
            "analyze",
            self.route_analyze,
            {
                "chat": "chat",
                "clarify": "clarify",
                "abstain": "abstain",
                "retrieve": "retrieve",
            },
        )
        graph.add_edge("chat", END)
        graph.add_edge("clarify", END)
        graph.add_edge("retrieve", "assess")
        graph.add_conditional_edges(
            "assess",
            self.route_assess,
            {"generate": "generate", "abstain": "abstain"},
        )
        graph.add_edge("generate", END)
        graph.add_edge("abstain", END)
        return graph.compile()

    def ask(self, question: str) -> AgentAnswer:
        state = self.graph.invoke({"question": question})

        if state.get("action") == "chat":
            action = "chat"
        elif state.get("action") == "clarify":
            action = "clarify"
        elif state.get("action") == "abstain":
            action = "abstain"
        else:
            action = "recommend"

        return AgentAnswer(
            action=action,
            answer=state["answer"],
            requirements=state["requirements"],
            citations=state.get("accepted_evidence") or state.get("evidence", []),
            confidence=state.get("confidence", 0.0),
            trace=state.get("trace", []),
        )
