# Anvesha: product and research plan

Adopted: 2026-10-16. Company: **Kshurika Consultancy**. Task: **ANV-002**.

Anvesha is an open-source search API that accepts a word or sentence, returns a durable search ID, and lets clients poll for useful ranked results and submit feedback. Its priority is result quality; latency is secondary. It must work without mandatory paid APIs or hosted LLMs.

This document preserves the product direction and research rationale. It is not a completion report. [Milestones](MILESTONES.md) define delivery gates, the [task ledger](tracking/tasks.json) records actual progress, and the [architecture](architecture/README.md) distinguishes the first implementation from future capabilities. Primary sources and their review date are in [RESEARCH.md](RESEARCH.md).

## 1. Product scope and success

The ambition is high-quality web and document search with the convenience of a general search API. Google-level general-web coverage and quality are aspirations requiring evidence, not properties of the MVP. Local businesses, shopping, images, breaking news, navigation, and technical research need different data and ranking. We should prove useful coverage category by category.

Start with technical documentation, research, and authoritative reference material as the intended quality focus. The first executable slice is smaller: locally indexed documents and optional Wikidata entity metadata. Its bundled corpus is demonstration material, not a web index. A user-supplied corpus can make local search useful immediately, subject to the operator's document rights.

The first product returns ranked links, snippets, provenance, and explicit limitations. Generated answers are a later optional layer with separate evaluation. A fluent answer is not evidence of good retrieval.

