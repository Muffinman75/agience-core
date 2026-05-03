from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReceiptArtifactRef(BaseModel):
    artifact_id: str
    role: Literal["source", "target", "receipt-parent", "receipt-child"]

    model_config = ConfigDict(extra="forbid")


class ReceiptActor(BaseModel):
    principal_id: str
    principal_type: Literal["user", "service", "system"]
    client_id: Optional[str] = None
    display_name: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class ReceiptAuthority(BaseModel):
    authorization_mode: Literal["human-review", "delegated-jwt", "api-key", "service-policy", "dkg-wallet"]
    approval_ref: Optional[str] = None
    scope_refs: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class BaseReceipt(BaseModel):
    schema_version: str = "1.0"
    receipt_type: Literal["commit", "grant", "revoke", "access", "projection", "publication", "provenance"]
    receipt_id: str
    status: Literal["recorded", "superseded", "voided"] = "recorded"
    recorded_at: str
    artifact_refs: List[ReceiptArtifactRef] = Field(default_factory=list)
    actor: ReceiptActor
    authority: ReceiptAuthority
    context: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class CommitProvenanceCheck(BaseModel):
    missing_provenance_count: int = 0
    warnings: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class CommitReceiptPayload(BaseModel):
    workspace_id: str
    collection_id: str
    artifact_count: int
    commit_reason: Optional[str] = None
    commit_preview_ref: Optional[str] = None
    provenance_check: CommitProvenanceCheck = Field(default_factory=CommitProvenanceCheck)

    model_config = ConfigDict(extra="forbid")


class CommitReceipt(BaseReceipt):
    receipt_type: Literal["commit"] = "commit"
    commit: CommitReceiptPayload


class GrantReceiptPayload(BaseModel):
    grant_id: str
    grantor_principal_id: str
    subject_principal_id: str
    subject_did: str
    scope_type: Literal["collection", "artifact", "context", "subgraph"]
    scope_id: str
    capabilities: List[str] = Field(default_factory=list)
    valid_from: Optional[str] = None
    valid_until: str
    flare_ledger_ref: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class GrantReceipt(BaseReceipt):
    receipt_type: Literal["grant"] = "grant"
    grant: GrantReceiptPayload


class RevokeReceiptPayload(BaseModel):
    revoke_id: str
    revoked_grant_id: str
    subject_principal_id: str
    subject_did: Optional[str] = None
    effective_at: str
    reason: Optional[str] = None
    flare_ledger_ref: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class RevokeReceipt(BaseReceipt):
    receipt_type: Literal["revoke"] = "revoke"
    revoke: RevokeReceiptPayload


class AccessReceiptPayload(BaseModel):
    request_id: str
    decision: Literal["allow", "deny"]
    query_mode: Literal["search", "lookup", "batch", "graph-traversal"]
    policy_class: str
    matched_scope_id: Optional[str] = None
    query_fingerprint: Optional[str] = None
    ttl_hint_seconds: Optional[int] = None
    flare_response_ref: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class AccessReceipt(BaseReceipt):
    receipt_type: Literal["access"] = "access"
    access: AccessReceiptPayload


class SourceArtifactVersionRef(BaseModel):
    artifact_id: str
    version: int

    model_config = ConfigDict(extra="forbid")


class ProjectionReceiptPayload(BaseModel):
    projection_id: str
    projection_mode: Literal["summary", "claim", "rdf", "bundle"]
    target_system: Literal["dkg"] = "dkg"
    target_stage: Literal["wm", "swm", "vm"]
    context_graph_id: str
    export_job_id: str
    content_digest: Optional[str] = None
    source_artifact_version_refs: List[SourceArtifactVersionRef] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ProjectionReceipt(BaseReceipt):
    receipt_type: Literal["projection"] = "projection"
    projection: ProjectionReceiptPayload


class PublicationReceiptPayload(BaseModel):
    publication_id: str
    dkg_stage: Literal["wm", "swm", "vm"]
    context_graph_id: str
    assertion_id: Optional[str] = None
    ual: Optional[str] = None
    batch_id: Optional[str] = None
    publish_state: Literal["written", "promoted", "published", "finalized", "failed"]
    remote_timestamp: Optional[str] = None
    remote_ref: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class PublicationReceipt(BaseReceipt):
    receipt_type: Literal["publication"] = "publication"
    publication: PublicationReceiptPayload


class ProvenanceReceiptPayload(BaseModel):
    lineage_subject_id: str
    lifecycle_state: Literal["committed", "retrieved", "projected", "published", "superseded"]
    receipt_chain: List[str] = Field(default_factory=list)
    latest_dkg_stage: Optional[Literal["wm", "swm", "vm"]] = None
    latest_policy_class: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class ProvenanceReceipt(BaseReceipt):
    receipt_type: Literal["provenance"] = "provenance"
    provenance: ProvenanceReceiptPayload


class PolicyMappingRecord(BaseModel):
    rule_id: str
    subject_type: Literal["artifact", "artifact_type", "collection", "workspace", "system"]
    subject_id: str
    policy_class: Literal["internal-standard", "internal-confidential", "export-approved", "public-verifiable"]
    retrieval_profile: Literal["native-search", "protected-search", "mixed-search"]
    export_profile: Literal["no-export", "approval-required", "derived-only", "full-projection-allowed"]
    promotion_profile: Literal["none", "wm-only", "swm-eligible", "vm-eligible"]
    identity_profile: Literal["human-review-only", "delegated-service", "policy-automation"]
    flare_contexts: List[str] = Field(default_factory=list)
    dkg_context_graphs: List[str] = Field(default_factory=list)
    required_receipts: List[str] = Field(default_factory=list)
    artifact_filters: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class RetrievalRouteDecision(BaseModel):
    retrieval_profile: Literal["native-search", "protected-search", "mixed-search"]
    route: Literal["agience", "flare", "agience+flare"]
    policy_class: str
    requires_access_receipt: bool = False

    model_config = ConfigDict(extra="forbid")


class ProjectionRequest(BaseModel):
    artifact_id: str
    artifact_version: int
    source_collection_id: str
    projection_mode: Literal["summary", "claim", "rdf", "bundle"]
    target_stage: Literal["wm"] = "wm"
    context_graph_id: str
    approval_receipt_id: str
    policy_class: str
    content_digest: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class ProjectionResult(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    required_receipts: List[str] = Field(default_factory=list)
    target_stage: Literal["wm"] = "wm"
    projection_mode: Literal["summary", "claim", "rdf", "bundle"]
    context_graph_id: str

    model_config = ConfigDict(extra="forbid")
