export type JobState = "QUEUED" | "LEASED" | "RUNNING" | "SUCCEEDED" | "RETRYABLE_FAILURE" | "FAILED" | "CANCELLED";

export function workerLeaseIdentity(runId: string, runAttempt: string): string {
  if (!/^\d+$/.test(runId) || !/^\d+$/.test(runAttempt)) {
    throw new Error("GitHub run ID and run attempt must be numeric strings");
  }
  return `${runId}:${runAttempt}`;
}

export function isFinishableState(state: JobState): boolean {
  return state === "RUNNING";
}

export function expiredLeaseDisposition(state: JobState): "QUEUED" | "RETRYABLE_FAILURE" | null {
  if (state === "LEASED") return "QUEUED";
  if (state === "RUNNING") return "RETRYABLE_FAILURE";
  return null;
}


export interface WorkerLeaseRecord {
  worker_run_id?: string | null;
  worker_repository?: string | null;
  worker_sha?: string | null;
  lease_expires_at?: string | null;
}

export interface WorkerLeaseExpected {
  run_id: string;
  run_attempt: string;
  repository: string;
  sha: string;
}

export function workerLeaseIsCurrent(
  lease: WorkerLeaseRecord,
  expected: WorkerLeaseExpected,
  nowMs = Date.now(),
): boolean {
  if (lease.worker_run_id !== workerLeaseIdentity(expected.run_id, expected.run_attempt)) return false;
  if (lease.worker_repository !== expected.repository || lease.worker_sha !== expected.sha) return false;
  if (!lease.lease_expires_at) return false;
  const expiry = Date.parse(lease.lease_expires_at);
  return Number.isFinite(expiry) && expiry > nowMs;
}

export interface ArtifactBinding {
  owner_id: string;
  job_id: string;
  revision_digest: string;
  artifact_digest: string;
}

export function artifactMatchesExisting(existing: Partial<ArtifactBinding>, expected: ArtifactBinding): boolean {
  return existing.owner_id === expected.owner_id
    && existing.job_id === expected.job_id
    && existing.revision_digest === expected.revision_digest
    && existing.artifact_digest === expected.artifact_digest;
}
