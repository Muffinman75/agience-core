// frontend/src/components/workspace/DkgProjectionPanel.tsx
//
// Read-only view of how a committed Agience artifact projects onto the
// OriginTrail DKG v10 knowledge graph. It surfaces the governance gate, the
// memory-layer lifecycle (WM -> SWM -> VM), the deterministic subject URI (or
// the real UAL once published), and the typed `agience:` triples that the
// `agience-dkg` integration writes to the daemon.
//
// The data is a hybrid read model (see backend `build_dkg_projection_view`):
// the projection *plan* is always computed from the committed artifact; real
// publication receipts (UAL + stage) are merged in once the integration has
// written the artifact to a DKG node.

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Copy,
  Database,
  Loader2,
  RefreshCw,
  ShieldCheck,
  ShieldX,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  getDkgProjection,
  type DkgProjectionView,
  type DkgPublication,
  type DkgStage,
} from '@/api/dkg';

interface DkgProjectionPanelProps {
  artifactId?: string;
}

const STAGE_LABELS: Record<DkgStage, string> = {
  wm: 'Working Memory',
  swm: 'Shared Memory',
  vm: 'Verifiable Memory',
};

const STAGE_BLURB: Record<DkgStage, string> = {
  wm: 'Local draft on the operator daemon — no chain publish.',
  swm: 'Shared with the context graph — discoverable by peers.',
  vm: 'Minted on-chain — globally verifiable.',
};

function shortPredicate(predicate: string): string {
  if (predicate === 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type') return 'a';
  if (predicate.startsWith('https://agience.ai/ontology/'))
    return `agience:${predicate.slice('https://agience.ai/ontology/'.length)}`;
  if (predicate.startsWith('https://schema.org/'))
    return `schema:${predicate.slice('https://schema.org/'.length)}`;
  return predicate;
}

function shortObject(object: string): string {
  if (object.startsWith('https://agience.ai/ontology/'))
    return `agience:${object.slice('https://agience.ai/ontology/'.length)}`;
  return object;
}

function StatusBadge({ view }: { view: DkgProjectionView }) {
  if (view.status === 'confirmed')
    return (
      <Badge className="bg-emerald-600 hover:bg-emerald-600/90">
        <ShieldCheck size={12} className="mr-1" /> Published to DKG
      </Badge>
    );
  if (view.status === 'planned')
    return (
      <Badge className="bg-blue-600 hover:bg-blue-600/90">
        <ShieldCheck size={12} className="mr-1" /> Committed — projection ready
      </Badge>
    );
  return (
    <Badge variant="secondary" className="text-amber-700">
      <ShieldX size={12} className="mr-1" /> Not eligible (draft)
    </Badge>
  );
}

function StageStep({
  stage,
  active,
  pub,
}: {
  stage: DkgStage;
  active: boolean;
  pub: DkgPublication | null;
}) {
  const done = Boolean(pub);
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2">
        {done ? (
          <CheckCircle2 size={16} className="text-emerald-600 flex-shrink-0" />
        ) : active ? (
          <Circle size={16} className="text-blue-500 flex-shrink-0" />
        ) : (
          <Circle size={16} className="text-gray-300 flex-shrink-0" />
        )}
        <span
          className={`text-xs font-semibold uppercase tracking-wide ${
            done ? 'text-emerald-700' : active ? 'text-blue-700' : 'text-gray-400'
          }`}
        >
          {stage}
        </span>
      </div>
      <p className="mt-1 text-[11px] leading-tight text-gray-500">{STAGE_BLURB[stage]}</p>
      {done && pub?.publish_state && (
        <p className="mt-0.5 text-[11px] font-medium text-emerald-700">{pub.publish_state}</p>
      )}
    </div>
  );
}

