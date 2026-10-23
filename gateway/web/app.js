"use strict";
const $ = id => document.getElementById(id);
const show = (id, value) => { $(id).textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2); };
function baseUrl() {
  const raw = $("apiBase").value.trim() || window.location.origin;
  const url = new URL(raw, window.location.origin);
  if (url.protocol !== "https:" && url.hostname !== "localhost" && url.hostname !== "127.0.0.1") throw new Error("HTTPS is required except for local development.");
  if (url.username || url.password || url.search || url.hash) throw new Error("Base URL must not contain credentials, query parameters or a fragment.");
  return url.toString().replace(/\/$/, "");
}
async function request(path, options = {}) {
  const token = $("token").value;
  if (!token) throw new Error("Provide a development/testing access token or connect an approved identity provider.");
  const url = baseUrl() + path;
  const response = await fetch(url, { ...options, headers: { "Accept":"application/json", "Authorization":"Bearer " + token, ...(options.body ? {"Content-Type":"application/json"} : {}), ...options.headers }, cache:"no-store", credentials:"omit", redirect:"error", referrerPolicy:"no-referrer" });
  const body = await response.json().catch(() => ({error:"non_json_response"}));
  if (!response.ok) throw new Error("HTTP " + response.status + ": " + JSON.stringify(body));
  return body;
}
$("submit").addEventListener("click", async () => {
  $("submit").disabled = true; show("status","Submitting…");
  try {
    const contract = JSON.parse($("contract").value);
    if (!contract || typeof contract !== "object" || Array.isArray(contract)) throw new Error("Contract must be a JSON object.");
    if (contract.state !== "REQUESTED") throw new Error("New requests must have state REQUESTED.");
    const result = await request("/v1/tasks", {method:"POST", body:JSON.stringify(contract)});
    show("result", result); show("status", "Request recorded; dispatch performed: " + String(result.dispatch_performed));
    if (result.task_id) $("taskId").value = result.task_id;
  } catch (error) { show("status","Request not confirmed."); show("result",String(error.message || error)); }
  finally { $("submit").disabled = false; }
});
async function lookup(suffix) {
  const id = $("taskId").value.trim();
  if (!id || id.includes("/") || id.includes("\\") || id === "." || id === "..") { show("record","Enter a valid task ID."); return; }
  try { show("record", await request("/v1/tasks/" + encodeURIComponent(id) + suffix)); }
  catch (error) { show("record",String(error.message || error)); }
}
$("getTask").addEventListener("click", () => lookup(""));
$("getAudit").addEventListener("click", () => lookup("/audit"));
$("apiBase").value = window.location.origin === "null" ? "" : window.location.origin;
$("contract").value = JSON.stringify({
  contract_version:"1JGM-GATEWAY-TASK-1.0", task_id:"task-replace-me", idempotency_key:"idem-replace-me",
  initiated_by:"replace-with-authenticated-subject", session_ref:"session-reference", aigc_contract_ref:"existing-aigc-contract-reference",
  target:{kind:"repository",repository:"Lornt1666/AIGC",branch:"main"}, operation:"repo.read_file",
  arguments:{path:"README.md"}, resource_scope:["repository:read"], risk_level:"low", approval_id:null,
  expires_at:new Date(Date.now()+10*60*1000).toISOString(), execution:{timeout_seconds:30,max_output_bytes:10000},
  expected_outputs:["file content"], acceptance_criteria:["result returned with evidence"], state:"REQUESTED", audit_correlation_id:"audit-replace-me"
},null,2);
