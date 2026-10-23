# External-service compatibility matrix

**Assessment date:** 2026-10-23  
**Status:** capability research performed; requested Neon resource identity and per-capability state remain unverified.

## Neon target

- Organization reference: `org-billowing-band-24504091`
- Project reference: `delicate-feather-78716523`
- Requested branch label: `production`

No Neon API credential or connected Neon management interface is available in this execution environment. Public documentation cannot confirm that these identifiers exist in the user's Neon account. The Neon API uses bearer API-key authentication, and branch operations use a branch ID; the label `production` must be resolved to the actual branch ID before a provider request can be safely bound. Do not attempt provisioning or mutate anything until account metadata confirms the target.

## Required statuses

Use only: `NOT_STARTED`, `BLOCKED`, `PROVISIONED`, `INTEGRATED`, `E2E_VERIFIED`.

| Capability | Status | Provider role / evidence | Minimum unblock / acceptance |
|---|---|---|---|
| PostgreSQL | BLOCKED | PostgreSQL is Neon’s core service, but target project/branch not authenticated or verified | Connect a scoped Neon API key or authorized Neon management connector; verify org/project/branch IDs and database endpoint; run a non-mutating connectivity and identity query |
| Authentication | BLOCKED | Neon Auth supports branch-level integration with providers including Better Auth; not confirmed enabled on this branch | Verify target and existing auth provider; integration only after approved design; test sign-in, session expiry, tenant/row isolation and token rejection |
| AI Gateway | BLOCKED | Neon exposes a branch-level AI Gateway endpoint API; project/branch availability is not verified | Resolve target branch ID, query AI Gateway status, verify provider and credentials without exposing them, run one approved bounded test |
| Object Storage | BLOCKED | Neon documents branchable object storage and S3-compatible access; availability is branch-specific | Query branch storage state, confirm bucket/credential model and data retention, then test least-privilege write/read/delete only in a disposable approved test bucket |
| Functions | BLOCKED | Neon exposes branch-level Functions APIs; function listing/deployment endpoints are documented as Beta | Verify target and runtime availability; deploy only to a non-production branch with explicit approval; test auth, bounded execution, logs and rollback |
| Realtime | BLOCKED | Neon exposes branch-level Realtime enablement; provisioning is asynchronous and origin allowlists matter | Verify support and branch state, set exact approved origins (never wildcard by default), wait for ready state, test authorized and unauthorized subscriptions |

## Official provider documentation

- [Neon API authentication](https://api-docs.neon.tech/reference/authentication)
- [Enable Neon Auth on a branch](https://api-docs.neon.tech/reference/createneonauth)
- [Get branch AI Gateway endpoint](https://api-docs.neon.tech/reference/getprojectbranchaigateway)
- [Get branch object-storage state](https://api-docs.neon.tech/reference/getprojectbranchstorage)
- [List branch functions](https://api-docs.neon.tech/reference/listprojectbranchfunctions)
- [Enable Realtime on a branch](https://api-docs.neon.tech/reference/enableprojectbranchrealtime)

These pages establish that provider interfaces exist; they do not establish provisioning, entitlement, or working configuration for the requested project.

## Cloud Shell compatibility note

The [Cloud Shell REST API](https://docs.cloud.google.com/shell/docs/reference/rest) documents environment lifecycle, authorization, and SSH-key management. It does not document a general REST method for arbitrary command execution. The current code therefore prepares a typed, user-assisted read-only diagnostic rather than claiming API-driven command dispatch.

## Antigravity compatibility note

Google documents both a [Python Antigravity SDK](https://www.antigravity.google/docs/sdk/overview) and a [managed Antigravity agent through the Gemini Interactions API](https://ai.google.dev/gemini-api/docs/antigravity-agent). These are distinct from the desktop application. The current code creates a workspace-bound manual handoff only; no SDK, managed API, desktop app, or CLI execution has been performed.

## Release rule

A provider feature may advance to `PROVISIONED` only after the exact target is verified and provider metadata proves the resource is provisioned. Advance to `INTEGRATED` only after the application uses the real interface with approved identity and least privilege. Advance to `E2E_VERIFIED` only after a test in the intended environment proves the full request-to-result path, denial path, audit evidence, and recovery behavior.
