from api.dkg_integration import (
    PolicyMappingRecord,
    ProjectionRequest,
    ReceiptActor,
    ReceiptAuthority,
)
from services.dkg_integration_service import (
    build_commit_receipt,
    resolve_policy_mapping,
    resolve_retrieval_route,
    validate_projection_request,
    validate_receipt_chain,
)


def test_build_commit_receipt_captures_commit_metadata():
    receipt = build_commit_receipt(
        workspace_id="ws-1",
        collection_id="col-1",
        artifact_ids=["art-1", "art-2"],
        actor=ReceiptActor(
            principal_id="user-1",
            principal_type="user",
            client_id="agience-web",
        ),
        authority=ReceiptAuthority(
            authorization_mode="human-review",
            scope_refs=["workspace:ws-1", "collection:col-1"],
        ),
        approval_ref="apr-1",
    )

    assert receipt.receipt_type == "commit"
    assert receipt.commit.workspace_id == "ws-1"
    assert receipt.commit.collection_id == "col-1"
    assert receipt.commit.artifact_count == 2
    assert receipt.authority.approval_ref == "apr-1"
    assert [ref.artifact_id for ref in receipt.artifact_refs] == ["art-1", "art-2"]


def test_validate_receipt_chain_requires_parent_for_publication():
    from api.dkg_integration import PublicationReceipt, PublicationReceiptPayload

    receipt = PublicationReceipt(
        receipt_id="rcpt_publication_1",
        recorded_at="2026-05-03T11:00:00Z",
        artifact_refs=[],
        actor=ReceiptActor(principal_id="svc-1", principal_type="service"),
        authority=ReceiptAuthority(authorization_mode="service-policy"),
        publication=PublicationReceiptPayload(
            publication_id="pub-1",
            dkg_stage="wm",
            context_graph_id="cg-1",
            publish_state="written",
            assertion_id="assert-1",
        ),
    )

    try:
        validate_receipt_chain(receipt)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "artifact reference" in str(exc) or "parent receipt" in str(exc)


def test_resolve_policy_mapping_uses_precedence_order():
    mappings = [
        PolicyMappingRecord(
            rule_id="system-default",
            subject_type="system",
            subject_id="default",
            policy_class="internal-standard",
            retrieval_profile="native-search",
            export_profile="approval-required",
            promotion_profile="wm-only",
            identity_profile="human-review-only",
        ),
        PolicyMappingRecord(
            rule_id="collection-confidential",
            subject_type="collection",
            subject_id="col-1",
            policy_class="internal-confidential",
            retrieval_profile="protected-search",
            export_profile="derived-only",
            promotion_profile="wm-only",
            identity_profile="human-review-only",
        ),
        PolicyMappingRecord(
            rule_id="artifact-override",
            subject_type="artifact",
            subject_id="art-1",
            policy_class="export-approved",
            retrieval_profile="mixed-search",
            export_profile="full-projection-allowed",
            promotion_profile="swm-eligible",
            identity_profile="delegated-service",
        ),
    ]

    resolved = resolve_policy_mapping(
        mappings=mappings,
        artifact_id="art-1",
        collection_id="col-1",
        workspace_id="ws-1",
    )

    assert resolved is not None
    assert resolved.rule_id == "artifact-override"


def test_resolve_retrieval_route_marks_flare_receipts_for_protected_search():
    mapping = PolicyMappingRecord(
        rule_id="collection-confidential",
        subject_type="collection",
        subject_id="col-1",
        policy_class="internal-confidential",
        retrieval_profile="protected-search",
        export_profile="derived-only",
        promotion_profile="wm-only",
        identity_profile="human-review-only",
    )

    decision = resolve_retrieval_route(mapping)

    assert decision.route == "flare"
    assert decision.requires_access_receipt is True
    assert decision.policy_class == "internal-confidential"


def test_validate_projection_request_blocks_uncommitted_artifact():
    mapping = PolicyMappingRecord(
        rule_id="export-approved",
        subject_type="collection",
        subject_id="col-1",
        policy_class="export-approved",
        retrieval_profile="mixed-search",
        export_profile="full-projection-allowed",
        promotion_profile="swm-eligible",
        identity_profile="delegated-service",
        required_receipts=["commit"],
    )
    request = ProjectionRequest(
        artifact_id="art-1",
        artifact_version=1,
        source_collection_id="col-1",
        projection_mode="claim",
        context_graph_id="cg-1",
        approval_receipt_id="apr-1",
        policy_class="export-approved",
    )

    result = validate_projection_request(request, mapping=mapping, is_committed=False)

    assert result.allowed is False
    assert result.reason == "artifact must be committed before projection"


def test_validate_projection_request_allows_committed_export():
    mapping = PolicyMappingRecord(
        rule_id="export-approved",
        subject_type="collection",
        subject_id="col-1",
        policy_class="export-approved",
        retrieval_profile="mixed-search",
        export_profile="full-projection-allowed",
        promotion_profile="swm-eligible",
        identity_profile="delegated-service",
        required_receipts=["commit"],
    )
    request = ProjectionRequest(
        artifact_id="art-1",
        artifact_version=2,
        source_collection_id="col-1",
        projection_mode="summary",
        context_graph_id="cg-1",
        approval_receipt_id="apr-1",
        policy_class="export-approved",
    )

    result = validate_projection_request(request, mapping=mapping, is_committed=True)

    assert result.allowed is True
    assert result.target_stage == "wm"
    assert sorted(result.required_receipts) == ["commit", "projection"]
