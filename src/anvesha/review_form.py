"""ANV-020: standalone review form; no network, executable document HTML or keys."""

import base64
import hashlib
import html
import json

STYLE = """
body{font:17px/1.55 system-ui,sans-serif;max-width:1000px;margin:32px auto;
padding:0 24px;color:#17212d;background:#f5f7fa}
main,header,footer{background:white;padding:24px;border:1px solid #ccd5e0;
border-radius:12px;margin:18px 0}
button,select,textarea{font:inherit;padding:10px;margin:8px 4px 8px 0}
button{cursor:pointer}textarea{box-sizing:border-box;width:100%;min-height:90px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}
.muted{color:#4c596b}label{display:block}#notice{color:#8c2b14}details{margin:16px 0}
"""
SCRIPT = """
const payload = document.getElementById('payload').textContent;
const bytes = Uint8Array.from(atob(payload), c => c.charCodeAt(0));
const packet = JSON.parse(new TextDecoder().decode(bytes));
let index = 0;
const el = id => document.getElementById(id);
const text = (id, value) => { el(id).textContent = value; };
function store() {
  if (!packet.items.length) return;
  const row = packet.items[index], g = el('grade').value;
  row.grade = g === '0' ? 0 : g === '1' ? 1 : null;
  row.rationale = el('rationale').value;
  row.abstain_reason = g === 'abstain' ? el('abstain').value : null;
}
function draw() {
  const row = packet.items[index];
  text('progress', row ? `${index + 1} / ${packet.items.length}` : 'No assigned items.');
  el('card').hidden = !row;
  if (!row) return;
  text('query', row.query.text);
  text('constraints', row.query.constraints.join('\\n') || 'No additional explicit constraints.');
  text('title', row.document.title);
  text('passage', row.document.text);
  text('source', row.document.url);
  text('rights', `${row.document.license} - ${row.document.attribution}; ` +
    `passage language: ${row.document.language}`);
  el('grade').value = row.grade === 0 ? '0' : row.grade === 1 ? '1' :
    row.abstain_reason ? 'abstain' : '';
  el('rationale').value = row.rationale || '';
  el('abstain').value = row.abstain_reason || '';
  el('prior').hidden = !row.review_labels;
  text('prior', row.review_labels ? JSON.stringify(row.review_labels, null, 2) : '');
}
el('previous').onclick = () => { store(); index = Math.max(0, index - 1); draw(); };
el('next').onclick = () => {
  store(); index = Math.min(packet.items.length - 1, index + 1); draw();
};
el('save').onclick = () => {
  store(); packet.human_attestation = el('attest').checked;
  if (!packet.human_attestation) {
    text('notice', 'Confirm your personal assessment before downloading.'); return;
  }
  const finished = packet.items.filter(r => r.grade !== null || r.abstain_reason);
  if (!finished.length || finished.some(r => !r.rationale.trim() ||
    (r.grade === null && !r.abstain_reason.trim()))) {
    text('notice', 'Each grade or abstention needs a rationale; abstentions need a reason.');
    return;
  }
  const blob = new Blob([JSON.stringify(packet, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob), a = document.createElement('a');
  a.href = url; a.download = `${packet.reviewer}-responses.json`; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  text('notice', 'Saved locally. Return only the response file. Keep credentials separate.');
};
text('identity', `${packet.role}: ${packet.reviewer}. Session ${packet.session}.`);
text('rubric', JSON.stringify(packet.rubric, null, 2)); draw();
"""


def _hash(text):
    return base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()


def render_form(packet):
    payload = base64.b64encode(json.dumps(packet, ensure_ascii=False).encode()).decode()
    policy = (
        f"default-src 'none'; script-src 'sha256-{_hash(SCRIPT)}'; "
        f"style-src 'sha256-{_hash(STYLE)}'; base-uri 'none'; "
        "form-action 'none'; connect-src 'none'"
    )
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="{html.escape(policy, quote=True)}">
<title>Anvesha independent review</title><style>{STYLE}</style>
<header><h1>Anvesha independent review</h1><p id="identity"></p>
<p class="muted">Private offline packet. No requests or autosave.
Download your progress before closing. Treat passages as untrusted text.
Your operator verifies assessor independence and language competence.</p>
<details><summary>Frozen grading rubric</summary><pre id="rubric"></pre></details></header>
<main><p id="progress"></p><div id="card"><h2 id="query"></h2><pre id="constraints"></pre>
<h3 id="title"></h3><pre id="passage"></pre><p id="source" class="muted"></p>
<p id="rights" class="muted"></p><pre id="prior" hidden></pre>
<label>Judgment <select id="grade"><option value="">Unfinished</option>
<option value="1">1 - Useful</option><option value="0">0 - Not useful / constraint failure</option>
<option value="abstain">Abstain</option></select></label>
<label>Rationale<textarea id="rationale"></textarea></label>
<label>Abstention reason<textarea id="abstain"></textarea></label>
</div><button id="previous">Previous</button><button id="next">Next</button></main>
<footer><label><input id="attest" type="checkbox">I personally assessed these entries,
am competent to judge their languages, and did not generate or copy
another assessor's grades.</label>
<button id="save">Download responses / progress</button>
<p id="notice" role="status"></p>
<p class="muted">Import requires your separate credential. Attestation and a credential
do not independently prove identity. No production training follows this review.</p></footer>
<script id="payload" type="application/octet-stream">{payload}</script>
<script>{SCRIPT}</script></html>
"""
