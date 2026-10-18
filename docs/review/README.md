# Independent human review workflow

Task ANV-020, [ADR 0004](../decisions/0004-multilingual-corpus-and-human-review.md). The code and expanded corpus are an implementation slice. Real independent assessments, adjudication and permitted external comparisons remain open acceptance criteria. **New human judgments at delivery: zero.** Synthetic tests are labelled as such and never counted as human evidence.

## Operator boundary and enrollment

This is a local, trusted-operator tool, separate from the production API and feedback store. No server, paid API, hosted model or external account is required. People with access to the entire workspace can read its passages, keys and assessments. Per-reviewer credentials and signed packet contents protect imports and revisions; they do not prove a person's identity, independence or that they read the passages. Do not expose this directory over HTTP or treat it as hosted tenant isolation.

Before distributing packets, privately enroll **two distinct consenting assessors** and a **different adjudicator**. Record real identity-to-pseudonym mapping, consent, language competence and conflicts of interest outside Git. Pseudonyms in example commands are placeholders, not enrolled people. Supply each assessor only their own packet/form and their separate credential. Do not send another assessor's grades, source ranks or the answer-context key. No tool sends messages or contacts people automatically.

Use language-specific batches if appropriate. `--languages en` filters query languages, not candidate passage languages: candidates can be in other languages. Assessors must judge only languages they know and abstain otherwise. Ensure adjudicators can assess the disputed passages; a credential does not confer language competence. The English rubric and AI-authored probes also need native-speaker review before a multilingual study can be claimed.

## Prepare and freeze a pilot

```text
uv run --extra dev python -m anvesha.review_data prepare --download
uv run --extra dev python -m anvesha.intent_evaluation run
uv run --extra dev python -m anvesha.review init --reviewers reviewer-a reviewer-b --adjudicator adjudicator --languages en
uv run --extra dev python -m anvesha.review export --reviewer reviewer-a
uv run --extra dev python -m anvesha.review export --reviewer reviewer-b
uv run --extra dev python -m anvesha.review status
```

The run compares token overlap, direct BM25 and the actual M1 local worker at depth 50. The pool is the deduplicated union of their top ten candidates. Only retrieved IDs enter it; no model invents result URLs. URLs identify records in the pinned dataset, not current Wikipedia destinations. A navigation probe requesting a Wikipedia URL can therefore expose a real limitation, even when an archive passage discusses the target.

The default private workspace is `.anvesha/reviews/xquad-intents-v1`. Initialization refuses to overwrite it. It freezes the complete supplied pool hash, dataset/ranking fingerprints, selected candidates and [binary rubric](rubric-v1.json). It chooses a deterministic pilot of at most **200 pairs**, round-robin across language/intent buckets; this is a bounded pilot, not a statistically representative sample. `--max-pairs 0` selects every eligible pair. At least 20% of each bucket (rounded up) gets independent double assignment; use `--double-fraction 1` for every pair. The report distinguishes selected and eligible pool pairs, queries with candidates, empty query IDs and per-reviewer progress.

Default sessions include development only. Reviewing holdout requires both `--split holdout` (or `all`) and `--release-holdout`, normally in a new `--workspace` after the pipeline is frozen. All article translations share their split. Public holdout data is reserved from project tuning, not secret or guaranteed model-unseen. Reading the baseline holdout report does not authorize training on it.

## Assess and import

Keep calibration outside independent assessment. Use practice queries that are absent from the assigned study query set, and never import an assistant's suggested grade or rationale as a person's independent judgment. If an assigned item is coached, privately record the affected session, reviewer and item, leave that row unjudged, and obtain an unexposed assessor's judgment through a fresh study assignment before counting it as independent. Do not use abstention to hide coaching. The current CLI does **not** enforce coaching exclusions or support reassignment; an operator note is not an import guard. Keep the affected session incomplete until a reviewed replacement workflow is available under ANV-020. Do not delete assignments or edit signed packets to force completion.

An assessor opens their `packets/<pseudonym>/review.html` locally in a browser. The form renders passages as text, makes no network requests and includes no credentials or hidden system/gold labels. Read the rubric and original query, grade each record **1** or **0**, or explicitly **abstain**. Every submitted entry needs a rationale; abstentions also need a reason. Unfinished rows remain unjudged. The form requires a personal-assessment checkbox before downloading responses.

