"""CLI entry points — extract-document, extract-batch, validate-graph, show-graph-summary."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.extraction.pipeline import extract_relationships, extract_single_document
from src.graph.manager import create_deal, load_graph, save_graph
from src.graph.merger import merge_document_extraction, merge_relationships
from src.graph.validator import validate_full
from src.models.extraction import DocumentExtractionResult
from src.models.schema import (
    ExtractionMetadata,
    Relationship,
    SCHEMA_VERSION,
)

logger = logging.getLogger(__name__)


def _compute_file_hash(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_conflict(graph, file_path: str, file_hash: str, extraction=None):
    """Detect if a document already exists in the graph.

    Returns (document_id, match_method) or (None, None).
    """
    # Match by file_hash
    for doc_id, doc in graph.documents.items():
        if doc.file_hash == file_hash:
            return doc_id, "file_hash"

    # Match by source_file_path
    for doc_id, doc in graph.documents.items():
        if doc.source_file_path == file_path:
            return doc_id, "source_file_path"

    # Match by name + type (requires extraction result)
    if extraction:
        for doc_id, doc in graph.documents.items():
            if (doc.name == extraction.name
                    and doc.document_type == extraction.document_type):
                return doc_id, "name_type"

    return None, None


def extract_document(
    file_path: str,
    deal_dir: str,
    resolve: str | None = None,
    client=None,
) -> str:
    """Extract a single document and merge into deal graph.

    Returns JSON string with results or conflict status.
    """
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"status": "error", "message": f"File not found: {file_path}"})

    suffix = path.suffix.lower()
    if suffix not in (".pdf", ".docx"):
        return json.dumps({"status": "error", "message": f"Unsupported file type: {suffix}"})

    file_hash = _compute_file_hash(file_path)

    # Load or create graph
    graph = load_graph(deal_dir)
    if graph is None:
        graph = create_deal(deal_dir, path.stem)

    # Conflict detection (by hash and path first)
    conflict_id, match_method = _find_conflict(graph, file_path, file_hash)

    if conflict_id and resolve is None:
        return json.dumps({
            "status": "conflict",
            "reason": "document_exists",
            "document_id": conflict_id,
            "match_method": match_method,
            "options": ["replace", "version", "cancel"],
        })

    # Run extraction
    result = extract_single_document(file_path, existing_graph=graph, client=client)
    if isinstance(result, dict):
        return json.dumps({"status": "error", "message": result.get("error", "Extraction failed")})

    # If no conflict found by hash/path, check by name+type after extraction
    if not conflict_id:
        conflict_id, match_method = _find_conflict(graph, file_path, file_hash, extraction=result)
        if conflict_id and resolve is None:
            return json.dumps({
                "status": "conflict",
                "reason": "document_exists",
                "document_id": conflict_id,
                "match_method": match_method,
                "options": ["replace", "version", "cancel"],
            })

    # Build extraction metadata
    meta = result._extraction_meta if hasattr(result, "_extraction_meta") else {}  # type: ignore[attr-defined]
    now = datetime.now(timezone.utc).isoformat()
    ext_metadata = ExtractionMetadata(
        extracted_at=now,
        model=meta.get("model", "unknown"),
        model_version=meta.get("model", "unknown").split("-")[-1] if meta.get("model") else "unknown",
        temperature=0,
        prompt_version=meta.get("prompt_version", "unknown"),
        processing_time_ms=meta.get("processing_time_ms"),
        pdf_has_text_layer=meta.get("has_text_layer"),
    )

    # Handle resolve modes
    if conflict_id and resolve == "replace":
        old_doc = graph.documents[conflict_id]
        # Preserve annotations (they are untouched by merger)
        # Downgrade confidence on related edges
        for rel in graph.relationships:
            if rel.source_document_id == conflict_id or rel.target_document_id == conflict_id:
                rel.confidence = "low"
                rel.needs_review = True
        # Remove old document, merge new one
        del graph.documents[conflict_id]
        graph, new_doc_id = merge_document_extraction(
            graph, result, file_path, file_hash, ext_metadata,
        )
        # Reassign the old ID to preserve references
        doc = graph.documents.pop(new_doc_id)
        doc.id = conflict_id
        doc.ai_original_values = old_doc.ai_original_values
        graph.documents[conflict_id] = doc
        # Update extraction log
        graph.extraction_log[-1].action = "re-extract_replace"
        graph.extraction_log[-1].document_id = conflict_id
        doc_id = conflict_id

    elif conflict_id and resolve == "version":
        # Keep old document, create new one
        graph, new_doc_id = merge_document_extraction(
            graph, result, file_path, file_hash, ext_metadata,
        )
        # Add supersedes edge
        graph.relationships.append(Relationship(
            id=f"rel-supersedes-{new_doc_id[:8]}",
            source_document_id=new_doc_id,
            target_document_id=conflict_id,
            relationship_type="supersedes",
            confidence="high",
            description=f"New version of {graph.documents[conflict_id].name}",
        ))
        graph.extraction_log[-1].action = "re-extract_version"
        doc_id = new_doc_id

    else:
        # Normal extraction (no conflict)
        graph, doc_id = merge_document_extraction(
            graph, result, file_path, file_hash, ext_metadata,
        )

    # Run relationship linking if other documents exist
    if len(graph.documents) > 1:
        content = Path(file_path).read_bytes() if suffix == ".pdf" else None
        if content:
            rel_result = extract_relationships(
                file_path, content, graph, client=client,
            )
            if isinstance(rel_result, dict):
                logger.warning(f"Relationship linking failed: {rel_result}")
            else:
                graph = merge_relationships(
                    graph, rel_result, doc_id, {}, ext_metadata,
                )

    save_graph(graph, deal_dir)

    return json.dumps({
        "status": "success",
        "document_id": doc_id,
        "name": result.name,
        "document_type": result.document_type,
        "parties_found": len(result.parties),
        "terms_found": len(result.defined_terms),
        "provisions_found": len(result.key_provisions),
    })


def extract_batch(
    folder_path: str,
    deal_dir: str,
    deal_name: str,
    client=None,
) -> str:
    """Process all PDF/DOCX files in a folder. Creates new deal graph.

    Returns JSON string with batch results summary.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        return json.dumps({"status": "error", "message": f"Folder not found: {folder_path}"})

    # Discover files
    files = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in (".pdf", ".docx")
    )

    if not files:
        return json.dumps({"status": "error", "message": "No PDF or DOCX files found in folder"})

    # Create new deal
    graph = create_deal(deal_dir, deal_name)
    processed = 0
    warnings = []

    for file_path in files:
        result = extract_single_document(str(file_path), existing_graph=graph, client=client)
        if isinstance(result, dict):
            warnings.append(f"Failed to extract {file_path.name}: {result.get('error', 'unknown')}")
            continue

        file_hash = _compute_file_hash(str(file_path))
        now = datetime.now(timezone.utc).isoformat()
        meta = result._extraction_meta if hasattr(result, "_extraction_meta") else {}  # type: ignore[attr-defined]
        ext_metadata = ExtractionMetadata(
            extracted_at=now,
            model=meta.get("model", "unknown"),
            model_version=meta.get("model", "unknown").split("-")[-1] if meta.get("model") else "unknown",
            temperature=0,
            prompt_version=meta.get("prompt_version", "unknown"),
            processing_time_ms=meta.get("processing_time_ms"),
            pdf_has_text_layer=meta.get("has_text_layer"),
        )
        graph, _ = merge_document_extraction(
            graph, result, str(file_path), file_hash, ext_metadata,
        )
        processed += 1

    # Relationship linking pass
    rel_count = 0
    if len(graph.documents) > 1:
        for doc_id, doc in list(graph.documents.items()):
            file_path = Path(doc.source_file_path)
            if file_path.exists() and file_path.suffix.lower() == ".pdf":
                content = file_path.read_bytes()
            else:
                content = None

            if content:
                rel_result = extract_relationships(
                    str(file_path), content, graph, client=client,
                )
                if not isinstance(rel_result, dict):
                    now = datetime.now(timezone.utc).isoformat()
                    ext_meta = ExtractionMetadata(
                        extracted_at=now, model="unknown", model_version="unknown",
                        temperature=0, prompt_version="unknown",
                    )
                    before = len(graph.relationships)
                    graph = merge_relationships(graph, rel_result, doc_id, {}, ext_meta)
                    rel_count += len(graph.relationships) - before

    # Validate and save
    validation = validate_full(graph)
    if validation.warnings:
        warnings.extend(validation.warnings)

    save_graph(graph, deal_dir)

    return json.dumps({
        "status": "success",
        "deal_name": deal_name,
        "documents_processed": processed,
        "relationships_found": len(graph.relationships),
        "parties_found": len(graph.parties),
        "defined_terms_found": len(graph.defined_terms),
        "warnings": warnings,
    })


