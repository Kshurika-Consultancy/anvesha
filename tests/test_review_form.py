"""ANV-020: optional Node DOM simulation of the browser form's save contract."""

import base64
import json
import shutil
import subprocess

import pytest

from anvesha.review_form import SCRIPT


@pytest.mark.skipif(shutil.which("node") is None, reason="Optional Node.js form runtime check")
def test_form_navigation_attestation_unicode_and_download_contract():
    packet = {
        "reviewer": "fixture",
        "role": "reviewer",
        "session": "synthetic",
        "rubric": {"id": "fixture"},
        "signature": "untouched",
        "human_attestation": False,
        "items": [
            {
                "pair_id": f"p-{i}",
                "query": {"text": "\u092a\u094d\u0930\u0936\u094d\u0928", "constraints": []},
                "document": {
                    "title": "<img onerror=bad()>",
                    "text": "<script>bad()</script>",
                    "url": "https://example.org",
                    "license": "Apache-2.0",
                    "attribution": "Synthetic fixture",
                    "language": "hi",
                },
                "grade": None,
                "rationale": "",
                "abstain_reason": None,
                "revision": 0,
            }
            for i in range(2)
        ],
    }
    test_script = r"""
const vm = require('node:vm');
let input=''; process.stdin.on('data', s => input += s);
process.stdin.on('end', async () => {
  const {script, payload} = JSON.parse(input), elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, {textContent:'',value:'',checked:false,hidden:false});
    return elements.get(id);
  };
  get('payload').textContent=payload;
  let saved;
  const context={document:{getElementById:get,createElement:()=>({click(){}})},
    TextDecoder,Uint8Array,atob,Blob,
    URL:{createObjectURL:b=>{saved=b;return 'blob:fixture'},revokeObjectURL:()=>{}},
    setTimeout:f=>f()};
  vm.runInNewContext(script,context);
  const displayed = get('query').textContent;
  get('grade').value='0'; get('rationale').value='Synthetic rationale';
  get('next').onclick();
  get('save').onclick();
  if (saved) throw Error('Unattested save unexpectedly succeeded');
  get('attest').checked=true; get('save').onclick();
  const output=JSON.parse(await saved.text());
  process.stdout.write(JSON.stringify({displayed,output}));
});
"""
    payload = base64.b64encode(json.dumps(packet, ensure_ascii=False).encode()).decode()
    result = subprocess.run(
        [shutil.which("node"), "-e", test_script],
        input=json.dumps({"script": SCRIPT, "payload": payload}),
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
        encoding="utf-8",
    )
    data = json.loads(result.stdout)
    assert data["displayed"] == packet["items"][0]["query"]["text"]
    assert data["output"]["human_attestation"] is True
    assert data["output"]["signature"] == "untouched"
    assert data["output"]["items"][0]["grade"] == 0
    assert data["output"]["items"][1]["grade"] is None
