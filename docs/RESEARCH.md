# Research and source-rights register

Reviewed: **2026-10-16**. Task: **ANV-002**. Maintainer: Kshurika Consultancy.

This is a dated primary-source bibliography supporting [PLAN.md](PLAN.md). Findings are paraphrases; proposed applications are engineering judgments. Published experiments do not demonstrate Anvesha's quality. Terms can change and account-specific agreements can override standard terms. Recheck a source before adding a connector, exporting a dataset, training a model, or launching a hosted deployment.

The operational permissions for enabled connectors belong in `policies/sources/`; this research register does not itself enable a source or grant permission. Record ambiguous rights as unresolved, not allowed.

## Retrieval and agentic search

| Reference | What it supports | Proposed use and limitation |
| --- | --- | --- |
| [TREC 2025 RAG overview, published March 2026](https://trec.nist.gov/pubs/trec34/papers/Overview_rag.pdf) | A multi-stage retrieval baseline and separate relevance, coverage, attribution, and agreement assessment | Use a strong hybrid baseline and stage-specific evaluations. The track's corpus/task are not the live web |
| [Question's Gambit: The First Move Matters in Agentic Deep Search, September 2026](https://arxiv.org/abs/2609.14412) | Research on initial query decomposition for deep-search agents | Test complementary query planning on complex intents. Do not assume results transfer to different models or sources |
| [Search, Inspect, Fetch: Exploiting Structure-Aware Boolean Retrieval for Deep-Search Agents, August 2026](https://arxiv.org/abs/2608.02751) | The SIEVE approach to structured retrieval and selective inspection/fetching | Preserve document structure and compare selective section reading with full-text reading |
| [Search-R1, March 2025](https://arxiv.org/abs/2503.09516) | Learning interleaved reasoning and search using reinforcement learning | Later experiment after reward quality and reproducible evaluation exist; not an MVP requirement |
| [OpenSearch reciprocal rank fusion documentation](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/rrf/) | Rank-based fusion and its tradeoffs against score normalization | RRF is a transparent baseline; compare alternatives instead of treating it as optimal |
| [Qwen3-Embedding-8B official model card](https://huggingface.co/Qwen/Qwen3-Embedding-8B) and [Qwen3-Reranker-8B official model card](https://huggingface.co/Qwen/Qwen3-Reranker-8B) | Model purpose, published evaluation, and Apache-2.0 licence metadata | Benchmark optional local models; pin revision/licence and measure hardware cost. Model-card claims are not Anvesha measurements |
| [Unbiased Learning-to-Rank with Biased Feedback](https://arxiv.org/abs/1608.04468) | Position bias in implicit feedback and methods to account for it | Preserve presentation context and avoid equating clicks with relevance |
| [The Vulnerability of LLM Rankers to Prompt Injection Attacks, February 2026](https://arxiv.org/abs/2602.16752) | Attacks targeting ranking judgments via document instructions | Add adversarial ranking evaluation before integrating LLM rankers |

Research validation must record dataset rights, query strata, baseline, candidate pools, model revisions, prompts, inference parameters, seeds where relevant, compute budget, and uncertainty. Reproducing a paper's method is different from reproducing its results. Do not train on the holdout or use a production model as the sole judge of its own outputs.

## SearXNG and upstream services

| Primary source | Finding at review | Decision for Anvesha |
| --- | --- | --- |
| [SearXNG Search API](https://docs.searxng.org/dev/search_api.html) | HTTP API supports configurable output formats; unconfigured formats can return 403, and many public instances disable them | Do not claim SearXNG lacks an API. Compare a documented configuration |
| [SearXNG limiter documentation](https://docs.searxng.org/admin/searx.limiter) | Explains anti-abuse behavior and upstream blocking context | Durable queues do not solve upstream permission or availability limits |
| [SearXNG source README](https://raw.githubusercontent.com/searxng/searxng/master/README.rst) | Identifies AGPL-3.0-or-later licensing | Independent Apache core; no copied SearXNG implementation |
| [Google Custom Search JSON API overview](https://developers.google.com/custom-search/v1/overview) | Closed to new customers; existing customers must transition by 2027-01-01 | Exclude as a new mandatory foundation |
| [Microsoft Bing Search APIs retirement announcement](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement) | Announces retirement on 2025-08-11 | Do not target the retired standalone APIs |
| [Brave Search API terms, updated 2026-09-01](https://api-dashboard.search.brave.com/terms-of-service) | Standard terms restrict non-transient storage, redistribution, API replacement, and use of results to create/evaluate/improve AI services | No default connector approval. Obtain applicable terms covering Anvesha's actual lifecycle if pursued |
| [Google machine-generated traffic policy](https://developers.google.com/search/docs/essentials/spam-policies#machine-generated-traffic) | Identifies unpermitted automated search queries as a policy violation | Do not design reliability around scraping Google result pages |

Buying requests or using SearXNG does not supply the missing rights to cache, redistribute, evaluate, or learn from upstream results. A bring-your-own-key option still needs accurate operator guidance and source-specific restrictions. Provider failure should be observable, not silently replaced by prohibited scraping.

## Potential free sources and content boundaries

| Source | Rights/operational evidence | Scope decision |
| --- | --- | --- |
| [Wikidata licensing](https://www.wikidata.org/wiki/Wikidata:Licensing) | Structured data in main, Property, Lexeme, and EntitySchema namespaces is CC0; other namespaces have different terms | Optional M1 entity labels/descriptions from the structured API. No assumption that Wikipedia articles or every Wikimedia page are CC0 |
| [Wikimedia User-Agent Policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy) and [MediaWiki API etiquette](https://www.mediawiki.org/wiki/API:Etiquette) | Identify clients and follow courteous, bounded API use | Fixed endpoint, clear User-Agent, request/response limits, timeouts, backoff where applicable; free access is not unlimited capacity |
| [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) | Public metadata API without required signup; some abstracts can remain copyrighted | Candidate later connector. Review exact fields and preserve provenance; do not apply a blanket licence to abstracts |
| [Common Crawl terms](https://commoncrawl.org/terms-of-use) | Crawled content can carry separate owner terms and third-party rights | Candidate corpus-acquisition input. No blanket content clearance or general-search API assumption |
| [Open Web Index licence](https://openwebsearch.eu/owil-current/) | Current text limits use to personal/non-commercial/research purposes and includes attribution/underlying-rights conditions | Not approved for a company production API based only on this licence |
| [Marginalia API documentation](https://about.marginalia-search.com/article/api/) | Free non-commercial offering uses CC-BY-NC-SA 4.0; commercial offering is separate | No mandatory dependency and no assumption that free-to-users means non-commercial |
| [Mwmbl terms, effective 2025-05-10](https://mwmbl.org/terms) | Dataset provisions use CC-BY-NC-SA 4.0; code uses AGPL; automated use has conditions | Research reference only until the exact intended integration is reviewed |
| Operator-provided local corpus | Rights depend on each input, not on the ingestion command | Operator must review rights and provide licence/attribution. A successful import is not a legal determination |
| Bundled Anvesha demonstration corpus | First-party synthetic descriptions under the repository's Apache-2.0 licence | Clearly label as demo material. It validates the lifecycle, not web coverage or relevance quality |

M1 Wikidata output is entity metadata, not inspected evidence from arbitrary websites. Validating an entity identifier or constructing its canonical URL does not verify the truth of its description. Keep `metadata_only` visible.

## Software, data, brand, and privacy

| Primary source | Consequence |
| --- | --- |
| [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0.html) | Chosen for independently written code; retain applicable notices and respect its conditions |
| [Open Source Definition](https://opensource.org/osd) | Do not add non-commercial or anti-competitor restrictions to a licence presented as open source |
| [SearXNG AGPL notice](https://raw.githubusercontent.com/searxng/searxng/master/README.rst) | Any future copied/adapted AGPL component requires separate licence analysis; an API/process boundary is not automatic clearance |
| [India DPDP commencement notification, November 2025](https://www.meity.gov.in/static/uploads/2025/11/c56ceae6c383460ca69577428d36828b.pdf) | Commencement is phased. Review obligations against the actual launch date, data flows, jurisdiction, and current rules |

Do not conflate code ownership, service branding, database rights, model licences, and document copyright. Anvesha's Apache licence does not relicense imported content. Name/domain/package/trademark clearance remains a public-release task. This register is engineering due diligence, not a claim that every future deployment is legally cleared.

Learning consent must be separate from operational storage. Queries and comments can contain personal information; hashing does not reliably anonymize them. Track retention, deletion, access control, and export purpose. Keep raw client data out of public fixtures and development handoffs.

## Implementation and security references

| Reference | Application |
| --- | --- |
| [SQLite WAL](https://www.sqlite.org/wal.html) | Supports the single-host MVP tradeoff; do not put the shared database on a network filesystem or assume distributed coordination |
| [SQLite FTS5](https://www.sqlite.org/fts5.html) | Local lexical index and ranking primitives; escape natural-language input rather than passing raw query operators |
| [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) | Basis for future arbitrary-fetch controls and current fixed-destination design |
| [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | Separate untrusted content from instructions; constrain privileges and validate outputs before adding model stages |

## 2026-10-16 evaluation addition (ANV-019)

[SciFact's upstream licence](https://github.com/allenai/scifact/blob/master/LICENSE.md) separates CC-BY-4.0 claims/evidence annotations from its S2ORC-derived abstract database under [ODC-By-1.0](https://opendatacommons.org/licenses/by/1-0/). The [SciFact paper](https://aclanthology.org/2020.emnlp-main.609/) describes the scientific claim/evidence task; relevant evidence can support or refute a claim. The [official BEIR repository](https://github.com/beir-cellar/beir) supplies the formatted SciFact download and MD5, and defers dataset licensing to original owners. These sources support the narrow offline evaluation decision, not permission to redistribute underlying articles or a general-web quality claim.

The [versioned source manifest](../policies/sources/beir_scifact_evaluation.json), [dataset snapshot](../benchmarks/scifact-v1/README.md), and [methodology](EVALUATION.md) record actual transformations, hashes, attribution and limits. Commit 500 query/annotation records and document IDs; keep raw abstracts local. Use published labels without representing them as new Anvesha assessments. ANV-020 tracks broader representative strata and independent human review.

## How to update this register

For a material new fact or changed term, record the review date, primary URL, narrow supported finding, affected connector/task, and resulting decision. Preserve important historical constraints in the decision log instead of overwriting why a choice was made. A source URL alone is not evidence that every planned operation is permitted. Where terms are ambiguous, keep the capability disabled and record the specific question to resolve.