def validate_graph(deal_dir: str) -> str:
    """Validate deal-graph.json against schema and semantic rules.

    Returns JSON string with validation results.
    """
    graph = load_graph(deal_dir)
    if graph is None:
        return json.dumps({"status": "error", "message": f"No deal-graph.json found in {deal_dir}"})

    result = validate_full(graph)

    return json.dumps({
        "status": "valid" if result.is_valid else "invalid",
        "errors": result.errors,
        "warnings": result.warnings,
    })


def show_graph_summary(deal_dir: str) -> str:
    """Return a JSON summary of the deal graph."""
    graph = load_graph(deal_dir)
    if graph is None:
        return json.dumps({"status": "error", "message": f"No deal-graph.json found in {deal_dir}"})

    # Relationship breakdown by type
    rel_by_type: dict[str, int] = {}
    for rel in graph.relationships:
        rel_by_type[rel.relationship_type] = rel_by_type.get(rel.relationship_type, 0) + 1

    # CP status breakdown
    cp_by_status: dict[str, int] = {}
    for cp in graph.conditions_precedent:
        cp_by_status[cp.status] = cp_by_status.get(cp.status, 0) + 1

    # Needs review count
    needs_review = sum(1 for r in graph.relationships if r.needs_review)
    needs_review += sum(1 for x in graph.cross_references if x.needs_review)

    return json.dumps({
        "status": "success",
        "deal_name": graph.deal.name,
        "deal_status": graph.deal.status,
        "document_count": len(graph.documents),
        "documents": [
            {"id": d.id, "name": d.name, "type": d.document_type}
            for d in graph.documents.values()
        ],
        "relationship_count": len(graph.relationships),
        "relationships_by_type": rel_by_type,
        "party_count": len(graph.parties),
        "parties": [p.canonical_name for p in graph.parties.values()],
        "defined_term_count": len(graph.defined_terms),
        "condition_count": len(graph.conditions_precedent),
        "conditions_by_status": cp_by_status,
        "needs_review_count": needs_review,
        "last_updated": graph.deal.updated_at,
    })