export default function DkgProjectionPanel({ artifactId }: DkgProjectionPanelProps) {
  const [view, setView] = useState<DkgProjectionView | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    if (!artifactId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getDkgProjection(artifactId);
      setView(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to load DKG projection';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [artifactId]);

  useEffect(() => {
    load();
  }, [load]);

  const copySubject = useCallback(() => {
    if (!view?.subject_uri) return;
    navigator.clipboard?.writeText(view.subject_uri).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [view?.subject_uri]);

  if (!artifactId) {
    return (
      <p className="text-sm text-gray-500 text-center py-8">
        Save this artifact first to see its DKG projection.
      </p>
    );
  }

  if (loading && !view) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-1/2" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-6 w-3/4" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-8 text-center">
        <AlertTriangle className="text-amber-500" size={24} />
        <p className="text-sm text-gray-600">{error}</p>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw size={14} className="mr-1" /> Retry
        </Button>
      </div>
    );
  }

  if (!view) return null;

  const activeStage: DkgStage = view.swm ? 'vm' : view.wm ? 'swm' : 'wm';

  return (
    <div className="space-y-5">
      {/* Status + governance */}
      <div className="flex items-center justify-between gap-2">
        <StatusBadge view={view} />
        <Button variant="ghost" size="sm" onClick={load} disabled={loading} aria-label="Refresh">
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
        </Button>
      </div>

      <div
        className={`flex items-start gap-2 rounded-lg border p-3 text-sm ${
          view.committed
            ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
            : 'border-amber-200 bg-amber-50 text-amber-800'
        }`}
      >
        {view.committed ? (
          <ShieldCheck size={16} className="mt-0.5 flex-shrink-0" />
        ) : (
          <ShieldX size={16} className="mt-0.5 flex-shrink-0" />
        )}
        <span>{view.governance.message}</span>
      </div>

      {/* Lifecycle pipeline */}
      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Memory lifecycle
        </h4>
        <div className="flex items-stretch gap-3 rounded-lg border border-gray-200 p-3">
          <StageStep stage="wm" active={activeStage === 'wm'} pub={view.wm} />
          <div className="w-px bg-gray-200" />
          <StageStep stage="swm" active={activeStage === 'swm'} pub={view.swm} />
          <div className="w-px bg-gray-200" />
          <StageStep stage="vm" active={activeStage === 'vm'} pub={null} />
        </div>
      </div>

      {/* Subject URI */}
      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
          {view.is_real_subject ? 'Knowledge Asset UAL' : 'Planned subject URI'}
        </h4>
        <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 p-2">
          <Database size={14} className="flex-shrink-0 text-gray-400" />
          <code className="flex-1 truncate text-xs text-gray-700" title={view.subject_uri}>
            {view.subject_uri}
          </code>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={copySubject} aria-label="Copy URI">
            {copied ? <CheckCircle2 size={13} className="text-emerald-600" /> : <Copy size={13} />}
          </Button>
        </div>
        {!view.is_real_subject && view.committed && (
          <p className="mt-1 text-[11px] text-gray-500">
            Deterministic plan — becomes a real UAL once <code>agience-dkg wm-write</code> runs.
          </p>
        )}
      </div>

      {/* Typed triples */}
      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Typed <code className="text-[11px]">agience:</code> triples ({view.triples.length})
        </h4>
        <div className="overflow-hidden rounded-lg border border-gray-200">
          <table className="w-full text-xs">
            <tbody>
              {view.triples.map((t, i) => (
                <tr key={i} className={i % 2 ? 'bg-gray-50' : 'bg-white'}>
                  <td className="whitespace-nowrap px-2 py-1.5 font-mono font-medium text-purple-700 align-top">
                    {shortPredicate(t.predicate)}
                  </td>
                  <td className="px-2 py-1.5 align-top">
                    {t.kind === 'uri' ? (
                      <span className="font-mono text-blue-700">{shortObject(t.object)}</span>
                    ) : (
                      <span className="text-gray-700 break-words">{t.object}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Commit receipt */}
      {view.commit_receipt && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Commit receipt
          </h4>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-2">
            <code className="text-xs text-gray-700">{view.commit_receipt.receipt_id}</code>
            <p className="mt-0.5 text-[11px] text-gray-500">
              Links the on-chain record back to the human-approved version.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
