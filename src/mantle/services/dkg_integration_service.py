from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional
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
