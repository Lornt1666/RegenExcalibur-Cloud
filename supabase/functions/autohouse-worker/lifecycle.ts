export type JobState = "QUEUED" | "LEASED" | "RUNNING" | "SUCCEEDED" | "RETRYABLE_FAILURE" | "FAILED" | "CANCELLED";

export function isFinishableState(state: JobState): boolean {
  return state === "RUNNING";
}

export function expiredLeaseDisposition(state: JobState): "QUEUED" | "RETRYABLE_FAILURE" | null {
  if (state === "LEASED") return "QUEUED";
  if (state === "RUNNING") return "RETRYABLE_FAILURE";
  return null;
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
