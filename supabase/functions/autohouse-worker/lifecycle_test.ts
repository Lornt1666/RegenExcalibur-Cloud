import { artifactMatchesExisting, expiredLeaseDisposition } from "./lifecycle.ts";

function assertEquals<T>(actual: T, expected: T, message: string): void {
  if (actual !== expected) throw new Error(`${message}: expected ${String(expected)}, got ${String(actual)}`);
}

Deno.test("expired LEASED jobs return to the queue", () => {
  assertEquals(expiredLeaseDisposition("LEASED"), "QUEUED", "LEASED disposition");
});

Deno.test("expired RUNNING jobs require reconciliation, not automatic replay", () => {
  assertEquals(expiredLeaseDisposition("RUNNING"), "RETRYABLE_FAILURE", "RUNNING disposition");
});

Deno.test("terminal jobs are not recovered by lease expiry", () => {
  assertEquals(expiredLeaseDisposition("SUCCEEDED"), null, "SUCCEEDED disposition");
  assertEquals(expiredLeaseDisposition("FAILED"), null, "FAILED disposition");
  assertEquals(expiredLeaseDisposition("CANCELLED"), null, "CANCELLED disposition");
});

Deno.test("artifact binding accepts an exact idempotent replay", () => {
  const binding = { owner_id: "owner-a", job_id: "job-a", revision_digest: "sha256:rev", artifact_digest: "sha256:artifact" };
  assertEquals(artifactMatchesExisting(binding, binding), true, "exact binding");
});

Deno.test("artifact binding rejects digest reuse across jobs or revisions", () => {
  const expected = { owner_id: "owner-a", job_id: "job-a", revision_digest: "sha256:rev", artifact_digest: "sha256:artifact" };
  assertEquals(artifactMatchesExisting({ ...expected, job_id: "job-b" }, expected), false, "wrong job");
  assertEquals(artifactMatchesExisting({ ...expected, revision_digest: "sha256:other" }, expected), false, "wrong revision");
  assertEquals(artifactMatchesExisting({ ...expected, owner_id: "owner-b" }, expected), false, "wrong owner");
});