def main():
    """Argparse-based entry point."""
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    parser = argparse.ArgumentParser(
        prog="legal-mapping",
        description="Legal document dependency graph tool",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # extract-document
    p_extract = subparsers.add_parser("extract-document", help="Extract a single document")
    p_extract.add_argument("file_path", help="Path to PDF or DOCX file")
    p_extract.add_argument("deal_dir", help="Path to deal directory")
    p_extract.add_argument("--resolve", choices=["replace", "version"], default=None)

    # extract-batch
    p_batch = subparsers.add_parser("extract-batch", help="Batch extract all documents in a folder")
    p_batch.add_argument("folder_path", help="Folder containing documents")
    p_batch.add_argument("deal_dir", help="Path to deal directory")
    p_batch.add_argument("--deal-name", required=True, help="Deal name")

    # validate-graph
    p_validate = subparsers.add_parser("validate-graph", help="Validate deal graph")
    p_validate.add_argument("deal_dir", help="Path to deal directory")

    # show-graph-summary
    p_summary = subparsers.add_parser("show-graph-summary", help="Show graph summary")
    p_summary.add_argument("deal_dir", help="Path to deal directory")

    args = parser.parse_args()

    try:
        if args.command == "extract-document":
            output = extract_document(args.file_path, args.deal_dir, args.resolve)
        elif args.command == "extract-batch":
            output = extract_batch(args.folder_path, args.deal_dir, args.deal_name)
        elif args.command == "validate-graph":
            output = validate_graph(args.deal_dir)
        elif args.command == "show-graph-summary":
            output = show_graph_summary(args.deal_dir)
        else:
            output = json.dumps({"status": "error", "message": f"Unknown command: {args.command}"})
            print(output)
            sys.exit(1)

        result = json.loads(output)
        print(output)
        sys.exit(0 if result.get("status") != "error" else 1)

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
