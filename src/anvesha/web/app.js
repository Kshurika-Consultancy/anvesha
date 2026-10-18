"use strict";
// ANV-022: no external assets, telemetry, storage, generated HTML or secret URLs.
const $ = (id) => document.getElementById(id);
const state = { key: "", capabilities: null, job: null, controller: null, version: null, next: null, seen: new Set() };
const messages = {
  invalid_api_key: "The access key was not accepted. Check your instance key.",
  llm_not_configured: "Configure a local model with anvesha setup --model YOUR_MODEL, or explicitly choose the lexical baseline.",
  llm_local_source_only: "LLM ranking currently supports your local collection only.",
  search_not_found: "This search is no longer available to this key.",
  results_not_available: "Results are not ready yet.",
};
function error(message) { $("error").textContent = message; $("error").hidden = !message; }
function controls() {
  const busy = Boolean(state.controller);
  $("search").disabled = !state.key || !$("query").value.trim() || busy || ($("ranking").value === "llm" && !state.capabilities?.llm_configured);
  $("ranking").disabled = busy;
  $("cancel").hidden = !busy || !state.job;
}
async function request(path, options = {}, signal) {
  const response = await fetch(path, { ...options, signal, credentials: "omit", cache: "no-store", redirect: "error", headers: { "X-API-Key": state.key, ...(options.body ? { "Content-Type": "application/json" } : {}) } });
  if (!response.ok) {
    let detail;
    try { detail = (await response.json()).detail; } catch { /* No response text is rendered. */ }
    throw new Error(messages[detail] || `Request could not be completed (HTTP ${response.status}).`);
  }
  return response.status === 204 ? null : response.json();
}
function clearResults() {
  $("results").replaceChildren(); $("results-panel").hidden = true;
  $("warnings").hidden = true; $("more").hidden = true;
  state.seen.clear(); state.version = null; state.next = null;
}
function disconnect() {
  state.controller?.abort(); state.controller = null; state.key = "";
  state.capabilities = null; state.job = null; clearResults();
  $("query").value = "";
  $("api-key").value = ""; $("connect-form").hidden = false;
  $("connection-state").hidden = true; $("job-panel").hidden = true;
  $("empty-state").hidden = false; $("collection-note").textContent = "Connect to see your collection.";
  $("model-note").textContent = "LLM ranking uses your configured endpoint. A local gateway may forward to external providers.";
  controls();
}
$("connect-form").addEventListener("submit", async (event) => {
  event.preventDefault(); error(""); $("connect").disabled = true;
  state.key = $("api-key").value.trim();
  try {
    state.capabilities = await request("/v1/capabilities");
    $("api-key").value = ""; $("connect-form").hidden = true; $("connection-state").hidden = false;
    $("collection-note").textContent = `${state.capabilities.document_count} imported documents`;
    $("model-note").textContent = state.capabilities.llm_configured
      ? `Model configured · ${state.capabilities.llm_endpoint_scope} endpoint. Gateway downstream routing is not verified by Anvesha.`
      : messages.llm_not_configured;
    $("query").focus();
  } catch (problem) { disconnect(); error(problem.message || "Connection failed."); }
  finally { $("connect").disabled = false; controls(); }
});
$("disconnect").addEventListener("click", () => { disconnect(); error(""); });
$("query").addEventListener("input", controls);
$("ranking").addEventListener("change", controls);
function showJob(job) {
  $("job-panel").hidden = false;
  const labels = { queued: "Waiting for the worker", running: "Researching your collection", completed: "Search complete", completed_partial: "Search complete with a fallback", failed: "Search could not complete", cancelled: "Search cancelled" };
  $("job-status").textContent = labels[job.state] || "Checking search";
  $("job-detail").textContent = `${job.id} · ${job.phase.replaceAll("_", " ")} · requested ranking: ${job.ranking}`;
  const codes = job.warnings || [];
  $("warnings").hidden = codes.length === 0;
  $("warnings").textContent = codes.some((code) => code.startsWith("llm:"))
    ? `The requested model stage could not complete. Showing lexical results. Details: ${codes.join(", ")}`
    : codes.join(", ");
}
function safeLink(value) {
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : null; }
  catch { return null; }
}
function element(tag, text, className) {
  const node = document.createElement(tag); node.textContent = text;
  if (className) node.className = className;
  return node;
}
function renderResult(item, jobId, version) {
  const row = element("li", "", "result");
  row.append(element("div", item.url, "result-url"));
  const heading = element("h3", ""); const destination = safeLink(item.url);
  const title = element(destination ? "a" : "span", item.title.slice(0, 500));
  if (destination) { title.href = destination; title.target = "_blank"; title.rel = "noopener noreferrer"; title.referrerPolicy = "no-referrer"; }
  heading.append(title); row.append(heading, element("p", item.snippet.slice(0, 2000)));
  const method = item.ranking_method === "llm_rerank" ? "LLM reordered" : "Lexical order";
  row.append(element("div", `${method} · ${item.evidence_status} · ${item.license} · ${item.attribution}`, "result-meta"));
  const feedback = element("div", "", "feedback"); const buttons = [];
  const receipt = element("span", "", "feedback-status"); receipt.setAttribute("role", "status");
  for (const [label, rating] of [["Useful", 1], ["Not useful", -1]]) {
    const button = element("button", label); button.type = "button"; button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", `${label}: ${item.title.slice(0, 100)}`);
    button.addEventListener("click", async () => {
      if (state.job?.id !== jobId) return;
      buttons.forEach((entry) => { entry.disabled = true; });
      try {
        await request(`/v1/searches/${jobId}/feedback`, { method: "POST", body: JSON.stringify({ version, result_id: item.id, rating, learning_opt_in: false }) });
        buttons.forEach((entry) => entry.setAttribute("aria-pressed", String(entry === button)));
        receipt.textContent = "Saved · learning off";
      } catch (problem) { receipt.textContent = problem.message || "Could not save feedback."; }
      finally { buttons.forEach((entry) => { entry.disabled = false; }); }
    });
    buttons.push(button); feedback.append(button);
  }
  feedback.append(receipt); row.append(feedback); $("results").append(row);
}
async function loadPage(offset, signal) {
  const jobId = state.job.id;
  const params = new URLSearchParams({ offset: String(offset), limit: "10" });
  if (state.version !== null) params.set("version", String(state.version));
  const page = await request(`/v1/searches/${jobId}/results?${params}`, {}, signal);
  if (state.job?.id !== jobId || signal?.aborted) return;
  state.version = page.version; state.next = page.next_offset;
  for (const item of page.results) {
    if (!state.seen.has(item.id)) { state.seen.add(item.id); renderResult(item, jobId, page.version); }
  }
  $("results-panel").hidden = false; $("empty-state").hidden = true;
  $("results-count").textContent = `${state.seen.size} of ${page.total} results`;
  $("more").hidden = state.next === null;
  if (page.total === 0) $("results").append(element("li", "No matching documents were found in this collection.", "empty-state"));
}
function pause(milliseconds, signal) {
  return new Promise((resolve, reject) => {
    const cancel = () => { clearTimeout(timer); reject(new DOMException("Stopped", "AbortError")); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", cancel); resolve(); }, milliseconds);
    signal.addEventListener("abort", cancel, { once: true });
    if (signal.aborted) cancel();
  });
}
$("search-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if ($("search").disabled) return;
  error(""); clearResults(); state.job = null;
  const controller = new AbortController(); state.controller = controller; controls();
  try {
    let job = await request("/v1/searches", { method: "POST", body: JSON.stringify({ query: $("query").value, sources: ["local"], limit: 20, ranking: $("ranking").value }) }, controller.signal);
    if (controller.signal.aborted || state.controller !== controller) return;
    if (!/^srch_[a-f0-9]{32}$/.test(job.id)) throw new Error("Invalid search identifier.");
    state.job = job; controls();
    while (true) {
      showJob(job);
      if (["completed", "completed_partial"].includes(job.state)) { await loadPage(0, controller.signal); break; }
      if (["failed", "cancelled"].includes(job.state)) break;
      await pause(Math.max(500, Math.min(5000, job.next_poll_after_ms || 1000)), controller.signal);
      job = await request(`/v1/searches/${job.id}`, {}, controller.signal);
      if (controller.signal.aborted || state.controller !== controller) return;
      state.job = job;
    }
  } catch (problem) { if (problem.name !== "AbortError") error(problem.message || "Search failed."); }
  finally { if (state.controller === controller) state.controller = null; controls(); }
});
$("cancel").addEventListener("click", async () => {
  if (!state.job) return;
  const jobId = state.job.id; $("cancel").disabled = true;
  try { const job = await request(`/v1/searches/${jobId}/cancel`, { method: "POST" }); if (state.job?.id === jobId) { state.controller?.abort(); state.controller = null; state.job = job; showJob(job); if (job.results_available) await loadPage(0); } }
  catch (problem) { error(problem.message || "Cancellation failed."); }
  finally { $("cancel").disabled = false; controls(); }
});
$("more").addEventListener("click", async () => {
  if (state.next === null) return; $("more").disabled = true;
  try { await loadPage(state.next); } catch (problem) { error(problem.message || "Could not load results."); }
  finally { $("more").disabled = false; }
});
$("connect").disabled = false;
controls();
