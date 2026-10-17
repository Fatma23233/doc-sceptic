from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from doc_sceptic.agent import DataArchitectureAgent


# -----------------------------------------------------------------------------
# Text helpers
# -----------------------------------------------------------------------------


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[-‐‑‒–—]", " ", text)
    text = re.sub(r"[^a-z0-9+.# ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_all(text: str, terms: list[str]) -> bool:
    haystack = normalize(text)
    return all(normalize(term) in haystack for term in terms)


def determine_choice(answer: str) -> str:
    text = normalize(answer)

    # Evaluate the recommendation block first so facts that merely compare
    # several products do not automatically become a hybrid recommendation.
    if "recommandation" in text:
        recommendation = text.split("recommandation", 1)[1]
        if "limites documentees" in recommendation:
            recommendation = recommendation.split("limites documentees", 1)[0]
    else:
        recommendation = text

    if "data factory" in recommendation:
        return "data_factory"

    if any(
        term in recommendation
        for term in [
            "sql database",
            "base de donnees sql",
            "sql database in fabric",
        ]
    ):
        return "sql_database"

    has_warehouse = any(
        term in recommendation
        for term in ["warehouse", "data warehouse", "fabric warehouse"]
    )
    has_lakehouse = "lakehouse" in recommendation

    hybrid_phrases = [
        "combiner",
        "combinaison",
        "architecture hybride",
        "utiliser les deux",
        "associer",
        "ensemble",
    ]

    if (
        has_warehouse
        and has_lakehouse
        and any(phrase in recommendation for phrase in hybrid_phrases)
    ):
        return "hybrid"

    # Explicit recommendation has priority even when the paragraph later
    # mentions the alternative as an optional complementary component.
    warehouse_preference_patterns = [
        "warehouse est le choix le plus adapte",
        "warehouse est le choix le plus approprié",
        "warehouse est le choix le plus approprie",
        "privilegiez le warehouse",
        "privilegiez warehouse",
        "recommande le warehouse",
        "recommande fabric warehouse",
    ]
    lakehouse_preference_patterns = [
        "lakehouse est le choix le plus adapte",
        "lakehouse est le choix le plus approprié",
        "lakehouse est le choix le plus approprie",
        "privilegiez le lakehouse",
        "privilegiez lakehouse",
        "recommande le lakehouse",
        "recommande fabric lakehouse",
    ]

    if any(pattern in recommendation for pattern in warehouse_preference_patterns):
        return "warehouse"
    if any(pattern in recommendation for pattern in lakehouse_preference_patterns):
        return "lakehouse"

    if has_warehouse and not has_lakehouse:
        return "warehouse"

    if has_lakehouse and not has_warehouse:
        return "lakehouse"

    warehouse_patterns = [
        "recommande fabric warehouse",
        "recommande le fabric warehouse",
        "recommande un warehouse",
        "utilisez fabric warehouse",
        "utilisez le fabric warehouse",
        "privilegier warehouse",
        "privilegiez warehouse",
    ]
    lakehouse_patterns = [
        "recommande fabric lakehouse",
        "recommande le fabric lakehouse",
        "recommande un lakehouse",
        "utilisez fabric lakehouse",
        "utilisez le fabric lakehouse",
        "privilegier lakehouse",
        "privilegiez lakehouse",
    ]

    if any(pattern in recommendation for pattern in warehouse_patterns):
        return "warehouse"
    if any(pattern in recommendation for pattern in lakehouse_patterns):
        return "lakehouse"

    return "unknown"


def infer_domain(agent: DataArchitectureAgent, question: str, action: str) -> str:
    # Conversational messages are routed before retrieval and therefore belong
    # to the chat domain even though _detect_domain alone may return general.
    if action == "chat":
        return "chat"

    detect = getattr(agent, "_detect_domain", None)
    if callable(detect):
        return str(detect(question))
    return "unknown"


def sources_match(citations, terms: list[str]) -> bool:
    if not terms:
        return True

    corpus_text = " ".join(
        f"{citation.title} {citation.section} {citation.source_path}"
        for citation in citations
    )
    corpus_text = normalize(corpus_text)

    # At least one expected domain signal must be represented by the citations.
    return any(normalize(term) in corpus_text for term in terms)


def has_inline_citations(answer: str) -> bool:
    return bool(re.search(r"\[S\d+\]", answer or ""))


# -----------------------------------------------------------------------------
# HTTP retry helpers
# -----------------------------------------------------------------------------


def parse_retry_after(error: requests.HTTPError) -> float | None:
    response = getattr(error, "response", None)
    if response is None:
        return None

    value = response.headers.get("retry-after")
    if value is None:
        return None

    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def is_retryable_http_error(error: requests.HTTPError) -> bool:
    response = getattr(error, "response", None)
    if response is None:
        return False
    return response.status_code in {429, 500, 502, 503, 504}


def call_agent_with_retry(
    agent: DataArchitectureAgent,
    question: str,
    max_retries: int,
    base_delay: float,
):
    attempts = 0

    while True:
        attempts += 1
        try:
            return agent.ask(question), attempts

        except requests.HTTPError as error:
            if not is_retryable_http_error(error) or attempts > max_retries:
                raise

            response = error.response
            status = response.status_code if response is not None else "?"
            retry_after = parse_retry_after(error)

            if retry_after is None:
                wait_seconds = min(base_delay * (2 ** (attempts - 1)), 120.0)
            else:
                # Small margin prevents retrying exactly on the boundary.
                wait_seconds = retry_after + 1.0

            print(
                f"\n    HTTP {status}: attente de {wait_seconds:.1f}s "
                f"avant tentative {attempts + 1}/{max_retries + 1}...",
                flush=True,
            )
            time.sleep(wait_seconds)


# -----------------------------------------------------------------------------
# Case evaluation
# -----------------------------------------------------------------------------


def evaluate_case(
    agent: DataArchitectureAgent,
    case: dict,
    max_retries: int,
    base_delay: float,
) -> dict:
    started = time.perf_counter()

    result, attempts = call_agent_with_retry(
        agent=agent,
        question=case["question"],
        max_retries=max_retries,
        base_delay=base_delay,
    )

    elapsed = time.perf_counter() - started
    answer = result.answer or ""

    actual_domain = infer_domain(agent, case["question"], result.action)
    actual_choice = determine_choice(answer)

    action_ok = result.action == case["expected_action"]
    domain_ok = actual_domain == case["expected_domain"]

    expected_choice = case.get("expected_choice", "none")
    if expected_choice in {"none", "any_grounded"}:
        choice_ok = True
    else:
        choice_ok = actual_choice == expected_choice

    answer_terms_ok = contains_all(
        answer,
        case.get("required_answer_terms", []),
    )
    source_domain_ok = sources_match(
        result.citations,
        case.get("expected_source_terms", []),
    )

    should_have_sources = case["expected_action"] == "recommend"
    sources_present_ok = bool(result.citations) if should_have_sources else True
    inline_citations_ok = has_inline_citations(answer) if should_have_sources else True

    checks = {
        "action": action_ok,
        "domain": domain_ok,
        "choice": choice_ok,
        "answer_terms": answer_terms_ok,
        "source_domain": source_domain_ok,
        "sources_present": sources_present_ok,
        "inline_citations": inline_citations_ok,
    }

    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "status": "evaluated",
        "expected": {
            "action": case["expected_action"],
            "choice": expected_choice,
            "domain": case["expected_domain"],
        },
        "actual": {
            "action": result.action,
            "choice": actual_choice,
            "domain": actual_domain,
            "confidence": result.confidence,
        },
        "checks": checks,
        "passed": all(checks.values()),
        "attempts": attempts,
        "elapsed_seconds": round(elapsed, 3),
        "answer": answer,
        "sources": [
            {
                "title": citation.title,
                "section": citation.section,
                "source_path": citation.source_path,
                "score": citation.score,
            }
            for citation in result.citations
        ],
        "trace": result.trace,
    }


