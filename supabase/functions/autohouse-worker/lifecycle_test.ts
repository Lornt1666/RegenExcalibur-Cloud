import { assertEquals } from "jsr:@std/assert@1";
import { artifactMatchesExisting, expiredLeaseDisposition } from "./lifecycle.ts";

Deno.test("expired LEASED jobs return to the queue", () => {
  assertEquals(expiredLeaseDisposition("LEASED"), "QUEUED");
});

Deno.test("expired RUNNING jobs require reconciliation, not automatic replay", () => {
  assertEquals(expiredLeaseDisposition("RUNNING"), "RETRYABLE_FAILURE");
});

Deno.test("terminal jobs are not recovered by lease expiry", () => {
  assertEquals(expiredLeaseDisposition("SUCCEEDED"), null);
  assertEquals(expiredLeaseDisposition("FAILED"), null);
  assertEquals(expiredLeaseDisposition("CANCELLED"), null);
});

Deno.test("artifact binding accepts an exact idempotent replay", () => {
  const binding = { owner_id: "owner-a", job_id: "job-a", revision_digest: "sha256:rev", artifact_digest: "sha256:artifact" };
  assertEquals(artifactMatchesExisting(binding, binding), true);
});

Deno.test("artifact binding rejects digest reuse across jobs or revisions", () => {
  const expected = { owner_id: "owner-a", job_id: "job-a", revision_digest: "sha256:rev", artifact_digest: "sha256:artifact" };
  assertEquals(artifactMatchesExisting({ ...expected, job_id: "job-b" }, expected), false);
  assertEquals(artifactMatchesExisting({ ...expected, revision_digest: "sha256:other" }, expected), false);
  assertEquals(artifactMatchesExisting({ ...expected, owner_id: "owner-b" }, expected), false);
});
