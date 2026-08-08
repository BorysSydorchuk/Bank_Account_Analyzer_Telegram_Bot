interface SyncStatusProps {
  // The real stage message from GET /api/jobs/{job_id} while a sync's
  // background job is running, or its final "Done — N transactions
  // categorized, M insights generated" line once it isn't (S3-04) — not a
  // timed guess at what the backend is probably doing.
  statusMessage: string | null
}

export function SyncStatus({ statusMessage }: SyncStatusProps) {
  if (!statusMessage) return null
  return <p className="text-xs text-text-secondary">{statusMessage}</p>
}