def error_result(case: dict, error: Exception) -> dict:
    response = getattr(error, "response", None)
    http_status = getattr(response, "status_code", None)

    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "status": "error",
        "passed": False,
        "error": f"{type(error).__name__}: {error}",
        "http_status": http_status,
    }


# -----------------------------------------------------------------------------
# Reporting
# -----------------------------------------------------------------------------


def print_summary(results: list[dict]) -> None:
    evaluated = [item for item in results if item.get("status") == "evaluated"]
    errors = [item for item in results if item.get("status") == "error"]
    passed = [item for item in evaluated if item.get("passed")]
    failed = [item for item in evaluated if not item.get("passed")]

    print("\n" + "=" * 62)
    print(" DOC-SCEPTIC BENCHMARK")
    print("=" * 62)
    print(f"Cas demandés          : {len(results)}")
    print(f"Cas évalués           : {len(evaluated)}")
    print(f"Erreurs API           : {len(errors)}")
    print(f"Tests réussis         : {len(passed)}/{len(evaluated)}")

    if evaluated:
        score = len(passed) / len(evaluated) * 100
        print(f"Score évalué          : {score:.1f}%")
    else:
        print("Score évalué          : n/a")

    check_names = [
        "action",
        "domain",
        "choice",
        "answer_terms",
        "source_domain",
        "sources_present",
        "inline_citations",
    ]

    if evaluated:
        print("\nContrôles sur les cas évalués")
        for name in check_names:
            value = sum(1 for item in evaluated if item["checks"].get(name, False))
            print(f"{name:20}: {value}/{len(evaluated)}")

    print("\nPar catégorie")
    grouped = defaultdict(list)
    for item in results:
        grouped[item["category"]].append(item)

    for category, items in sorted(grouped.items()):
        category_evaluated = [
            item for item in items if item.get("status") == "evaluated"
        ]
        category_passed = [
            item for item in category_evaluated if item.get("passed")
        ]
        category_errors = len(items) - len(category_evaluated)
        print(
            f"  {category:22} "
            f"{len(category_passed)}/{len(category_evaluated)} évalués"
            f" | erreurs API={category_errors}"
        )

    if failed:
        print("\nÉchecs fonctionnels")
        for item in failed:
            failed_checks = [
                name for name, ok in item["checks"].items() if not ok
            ]
            print(
                f"  {item['id']}: {', '.join(failed_checks)} | "
                f"action={item['actual']['action']} | "
                f"choice={item['actual']['choice']} | "
                f"domain={item['actual']['domain']}"
            )

    if errors:
        print("\nErreurs API non évaluées")
        for item in errors:
            status = item.get("http_status")
            print(
                f"  {item['id']}: HTTP {status} | {item.get('error', '')}"
            )

    if not failed and not errors:
        print("\nTous les cas sont passés.")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Doc-Sceptic")
    parser.add_argument(
        "--benchmark",
        default="evaluation/benchmark.json",
    )
    parser.add_argument(
        "--output",
        default="evaluation/results/benchmark_results.json",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--category", default=None)
    parser.add_argument(
        "--pause",
        type=float,
        default=8.0,
        help="Pause en secondes entre deux cas évalués.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Nombre maximum de nouvelles tentatives après une erreur HTTP temporaire.",
    )
    parser.add_argument(
        "--base-delay",
        type=float,
        default=15.0,
        help="Attente initiale lorsque retry-after n'est pas fourni.",
    )
    args = parser.parse_args()

    benchmark_path = Path(args.benchmark)
    output_path = Path(args.output)

    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    cases = benchmark["cases"]

    if args.category:
        cases = [case for case in cases if case["category"] == args.category]
    if args.limit is not None:
        cases = cases[: args.limit]

    print(f"Benchmark : {benchmark.get('name', benchmark_path.name)}")
    print(f"Cas       : {len(cases)}")
    print(f"Pause     : {args.pause:.1f}s entre les cas")
    print(f"Retries   : {args.max_retries} maximum")
    print("Chargement de Doc-Sceptic...")

    # Reuse a single instance so embedding/reranking models load once.
    agent = DataArchitectureAgent()

    results: list[dict] = []

    for index, case in enumerate(cases, 1):
        print(
            f"[{index:02d}/{len(cases):02d}] {case['id']} ... ",
            end="",
            flush=True,
        )

        try:
            result = evaluate_case(
                agent=agent,
                case=case,
                max_retries=args.max_retries,
                base_delay=args.base_delay,
            )
            results.append(result)
            print("PASS" if result["passed"] else "FAIL")

        except Exception as error:
            result = error_result(case, error)
            results.append(result)
            print(f"ERROR ({type(error).__name__})")

        # Save progressively so interruption does not lose completed results.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        progressive_output = {
            "benchmark": benchmark.get("name"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "requested": len(cases),
            "completed": len(results),
            "results": results,
        }
        output_path.write_text(
            json.dumps(progressive_output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if index < len(cases) and args.pause > 0:
            time.sleep(args.pause)

    evaluated = [item for item in results if item.get("status") == "evaluated"]
    errors = [item for item in results if item.get("status") == "error"]
    passed = [item for item in evaluated if item.get("passed")]

    final_output = {
        "benchmark": benchmark.get("name"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "requested": len(results),
        "evaluated": len(evaluated),
        "api_errors": len(errors),
        "passed": len(passed),
        "evaluated_score_percent": (
            round(len(passed) / len(evaluated) * 100, 2)
            if evaluated
            else None
        ),
        "results": results,
    }

    output_path.write_text(
        json.dumps(final_output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print_summary(results)
    print(f"\nRésultats détaillés : {output_path}")

    # Functional failures do not represent a script execution error. API errors
    # are explicitly reported in the JSON and console summary.
    return 0


if __name__ == "__main__":
    sys.exit(main())
