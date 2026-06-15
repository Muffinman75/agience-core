from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from api.dkg_integration import (
    BaseReceipt,
    CommitProvenanceCheck,
    CommitReceipt,
    CommitReceiptPayload,
    PolicyMappingRecord,
    ProjectionRequest,
    ProjectionResult,
    ReceiptActor,
    ReceiptArtifactRef,
    ReceiptAuthority,
    RetrievalRouteDecision,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt_id(prefix: str) -> str:
    return f"rcpt_{prefix}_{uuid4().hex[:12]}"


def build_commit_receipt(
    *,
    workspace_id: str,
    collection_id: str,
    artifact_ids: list[str],
    actor: ReceiptActor,
    authority: ReceiptAuthority,
    approval_ref: Optional[str] = None,
    commit_preview_ref: Optional[str] = None,
    commit_reason: str = "human-approved publish",
) -> CommitReceipt:
    effective_authority = authority.model_copy(
        update={"approval_ref": approval_ref or authority.approval_ref}
    )
    return CommitReceipt(
        receipt_id=_receipt_id("commit"),
        recorded_at=_now_iso(),
        artifact_refs=[
            ReceiptArtifactRef(artifact_id=artifact_id, role="source")
            for artifact_id in artifact_ids
        ],
        actor=actor,
        authority=effective_authority,
        commit=CommitReceiptPayload(
            workspace_id=workspace_id,
            collection_id=collection_id,
            artifact_count=len(artifact_ids),
            commit_reason=commit_reason,
            commit_preview_ref=commit_preview_ref,
            provenance_check=CommitProvenanceCheck(),
        ),
    )


def validate_receipt_chain(receipt: BaseReceipt) -> None:
    if not receipt.artifact_refs:
        raise ValueError("receipt must include at least one artifact reference")
    if receipt.receipt_type == "publication":
        if not any(ref.role == "receipt-parent" for ref in receipt.artifact_refs):
            raise ValueError("publication receipt must reference a parent receipt")


def resolve_policy_mapping(
    *,
    mappings: Iterable[PolicyMappingRecord],
    artifact_id: Optional[str] = None,
    artifact_type: Optional[str] = None,
    collection_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Optional[PolicyMappingRecord]:
    precedence = [
        ("artifact", artifact_id),
        ("artifact_type", artifact_type),
        ("collection", collection_id),
        ("workspace", workspace_id),
        ("system", "default"),
    ]
    materialized = list(mappings)
    for subject_type, subject_id in precedence:
        if not subject_id:
            continue
        for mapping in materialized:
            if mapping.subject_type == subject_type and mapping.subject_id == subject_id:
                return mapping
    return None


def resolve_retrieval_route(mapping: PolicyMappingRecord) -> RetrievalRouteDecision:
    route = {
        "native-search": "agience",
        "protected-search": "flare",
        "mixed-search": "agience+flare",
    }[mapping.retrieval_profile]
    return RetrievalRouteDecision(
        retrieval_profile=mapping.retrieval_profile,
        route=route,
        policy_class=mapping.policy_class,
        requires_access_receipt=mapping.retrieval_profile != "native-search",
    )


def validate_projection_request(
    request: ProjectionRequest,
    *,
    mapping: PolicyMappingRecord,
    is_committed: bool,
) -> ProjectionResult:
    if not is_committed:
        return ProjectionResult(
            allowed=False,
            reason="artifact must be committed before projection",
            required_receipts=mapping.required_receipts,
            projection_mode=request.projection_mode,
            context_graph_id=request.context_graph_id,
        )
    if mapping.export_profile == "no-export":
        return ProjectionResult(
            allowed=False,
            reason="policy blocks export",
            required_receipts=mapping.required_receipts,
            projection_mode=request.projection_mode,
            context_graph_id=request.context_graph_id,
        )
    if mapping.promotion_profile == "none":
        return ProjectionResult(
            allowed=False,
            reason="policy does not allow DKG promotion",
            required_receipts=mapping.required_receipts,
            projection_mode=request.projection_mode,
            context_graph_id=request.context_graph_id,
        )
    if not request.approval_receipt_id:
        return ProjectionResult(
            allowed=False,
            reason="approval receipt is required",
            required_receipts=mapping.required_receipts,
            projection_mode=request.projection_mode,
            context_graph_id=request.context_graph_id,
        )
    return ProjectionResult(
        allowed=True,
        required_receipts=sorted(set([*mapping.required_receipts, "projection"])),
        projection_mode=request.projection_mode,
        context_graph_id=request.context_graph_id,
    )


# ---------------------------------------------------------------------------
# DKG Projection view (read model for the frontend panel)
# ---------------------------------------------------------------------------

# RDF vocabulary — kept byte-for-byte in step with the `agience-dkg`
# integration's daemon transport (``daemon_client._quads_for_artifact``) so the
# "projected plan" shown in the UI is exactly what the integration writes to a
# DKG v10 node, not an approximation.
_AGIENCE_NS = "https://agience.ai/ontology/"
_SCHEMA_NS = "https://schema.org/"
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

_CONTEXT_GRAPH_PLACEHOLDER = "{contextGraph}"
_TEXT_PREVIEW_LIMIT = 280


def _parse_artifact_context(artifact: Dict[str, Any]) -> Dict[str, Any]:
    raw = artifact.get("context")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _lit_preview(value: str) -> str:
    """Truncate long literal objects for display (full text still projects)."""
    value = value or ""
    if len(value) > _TEXT_PREVIEW_LIMIT:
        return value[:_TEXT_PREVIEW_LIMIT] + "…"
    return value


def build_projection_triples(
    *,
    artifact: Dict[str, Any],
    subject_uri: str,
    context_graph_id: Optional[str] = None,
    memory_layer: str = "wm",
) -> List[Dict[str, str]]:
    """Project a committed Agience artifact onto the typed ``agience:`` triples.

    Mirrors ``daemon_client._quads_for_artifact``. ``kind`` is ``"uri"`` or
    ``"literal"`` so the UI can render them faithfully.
    """
    ctx = _parse_artifact_context(artifact)
    artifact_id = str(artifact.get("id") or artifact.get("root_id") or "")
    artifact_type = ctx.get("type") or ctx.get("artifact_type") or "Artifact"
    title = ctx.get("title") or ctx.get("preview_text") or artifact_id
    text = artifact.get("content") if isinstance(artifact.get("content"), str) else ""
    author = ctx.get("author") or artifact.get("created_by")
    tags = ctx.get("tags") if isinstance(ctx.get("tags"), list) else []
    collection_id = artifact.get("collection_id") or ctx.get("collection_id")
    commit_receipt_id = ctx.get("commit_receipt_id") or artifact.get("commit_receipt_id")
    cg_value = context_graph_id or _CONTEXT_GRAPH_PLACEHOLDER

    triples: List[Dict[str, str]] = [
        {"predicate": _RDF_TYPE, "object": f"{_AGIENCE_NS}{artifact_type}", "kind": "uri"},
        {"predicate": f"{_SCHEMA_NS}name", "object": title, "kind": "literal"},
        {"predicate": f"{_SCHEMA_NS}text", "object": _lit_preview(text), "kind": "literal"},
        {"predicate": f"{_AGIENCE_NS}artifactId", "object": artifact_id, "kind": "literal"},
        {"predicate": f"{_AGIENCE_NS}contextGraphId", "object": cg_value, "kind": "literal"},
        {"predicate": f"{_AGIENCE_NS}memoryLayer", "object": memory_layer, "kind": "literal"},
    ]
    if author:
        triples.append({"predicate": f"{_AGIENCE_NS}author", "object": str(author), "kind": "literal"})
    for tag in tags:
        triples.append({"predicate": f"{_AGIENCE_NS}tags", "object": str(tag), "kind": "literal"})
    if collection_id:
        triples.append({"predicate": f"{_AGIENCE_NS}collection", "object": str(collection_id), "kind": "literal"})
    if commit_receipt_id:
        triples.append({"predicate": f"{_AGIENCE_NS}commitReceiptId", "object": str(commit_receipt_id), "kind": "literal"})

    for t in triples:
        t["subject"] = subject_uri
    return triples


def build_dkg_projection_view(
    *,
    artifact: Dict[str, Any],
    publications: List[Dict[str, Any]],
    actor_principal_id: str = "",
    actor_type: str = "user",
) -> Dict[str, Any]:
    """Assemble the read model for the DKG Projection panel.

    Hybrid data source:
      * Always computes the governed *projection plan* — the typed ``agience:``
        triples and the deterministic subject URI — from the committed
        artifact. This needs no DKG node and is faithful to what the
        integration writes.
      * Merges any real *publication receipts* written back by ``agience-dkg``
        after a live ``wm-write`` / ``promote`` (real UAL, ``written`` /
        ``promoted`` state). When present, ``status`` is ``"confirmed"`` and
        the subject URI is the real UAL.
    """
    artifact_id = str(artifact.get("id") or "")
    root_id = str(artifact.get("root_id") or artifact_id)
    state = artifact.get("state") or "draft"
    committed = state == "committed"

    pubs = sorted(publications, key=lambda p: p.get("recorded_at") or "")
    wm = next((p for p in reversed(pubs) if p.get("dkg_stage") == "wm"), None)
    swm = next((p for p in reversed(pubs) if p.get("dkg_stage") == "swm"), None)
    confirmed = bool(pubs)

    # Prefer a real UAL as the triple subject once the artifact has been
    # written to a node; otherwise show the deterministic plan subject.
    real_ual = (wm or swm or {}).get("ual") if confirmed else None
    context_graph_id = (wm or swm or {}).get("context_graph_id") if confirmed else None
    subject_uri = real_ual or (
        f"{_AGIENCE_NS}{context_graph_id or _CONTEXT_GRAPH_PLACEHOLDER}/{artifact_id}"
    )

    triples = build_projection_triples(
        artifact=artifact,
        subject_uri=subject_uri,
        context_graph_id=context_graph_id,
    )

    commit_receipt: Optional[Dict[str, Any]] = None
    if committed:
        # Stable (non-random) commit receipt derived from the committed state —
        # the artifact has, by definition, passed the human-review boundary.
        commit_receipt = CommitReceipt(
            receipt_id=f"rcpt_commit_{root_id}",
            recorded_at=artifact.get("modified_time") or artifact.get("created_time") or _now_iso(),
            artifact_refs=[ReceiptArtifactRef(artifact_id=artifact_id, role="source")],
            actor=ReceiptActor(
                principal_id=actor_principal_id or (artifact.get("created_by") or "unknown"),
                principal_type=actor_type if actor_type in {"user", "service", "system"} else "user",
            ),
            authority=ReceiptAuthority(authorization_mode="human-review"),
            commit=CommitReceiptPayload(
                workspace_id=artifact.get("collection_id") or "",
                collection_id=artifact.get("collection_id") or "",
                artifact_count=1,
                commit_reason="human-approved publish",
            ),
        ).model_dump()

    return {
        "artifact_id": artifact_id,
        "root_id": root_id,
        "state": state,
        "committed": committed,
        "status": "confirmed" if confirmed else ("planned" if committed else "not-eligible"),
        "governance": {
            "committed": committed,
            "message": (
                "Committed — passed the human-review boundary and eligible for governed DKG projection."
                if committed
                else "Not committed — must pass the human-review commit boundary before it can be projected to DKG."
            ),
        },
        "subject_uri": subject_uri,
        "is_real_subject": bool(real_ual),
        "triples": triples,
        "commit_receipt": commit_receipt,
        "publications": pubs,
        "wm": wm,
        "swm": swm,
    }
