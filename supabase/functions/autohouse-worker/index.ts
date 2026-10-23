import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@6.1.0";
import { artifactMatchesExisting, expiredLeaseDisposition } from "./lifecycle.ts";

const TRUTH = "SCHEMATIC — NOT FOR CONSTRUCTION — UNSEALED — PROFESSIONAL / AHJ REVIEW REQUIRED.";
const VERSION = "v441";
const ISSUER = "https://token.actions.githubusercontent.com";
const AUDIENCE = "autohouse-supabase";
const REPOSITORY = "Lornt1666/RegenExcalibur-Cloud";
const REPOSITORY_ID = "1226507055";
const OWNER_ID = "236225491";
const WORKFLOW_FILE = ".github/workflows/autohouse-v440-worker-bridge.yml";
const PRODUCTION_REF = "refs/heads/RegenExcalibur-Webpage";
const JWKS = createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`));

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" } });
}
function adminClient() {
  const url = Deno.env.get("SUPABASE_URL");
  let secret = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? undefined;
  if (!secret) { const raw = Deno.env.get("SUPABASE_SECRET_KEYS"); if (raw) secret = JSON.parse(raw)?.default; }
  if (!url || !secret) throw new Error("server admin environment unavailable");
  return createClient(url, secret, { auth: { persistSession: false, autoRefreshToken: false } });
}
async function githubIdentity(req: Request) {
  const auth = req.headers.get("authorization") ?? "";
  if (!auth.startsWith("Bearer ")) throw new Error("missing GitHub OIDC bearer token");
  const { payload, protectedHeader } = await jwtVerify(auth.slice(7), JWKS, { issuer: ISSUER, audience: AUDIENCE });
  const repository=String(payload.repository??""), repositoryId=String(payload.repository_id??""), ownerId=String(payload.repository_owner_id??"");
  const ref=String(payload.ref??""), workflowRef=String(payload.workflow_ref??""), runId=String(payload.run_id??""), sha=String(payload.sha??"");
  if (repository!==REPOSITORY) throw new Error("untrusted repository");
  if (repositoryId!==REPOSITORY_ID) throw new Error("untrusted repository id");
  if (ownerId!==OWNER_ID) throw new Error("untrusted repository owner id");
  if (ref!==PRODUCTION_REF) throw new Error(`untrusted production ref ${ref}`);
  if (!workflowRef.startsWith(`${REPOSITORY}/${WORKFLOW_FILE}@${PRODUCTION_REF}`)) throw new Error("untrusted workflow_ref");
  if (!runId || !sha) throw new Error("missing immutable workflow identity");
  return {repository,repository_id:repositoryId,repository_owner_id:ownerId,ref,workflow_ref:workflowRef,run_id:runId,run_attempt:String(payload.run_attempt??""),actor:String(payload.actor??""),actor_id:String(payload.actor_id??""),sha,event_name:String(payload.event_name??""),runner_environment:String(payload.runner_environment??""),jti:String(payload.jti??""),kid:String(protectedHeader.kid??"")};
}
async function recoverExpired(admin: ReturnType<typeof createClient>) {
  const now=new Date().toISOString();
  // A job that expired before RUNNING is safe to return to the queue.
  if (expiredLeaseDisposition("LEASED") === "QUEUED") {
    const { error } = await admin.from("autohouse_jobs")
      .update({state:"QUEUED",leased_at:null,lease_expires_at:null,worker_run_id:null,worker_repository:null,worker_sha:null,updated_at:now})
      .eq("state","LEASED").lt("lease_expires_at",now);
    if (error) throw new Error(`expired LEASED recovery failed: ${error.message}`);
  }
  // A RUNNING job may have produced external effects. Never auto-requeue it.
  if (expiredLeaseDisposition("RUNNING") === "RETRYABLE_FAILURE") {
    const { error } = await admin.from("autohouse_jobs")
      .update({state:"RETRYABLE_FAILURE",lease_expires_at:null,error:{kind:"LEASE_EXPIRED_AFTER_START",message:"Worker lease expired after execution began; reconcile side effects before retry.",automatic_retry:false,reconciliation_required:true},updated_at:now})
      .eq("state","RUNNING").lt("lease_expires_at",now);
    if (error) throw new Error(`expired RUNNING reconciliation failed: ${error.message}`);
  }
}
async function lease(admin: ReturnType<typeof createClient>, ident: Awaited<ReturnType<typeof githubIdentity>>, body: Record<string,unknown>) {
  await recoverExpired(admin);
  const requested=Array.isArray(body.job_types)?body.job_types.filter((x)=>typeof x==="string") as string[]:[];
  const supported=requested.length?requested:["shell_certification"];
  const {data:candidates,error:selectError}=await admin.from("autohouse_jobs").select("id,owner_id,project_id,project_revision_digest,job_type,input_digest,idempotency_key,state,attempt,created_at").eq("state","QUEUED").in("job_type",supported).order("created_at",{ascending:true}).limit(1);
  if(selectError) throw new Error(selectError.message); const job=candidates?.[0];
  if(!job) return {status:"NO_JOB",authenticated:true,worker:ident,supported_job_types:supported};
  const now=new Date(), expires=new Date(now.getTime()+15*60*1000);
  const {data:leased,error:leaseError}=await admin.from("autohouse_jobs").update({state:"LEASED",attempt:Number(job.attempt??0)+1,leased_at:now.toISOString(),lease_expires_at:expires.toISOString(),worker_run_id:ident.run_id,worker_repository:ident.repository,worker_sha:ident.sha,updated_at:now.toISOString()}).eq("id",job.id).eq("state","QUEUED").select("id,owner_id,project_id,project_revision_digest,job_type,input_digest,idempotency_key,state,attempt,leased_at,lease_expires_at,worker_run_id,worker_repository,worker_sha").maybeSingle();
  if(leaseError) throw new Error(leaseError.message); if(!leased) return {status:"LEASE_RACE_LOST",authenticated:true,worker:ident};
  let revision_payload:unknown=null;
  if(leased.project_id){const {data:rev,error:revError}=await admin.from("autohouse_revisions").select("payload").eq("project_id",leased.project_id).eq("revision_digest",leased.project_revision_digest).maybeSingle();if(revError)throw new Error(revError.message);revision_payload=rev?.payload??null;}
  const safeJob={...leased} as Record<string,unknown>;delete safeJob.owner_id;
  return {status:"LEASED",authenticated:true,worker:ident,job:safeJob,revision_payload};
}
async function startJob(admin: ReturnType<typeof createClient>, ident: Awaited<ReturnType<typeof githubIdentity>>, body: Record<string,unknown>) {
  const id=String(body.job_id??"");if(!id)throw new Error("missing job_id");
  const {data,error}=await admin.from("autohouse_jobs").update({state:"RUNNING",updated_at:new Date().toISOString()}).eq("id",id).eq("state","LEASED").eq("worker_run_id",ident.run_id).eq("worker_repository",ident.repository).select("id,state,attempt,worker_run_id").maybeSingle();
  if(error)throw new Error(error.message);if(!data)throw new Error("job lease ownership mismatch");return {status:"RUNNING",job:data};
}
async function finishJob(admin: ReturnType<typeof createClient>, ident: Awaited<ReturnType<typeof githubIdentity>>, body: Record<string,unknown>) {
  const id=String(body.job_id??""),outcome=String(body.outcome??"");if(!id)throw new Error("missing job_id");if(!["SUCCEEDED","FAILED"].includes(outcome))throw new Error("invalid outcome");
  const {data:current,error:currentError}=await admin.from("autohouse_jobs").select("id,owner_id,project_id,project_revision_digest,state,worker_run_id,worker_repository").eq("id",id).maybeSingle();
  if(currentError)throw new Error(currentError.message);if(!current)throw new Error("job not found");if(current.worker_run_id!==ident.run_id||current.worker_repository!==ident.repository)throw new Error("job lease ownership mismatch");if(!["LEASED","RUNNING"].includes(current.state))throw new Error(`job is not finishable from state ${current.state}`);
  const resultDigest=typeof body.result_digest==="string"?body.result_digest:null;if(outcome==="SUCCEEDED"&&!resultDigest)throw new Error("successful job requires result_digest");
  // Stage the artifact before the terminal SUCCEEDED transition. If the job update
  // fails, a retry can reconcile the same owner/digest/job tuple idempotently.
  if(outcome==="SUCCEEDED"&&resultDigest){
    const uri=typeof body.artifact_uri==="string"?body.artifact_uri:`https://github.com/${ident.repository}/actions/runs/${ident.run_id}`;
    const artifactType=typeof body.artifact_type==="string"?body.artifact_type:"worker_result";
    const expected={owner_id:current.owner_id,job_id:current.id,revision_digest:current.project_revision_digest,artifact_digest:resultDigest};
    const {data:existing,error:lookupError}=await admin.from("autohouse_artifacts").select("owner_id,job_id,revision_digest,artifact_digest").eq("owner_id",current.owner_id).eq("artifact_digest",resultDigest).maybeSingle();
    if(lookupError)throw new Error(`artifact reconciliation lookup failed: ${lookupError.message}`);
    if(existing){
      if(!artifactMatchesExisting(existing,expected))throw new Error("artifact digest already exists with mismatched job or revision binding");
    }else{
      const {error:artifactError}=await admin.from("autohouse_artifacts").insert({owner_id:current.owner_id,project_id:current.project_id,job_id:current.id,revision_digest:current.project_revision_digest,artifact_type:artifactType,artifact_digest:resultDigest,uri,metadata:{worker_repository:ident.repository,worker_run_id:ident.run_id,worker_sha:ident.sha,workflow_ref:ident.workflow_ref,identity_verified_by:"GitHub OIDC",content_digest_supplied_by_worker:true}});
      if(artifactError)throw new Error(`artifact ledger insert failed; job remains nonterminal: ${artifactError.message}`);
    }
  }
  const {data:updated,error:updateError}=await admin.from("autohouse_jobs").update({state:outcome,result_digest:resultDigest,error:outcome==="FAILED"?(body.error??{message:"worker failure"}):null,lease_expires_at:null,updated_at:new Date().toISOString()}).eq("id",id).eq("worker_run_id",ident.run_id).in("state",["LEASED","RUNNING"]).select("id,state,result_digest,attempt,worker_run_id,worker_sha,updated_at").single();
  if(updateError)throw new Error(`job terminal transition failed: ${updateError.message}`);
  return {status:outcome,job:updated};
}
Deno.serve(async(req:Request)=>{if(req.method!=="POST")return json({error:"POST required"},405);try{const ident=await githubIdentity(req),admin=adminClient(),body=await req.json().catch(()=>({})) as Record<string,unknown>,action=String(body.action??"selftest");if(action==="selftest")return json({authenticated:true,service:"AUTOHOUSE_OMEGA_WORKER_BRIDGE",version:VERSION,worker:ident,truth_boundary:TRUTH});if(action==="lease")return json(await lease(admin,ident,body));if(action==="start")return json(await startJob(admin,ident,body));if(action==="finish")return json(await finishJob(admin,ident,body));return json({error:"unknown action"},400);}catch(e){return json({error:e instanceof Error?e.message:String(e)},401);}});