Measure improvement against specific SearXNG configurations and a simple retrieval baseline, rather than describing every SearXNG deployment as equivalent. SearXNG already has an HTTP API; output formats depend on instance settings. Upstream blocking and source availability are separate problems from queuing. [SearXNG API](https://docs.searxng.org/dev/search_api.html)

| Problem to solve | Intended Anvesha behavior |
| --- | --- |
| Dependence on upstream discovery and ranking | Combine permitted connectors, an owned index, and independently evaluated ranking |
| Snippets omit decisive context | Inspect relevant document sections and expose evidence limitations |
| Complex questions require complementary searches | Plan bounded follow-up searches around distinct unresolved aspects |
| Mirrors and syndicated articles dominate | Cluster duplicates while retaining provenance and original-source links |
| Failures are hard to diagnose | Measure discovery, extraction, ranking, and evidence support separately |
| Long-running requests lose progress | Persist jobs, checkpoints, result snapshots, and explicit terminal states |
| Feedback creates noise or manipulation | Review versioned feedback and release measured improvements |

## 2. Principles that constrain implementation

1. **Preserve intent.** Retain the original query and explicit constraints. Query expansion must not silently erase quoted text, versions, dates, exclusions, or locality.
2. **Discover before judging.** No ranker can select a document that retrieval never found. Diagnose coverage failures separately from ranking failures.
3. **Separate relevance from truth.** A relevant page can be wrong. A ranking value is not a probability of correctness.
4. **Make evidence visible.** Distinguish metadata, snippets, inspected passages, and verified support. Never invent URLs or imply a document was fetched when it was not.
5. **Budget work, even when waiting is acceptable.** Each search needs limits on requests, documents, model work, retries, and elapsed time, plus a reason for stopping.
6. **Keep a usable free path.** Paid providers and hosted models may be optional additions only. The offline baseline must remain testable and runnable.
7. **Carry rights with data.** Access, caching, redistribution, evaluation, and training permissions are different dimensions.
8. **Treat retrieved content as untrusted.** It cannot issue instructions to privileged agents or change connector policy.
9. **Record decisions and gaps.** Follow [AGENTS.md](../AGENTS.md); every meaningful change and unresolved concern belongs to the task ledger.

## 3. Two complementary discovery paths

**Live permitted sources.** Add source-specific APIs, feeds, publisher integrations, and any general search providers whose actual agreement permits our use. Record source lineage because several providers may depend on the same underlying index. More provider names do not necessarily mean independent evidence.

**An owned corpus.** Grow a searchable collection from first-party documents, licensed datasets, permitted crawls, and publisher contributions. Begin with narrow, valuable categories. Expand in response to measured discovery gaps, not an unbounded goal of crawling the whole web.

Common Crawl is a potential acquisition input, not a ready-made search engine or a grant of every underlying content right. Crossref can add bibliographic metadata, with field-specific caveats such as copyrighted abstracts. Wikidata structured entity data is CC0, while other Wikimedia content can have different licences. [Common Crawl terms](https://commoncrawl.org/terms-of-use), [Crossref API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [Wikidata licensing](https://www.wikidata.org/wiki/Wikidata:Licensing)

Every connector needs a versioned rights manifest that records permitted retrieval, retention, transformation, display, redistribution, evaluation, training, attribution, deletion duties, operational limits, and the terms URL/review date. A restrictive source must not leak into a less restrictive cache or learning export through rank fusion.

## 4. Intended quality pipeline

### Interpret and route

Classify intent and extract entities, language, geography, time constraints, quoted phrases, and exclusions. Keep ambiguity when justified: “jaguar” has several plausible meanings. Exact errors and navigational queries should retain a direct literal retrieval path. Do not force every request through deep investigation.

### Generate complementary searches

Retain the original query and add a small, bounded set of alternatives. Complex comparisons may need separate searches for capabilities, costs, and evidence. Prefer distinct aspects over many near-identical paraphrases. Store each subquery's purpose and test expansion against the original intent.

### Retrieve a candidate pool

Use lexical and semantic retrieval on the owned index when available. Merge permitted connector lists using reciprocal rank fusion (RRF) as an initial baseline. Later compare tuned score fusion and learned ranking. RRF is simple and insensitive to incompatible provider score scales; it is not guaranteed to maximize relevance. [OpenSearch RRF documentation](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/rrf/)

### Normalize and cluster

Normalize URLs conservatively; query parameters can change document identity. Cluster exact duplicates first, then evaluate near-duplicate and syndication detection. Preserve all source and rights provenance. Ten copies of one article are not ten independent confirmations.

### Inspect documents

Fetch only where permitted and safe. Extract main text, headings, relevant sections, author information, and dates. Keep publication time, modification time, source-observed time, and fetch time distinct when known. Preserve evidence offsets or passage identifiers. Mark inaccessible or metadata-only material accurately.

### Rerank and assess evidence

Evaluate relevance to the original query, constraint satisfaction, completeness, freshness appropriate to the topic, original sourcing, accessibility, and spam signals. Use LLMs for bounded classification or passage judgments with structured outputs and supplied candidate IDs. Avoid unexplained “truth percentages,” opaque domain prestige as the sole signal, and model-created links.

### Investigate remaining gaps

Search again only for identified missing aspects, stale evidence, unavailable primary documents, or material contradictions. Stop on adequate supported coverage, diminishing useful discovery, cancellation, or resource limits. Report which condition ended the search. A stopped search has not exhausted the web.

### Publish a useful result set

Balance relevance, coverage, and duplication. Diversity is query-dependent: multiple official documentation pages may be appropriate for a technical question. Ground snippets in retrieved content and keep optional generated answers separate from search results.

## 5. Research to test, not assume

The TREC 2025 RAG track provides an example of hybrid sparse/dense retrieval, fusion, reranking, and evaluation of relevance and attribution. Its document corpus and task differ from general live web search. [TREC overview](https://trec.nist.gov/pubs/trec34/papers/Overview_rag.pdf)

Two 2026 research directions are particularly relevant: **Question's Gambit** explores decomposing an information need into complementary searches early; **SIEVE** explores search, structural inspection, and selective fetching. They motivate experiments, not immediate production complexity or claims that a local implementation reproduces published results. [Question's Gambit](https://arxiv.org/abs/2609.14412), [SIEVE](https://arxiv.org/abs/2608.02751)

Self-hosted embedding and reranking models, including the Apache-2.0 Qwen3 variants, are candidates to benchmark against smaller models and lexical baselines. Pin exact model revisions, licences, prompts, and hardware measurements. No model download is required for M1. [Qwen3 Embedding](https://huggingface.co/Qwen/Qwen3-Embedding-8B), [Qwen3 Reranker](https://huggingface.co/Qwen/Qwen3-Reranker-8B)

Search-R1 suggests a later path to learning search behavior, after reliable tasks, rewards, failure examples, and evaluation exist. Reinforcement learning is outside the initial MVP. [Search-R1](https://arxiv.org/abs/2503.09516)

## 6. Request-and-poll product contract

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/searches` | Persist a request and return an ID with HTTP 202 |
| `GET /v1/searches/{id}` | Return state, phase, warnings, and available result version |
| `GET /v1/searches/{id}/results` | Read a stable result snapshot |
| `POST /v1/searches/{id}/feedback` | Record feedback against the actual snapshot and optional result |
| `POST /v1/searches/{id}/cancel` | Stop remaining work without a stale worker publishing afterward |
| `DELETE /v1/searches/{id}` | Delete retained job data and associated feedback |

Only the query needs to be mandatory for a client. M1 also accepts optional sources and result limit. Language, region, freshness, and search-depth controls are later capabilities and must not be advertised until implemented. Exact implemented fields belong in [API documentation](API.md).

Durable acceptance precedes the 202 response. Jobs require authenticated ownership and client-scoped idempotency; opaque IDs alone are insufficient. Requests with a reused key and different parameters must conflict. Workers operate separately from HTTP handling and assume at-least-once execution, with leases, retry ceilings, cancellation checks, and atomic result publication.

Use explicit `queued`, `running`, `completed`, `completed_partial`, `failed`, and `cancelled` states. A successful search with zero matches is valid. Partial execution and limited corpus coverage are different concepts and should be explained separately. Poll responses report observable phases rather than invented percentages.

M1 supports conditional status polling with ETags and publishes a single final result version; it must not imply live partial snapshots exist. Status, results, and feedback identify the pipeline as `m1-rrf-v1`. Pin pagination and feedback to a result version. The longer-term interface can add intermediate immutable snapshots, retention-expiry semantics, and incremental results.

## 7. Feedback and learning

Collect overall usefulness, result-level relevance, reason categories such as outdated or wrong locale, and optional comments. Later evaluate pairwise preferences. Bind feedback to the authenticated client, search, result version, and pipeline version. Repeated submissions by one client should update their rating rather than create unlimited independent votes.

M1 stores feedback for inspection with the job's `m1-rrf-v1` pipeline version. Improvement follows a reviewed process:

1. Attribute the failure to discovery, interpretation, extraction, ranking, or evidence support.
2. Prioritize better sources or deterministic fixes where appropriate.
3. Curate consented and rights-compatible learning examples, including hard negatives.
4. Evaluate changes on an untouched holdout and relevant query strata.
5. Release versioned changes with rollback and monitor meaningful regressions.

Clicks are biased by position and presentation; they are not direct relevance labels. Guard against coordinated manipulation and accidental repeated votes. A single vote must not automatically promote, blacklist, or retrain production behavior. [Learning-to-rank research](https://arxiv.org/abs/1608.04468)

Separate operational records from explicitly opted-in learning data. Do not publish private queries or comments. Hashes alone do not make query data anonymous. Define retention and deletion before offering a hosted service.

## 8. Evaluation before quality claims

Build an initial 500-query human-judged set, then expand it. Cover navigation, exact phrases, ambiguity, factual questions, comparisons, temporal constraints, technical research, and adversarial pages. Add independent language evaluations before claiming strong multilingual performance. A small fixture suite validates behavior; it is not this benchmark.

Compare documented SearXNG configurations, a simple retrieval/reranking baseline, Anvesha on identical candidates, and the full Anvesha pipeline. Identical-candidate comparisons isolate ranking; end-to-end comparisons include discovery. Freeze source snapshots where feasible and record dates/configuration for live comparisons.

Pool candidates for human judgments, blind system identities, double-label a subset, measure assessor disagreement, and retain a holdout. LLM judges can assist, but should not be the sole evaluators of a system using related models. Candidate recall is relative to the judged pool, not the entire web.

| Proposed public-pilot gate | Initial target, to recalibrate after baselines |
| --- | --- |
| Ranking | At least 10% relative nDCG@10 improvement over the chosen baseline; report uncertainty |
| Human usefulness | At least 55% preference excluding ties, with an interval supporting improvement |
| Core query categories | No material regression in navigation or explicit constraints |
| URL integrity | Every result URL comes from retrieval or validated discovery |
| Snippet support | At least 95% of audited supporting snippets substantiate their associated claims |
| Durability | Recovery or explicit terminal failure in fault tests; no silently lost accepted jobs |
| Economics | Publish measured compute, source calls, and cost per useful completed search |

These are proposed release gates, not achieved measurements. A Google comparison needs a separate, time-stamped, permitted human study. Success on a research question-answering benchmark does not establish general-web parity.

## 9. Security, privacy, and operational limits

M1 has no arbitrary URL fetching and no LLM. Its optional live connector uses a fixed approved endpoint, bounded responses, timeouts, validated entity identifiers, and rejected redirects. Authentication and ownership apply to all search data. Secrets and raw provider errors must not be returned or written into handoff notes.

Before adding general fetching, implement SSRF-safe DNS and redirect handling, private-network protections, parser isolation, media/size/time limits, robots and rights policy, and audit tests. Before LLM reading/ranking, isolate untrusted document text from instructions and privileged tools, validate output schemas and candidate membership, and test prompt-injection failures. Prompt wording alone is not a security boundary. [OWASP SSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html), [OWASP prompt-injection guidance](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

Hosted operation additionally needs quotas, resource ceilings, feedback abuse controls, TLS, secret rotation, backups/restores, retention automation, deletion semantics, observability, and a documented incident process. The localhost MVP is not a public-service deployment recommendation.

## 10. Open source, providers, and company ownership

Use **Apache-2.0 for independently written Anvesha code**, retain contributor attribution, and maintain third-party notices. Model weights, datasets, and retrieved documents keep their own licences. No SearXNG code is copied into the Apache core. SearXNG uses AGPL; integrating or adapting it requires separate analysis. A process or API boundary is not automatic clearance. [Apache licence](https://www.apache.org/licenses/LICENSE-2.0.html), [SearXNG licence notice](https://raw.githubusercontent.com/searxng/searxng/master/README.rst)

Kshurika Consultancy can maintain the project and brand while permitting commercial use of the code. Do not add non-commercial or anti-competitor restrictions and still describe that licence as open source. Name, trademark, domain, and package-name clearance remains a release task; the selected project name is **Anvesha** and the repository is [Kshurika-Consultancy/anvesha](https://github.com/Kshurika-Consultancy/anvesha).

Provider constraints reviewed on 2026-10-16 materially affect the plan:

| Source | Planning consequence |
| --- | --- |
| Google Custom Search JSON API | Closed to new customers; existing users must transition by 2027-01-01. Not a new-product foundation |
| Bing Search APIs | Retired on 2025-08-11. Do not build around the old standalone APIs |
| Brave standard terms | Storage, redistribution, API replacement, and AI improvement restrictions require suitable separate terms for this use |
| Common Crawl | Underlying rights remain; extraction and indexing still need engineering |
| Open Web Index | Published personal/non-commercial/research restriction prevents assuming company production eligibility |
| Marginalia/Mwmbl | Free API or dataset terms include non-commercial restrictions; review the precise offering |
| SearXNG | Software rights do not grant upstream results rights |

See [RESEARCH.md](RESEARCH.md) for direct evidence and uncertainty. Public availability, a provider key, payment, or a free-to-users service is not a blanket reuse permission. Launch review must address actual contracts, processing locations, privacy obligations, retention, notices, and deletion. India's DPDP commencement is phased; use the official notification and current advice for the specific deployment rather than assuming one effective date for every provision.

## 11. Free operation and sustainable economics

Offer free self-hosted software with a local corpus and optional local models. A future sponsored public service can offer published quotas. Optional compatible providers can extend coverage without becoming a required dependency. The initial no-paid-provider setup has narrower coverage; more computation cannot replace undiscovered documents or missing rights.

Track CPU/GPU time, model tokens where relevant, connector calls, fetch volume, bytes stored, bandwidth, failure/retry rates, and human evaluation effort. Optimize cost per useful completed search, not only latency. Queue admission must remain bounded. Invest extra work where ablation experiments show quality gains.

## 12. Delivery sequence

The original planning estimate of roughly 13–16 weeks for two experienced engineers plus retrieval/evaluation support was an indicative pilot estimate, not a commitment. Deliver by evidence-backed gates; staffing, corpus acquisition, rights review, and evaluation effort can change the schedule.

The sequence is: **M0 foundations → M1 durable local MVP → M2 evaluation and hosted hardening → M3 evidence inspection and retrieval quality → M4 reviewed learning and adaptive search → M5 scaling when measured → M6 public pilot.** Dependencies and acceptance criteria live in [MILESTONES.md](MILESTONES.md) and [tasks.json](tracking/tasks.json).

The deliberate MVP departure from the earlier target stack is SQLite WAL/FTS5 instead of PostgreSQL/OpenSearch/workflow infrastructure. It proves the full asynchronous lifecycle with little setup and no paid dependency. The future stack remains an option when index size, write contention, worker topology, or recovery needs justify it. See [ADR 0001](decisions/0001-local-first-mvp.md).

Whole-web crawling, reinforcement learning, extensive autonomous-agent graphs, automatic production retraining, generated answers, and broad quality claims remain outside the first slice. The first deliverables are the tracked foundation, explicit source policies, a working polling API, stable results and feedback, and reproducible offline validation.
