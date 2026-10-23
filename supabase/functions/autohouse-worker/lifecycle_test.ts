import { artifactMatchesExisting, expiredLeaseDisposition, isFinishableState, workerLeaseIdentity } from "./lifecycle.ts";

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

Deno.test("only RUNNING jobs may be completed by a worker", () => {
  assertEquals(isFinishableState("RUNNING"), true, "RUNNING may finish");
  assertEquals(isFinishableState("LEASED"), false, "LEASED cannot finish");
  assertEquals(isFinishableState("RETRYABLE_FAILURE"), false, "reconciliation-required jobs cannot finish");
  assertEquals(isFinishableState("CANCELLED"), false, "cancelled jobs cannot finish");
});

Deno.test("worker lease identity binds the GitHub run attempt", () => {
  assertEquals(workerLeaseIdentity("12345", "1"), "12345:1", "first attempt");
  assertEquals(workerLeaseIdentity("12345", "2"), "12345:2", "rerun is distinct");
});

Deno.test("worker lease identity rejects malformed run identifiers", () => {
  let rejected = false;
  try { workerLeaseIdentity("123x", "1"); } catch { rejected = true; }
  assertEquals(rejected, true, "invalid run ID");
});
