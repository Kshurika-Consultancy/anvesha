# ADR 0002 Independent code and explicit data rights

Status: accepted, 2026-10-16. Tasks: ANV-001, ANV-005, ANV-011.

Independently written Anvesha code is Apache-2.0. The initial demonstration documents are first-party Apache-2.0 content and clearly labelled. Wikidata's structured entity metadata is the optional CC0-1.0 live source; other Wikimedia text namespaces and Wikipedia articles are not covered by that assumption.

Keep connector manifests under `policies/sources/`. Evaluation/training permission, content retention, and redistribution must be explicit and source-specific. User-imported local documents require operator-reviewed rights; loading them is not a licence grant.

No mandatory paid API or hosted model is allowed. SearXNG integration, general web providers, arbitrary fetching, and new data exports require their own tracked source review. Do not copy AGPL code into the Apache core or assume that an API boundary resolves every copyleft issue. Third-party content keeps its own rights.