There is no browser autosave. Download progress before closing. To resume, the operator imports the response file, then exports a fresh packet/form with that reviewer's own saved entries. Editing `packet.json` with the same fields is also supported. Do not alter immutable query/document/assignment/rubric fields; signatures reject such changes.

The operator sets `ANVESHA_REVIEW_TOKEN` to the credential for the packet's pseudonym, then imports. On PowerShell, load the existing private key without printing it:

```powershell
$reviewKeys = Get-Content -LiteralPath '.anvesha/reviews/xquad-intents-v1/credentials.json' | ConvertFrom-Json
$env:ANVESHA_REVIEW_TOKEN = $reviewKeys.'reviewer-a'
uv run --extra dev python -m anvesha.review import --packet '.anvesha/reviews/xquad-intents-v1/packets/reviewer-a/reviewer-a-responses.json'
Remove-Item Env:ANVESHA_REVIEW_TOKEN
```

The response download normally goes to the browser's Downloads directory. Move/copy that file into the indicated private packet directory, or pass its actual path. The browser never uploads it. Never paste credentials into Git, issue comments or shell command arguments.

Imports validate the personal-attestation flag, reviewer credential, session/role, signed immutable payload, assignment, binary grade types, explanations and revisions. One invalid row rolls back the whole import. Repeating identical submissions is idempotent for labels; import receipts preserve packet hashes and attestation. Changes to existing labels require a fresh packet and explicit `--revise`. Revisions remain in the database. Stale edits fail, and changing an assessment invalidates any adjudication tied to its older versions.

## Agreement, adjudication and export

`status` reports graded/abstained/pending assignments and resolved pairs separately. Agreement uses only independently double-graded, nonabstained pairs. It reports raw agreement and Cohen's kappa **per reviewer pair**; it does not pool kappa across different people. Kappa is null when marginal label variation makes it undefined. Small samples are descriptive and do not establish reliable population agreement.

Once all assigned reviews for a pair arrive, a disagreement or abstention requires adjudication. The separate adjudicator sees the supplied passage plus both submitted grades/rationales in their own packet:

```text
uv run --extra dev python -m anvesha.review export --reviewer adjudicator
```

Import that person's responses with their own credential. They must resolve to 0/1 with a rationale; no automatic majority vote or model-based adjudication is implemented. Initial reviewers cannot act as the adjudicator. A changed underlying review makes an older adjudication packet stale.

```text
uv run --extra dev python -m anvesha.review finalize
```

Default finalization refuses pending or unresolved work. Explicit `--allow-partial` can export progress, marked partial with full coverage denominators. Exports stay inside the private workspace in immutable revision-fingerprint directories, preserving old snapshots. They contain qrels and a coverage/provenance receipt. Single-reviewed, agreed and adjudicated counts remain separate. A fully reviewed pilot is not the entire corpus or web; empty-result queries are retained as coverage gaps. No quality metric, training, site blocking, feedback update or public publication follows automatically. Further review and release consent are required before any private labels could be added to a public benchmark.

## Reproducibility and remaining study work

```text
uv run --extra dev python -m anvesha.intent_evaluation run --output-dir .anvesha/evaluation/xquad-repeat --compare reports/evaluation/xquad-intents-v1/summary.json
uv run --extra dev python -m anvesha.review_data verify
uv run --extra dev python -m anvesha.intent_evaluation verify
```

Artifact verification is offline and needs no raw passages. It checks every query/system ranking, IDs, input hashes, coverage, derived metrics and rendered report. Default tests use synthetic local fixtures; the optional Node.js check executes the form's save/navigation contract without a browser or package install. Node is not required to use the workflow; a normal browser runs the standalone form.

The workflow consumes the new versioned `candidate-pool.json` format. SciFact's older flat `review-pool.jsonl` remains a legacy unassigned export; adapting it into a frozen session is follow-up work under ANV-020. Actual study completion also needs enrolled people, native-speaker review, independent double labels, adjudication, consented export decisions and permitted external baselines. More representative navigation, locale and current-web sources need their own rights-reviewed acquisition. Neither upstream QA mappings nor AI-authored probes satisfy those requirements.
