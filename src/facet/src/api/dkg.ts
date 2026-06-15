// frontend/src/api/dkg.ts
//
// Client for the DKG Projection read model. The governed projection *plan*
// (typed agience: triples + commit receipt) is always available for a
// committed artifact; real publication receipts (UAL + stage) are merged in
// once `agience-dkg` has written the artifact to a DKG v10 node.

import { get } from './api';

export interface DkgTriple {
  subject: string;
  predicate: string;
  object: string;
  kind: 'uri' | 'literal';
}

export type DkgStage = 'wm' | 'swm' | 'vm';
export type DkgPublishState =
  | 'written'
  | 'promoted'
  | 'published'
  | 'finalized'
  | 'failed';

export interface DkgPublication {
  publication_id: string;
  artifact_id?: string;
  artifact_root_id?: string;
  dkg_stage: DkgStage;
  context_graph_id: string;
  publish_state: DkgPublishState;
  ual?: string | null;
  assertion_id?: string | null;
  turn_uri?: string | null;
  projection_mode?: string | null;
  content_digest?: string | null;
  transport?: string | null;
  remote_timestamp?: string | null;
  recorded_at?: string;
  recorded_by?: string;
}

export interface DkgCommitReceipt {
  receipt_id: string;
  recorded_at: string;
  [key: string]: unknown;
}

export type DkgProjectionStatus = 'confirmed' | 'planned' | 'not-eligible';

export interface DkgProjectionView {
  artifact_id: string;
  root_id: string;
  state: string;
  committed: boolean;
  status: DkgProjectionStatus;
  governance: { committed: boolean; message: string };
  subject_uri: string;
  is_real_subject: boolean;
  triples: DkgTriple[];
  commit_receipt: DkgCommitReceipt | null;
  publications: DkgPublication[];
  wm: DkgPublication | null;
  swm: DkgPublication | null;
}

export function getDkgProjection(artifactId: string): Promise<DkgProjectionView> {
  return get(`/artifacts/${encodeURIComponent(artifactId)}/dkg/projection`);
}
