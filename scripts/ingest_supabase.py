from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Sequence

from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from doc_sceptic.config import Settings
from doc_sceptic.corpus import build_chunks
from doc_sceptic.supabase_store import service_client


PRIORITY_DOCUMENTS = {
    "fundamentals/decision-guide-lakehouse-warehouse.md",
    "fundamentals/decision-guide-data-store.md",
    "data-engineering/lakehouse-overview.md",
    "data-engineering/data-engineering-overview.md",
    "data-factory/compare-fabric-data-factory-and-azure-data-factory.md",
}

PRIORITY_PATTERNS = (
    "data-factory/*migration*.md",
    "data-factory/*migrate*.md",
    "data-factory/*compare*.md",
    "data-factory/*dataflow*gen2*.md",
    "data-factory/*pipeline*.md",
    "data-factory/*connector*parity*.md",
)


def load_config(settings: Settings) -> dict:
    config_path = settings.root / "configs" / "corpus.json"
    return json.loads(config_path.read_text(encoding="utf-8"))


def relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def matches_any(value: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def selected_by_config(path: Path, root: Path, config: dict) -> bool:
    rel = relative_path(path, root)
    include_patterns = config.get("include", ["**/*.md"])
    exclude_patterns = config.get("exclude", [])
    included = matches_any(rel, include_patterns)
    excluded = matches_any(rel, exclude_patterns)
    return included and not excluded


def selected_as_priority(path: Path, root: Path) -> bool:
    rel = relative_path(path, root)
    return rel in PRIORITY_DOCUMENTS or matches_any(rel, PRIORITY_PATTERNS)


def select_files(all_files: list[Path], root: Path, config: dict) -> list[Path]:
    priority = sorted(
        path for path in all_files if selected_as_priority(path, root)
    )
    priority_set = set(priority)

    normal = sorted(
        path
        for path in all_files
        if path not in priority_set and selected_by_config(path, root, config)
    )

    max_files = int(config.get("max_files", 350))
    remaining_slots = max(0, max_files - len(priority))

    return priority + normal[:remaining_slots]


def main() -> None:
    settings = Settings()
    settings.validate_supabase(service=True)

    config = load_config(settings)
    root = settings.corpus_path

    if not root.exists():
        raise SystemExit(
            "Corpus absent. Lance python scripts/download_corpus.py"
        )

    all_files = sorted(
        path for path in root.rglob("*.md") if path.is_file()
    )

    print(f"Documents Markdown disponibles : {len(all_files)}")

    files = select_files(all_files, root, config)

    if not files:
        raise SystemExit("Aucun document sélectionné pour l'ingestion.")

    print(f"Documents sélectionnés : {len(files)}")

    data_factory_target = (
        "data-factory/"
        "compare-fabric-data-factory-and-azure-data-factory.md"
    )

    selected_paths = {
        relative_path(path, root) for path in files
    }

    data_factory_present = data_factory_target in selected_paths

    print(
        "Document Data Factory de comparaison sélectionné : "
        f"{data_factory_present}"
    )

    if not data_factory_present:
        raise SystemExit(
            "ERREUR : le document Data Factory prioritaire "
            "n'a pas été sélectionné."
        )

    selected_data_factory = sorted(
        path for path in selected_paths if path.startswith("data-factory/")
    )

    print(
        "Documents Data Factory sélectionnés : "
        f"{len(selected_data_factory)}"
    )

    for path in selected_data_factory:
        print(f"  - {path}")

    print("\nConstruction des chunks...")
    chunks = build_chunks(files, root)

    print(f"Chunks générés : {len(chunks)}")

    if not chunks:
        raise SystemExit("Aucun chunk généré.")

    print("\nChargement du modèle d'embedding...")
    model = SentenceTransformer(settings.embedding_model)

    database = service_client(settings)
    batch_size = settings.ingest_batch_size

    for start in tqdm(
        range(0, len(chunks), batch_size),
        desc="Supabase ingestion",
    ):
        batch_chunks = chunks[start : start + batch_size]

        embeddings = model.encode(
            [chunk.text for chunk in batch_chunks],
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

        payload = []

        for chunk, vector in zip(batch_chunks, embeddings):
            source_file = root / chunk.source_path
            is_priority = selected_as_priority(source_file, root)

            payload.append(
                {
                    "id": chunk.chunk_id,
                    "title": chunk.title,
                    "section": chunk.section,
                    "source_path": chunk.source_path,
                    "source_url": chunk.url,
                    "content": chunk.text,
                    "metadata": {
                        "product": "Microsoft Fabric",
                        "priority_document": is_priority,
                    },
                    "embedding": vector,
                }
            )

        database.table("documents").upsert(
            payload,
            on_conflict="id",
        ).execute()

    print("\n=== Ingestion terminée ===")
    print(f"{len(files)} fichiers sélectionnés.")
    print(f"{len(chunks)} chunks stockés dans Supabase.")
    print("Document Data Factory : OK")


if __name__ == "__main__":
    main()
