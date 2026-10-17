from doc_sceptic.agent import DataArchitectureAgent
from doc_sceptic.schemas import Evidence, Requirements


def evidence(text: str, score: float = 0.24, title: str = "decision-guide-lakehouse-warehouse"):
    return Evidence(
        source_id="1",
        title=title,
        section="Evaluate each service",
        source_path="fundamentals/decision-guide-lakehouse-warehouse.md",
        url="https://example.test",
        text=text,
        score=score,
    )


def agent_without_init():
    agent = object.__new__(DataArchitectureAgent)
    agent.s = type("S", (), {"min_evidence_score": 0.35, "top_k": 6})()
    return agent


def test_direct_multi_table_evidence_prevents_false_abstention():
    agent = agent_without_init()
    state = {
        "requirements": Requirements(multi_table_transactions=True),
        "domain": "warehouse_lakehouse",
        "evidence": [
            evidence(
                "The Warehouse provides full multi-table ACID transactions through the SQL engine."
            )
        ],
        "trace": [],
    }
    result = agent.assess(state)
    assert result["action"] == "answer"


def test_data_factory_requires_domain_specific_document():
    agent = agent_without_init()
    state = {
        "requirements": Requirements(),
        "domain": "data_factory",
        "evidence": [
            evidence(
                "Warehouse supports T-SQL and Power BI.",
                score=0.60,
                title="decision-guide-lakehouse-warehouse",
            )
        ],
        "trace": [],
    }
    result = agent.assess(state)
    assert result["action"] == "abstain"
