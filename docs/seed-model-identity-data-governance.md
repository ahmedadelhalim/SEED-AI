# SEED Model Identity Data Governance

## Scope

This document defines the auditable path for future knowledge curation, evaluation, and optional fine-tuning. It does not start training or download data.

## Dataset record requirements

Every retained item must record:

- stable item identifier
- source URI and publisher
- collection timestamp
- language and content type
- license or permission basis
- consent and privacy classification where applicable
- transformation and filtering history
- reviewer and approval status
- retention and deletion policy
- hash of the source and normalized item

## Data classes

1. **Behavior evaluations** — fixed prompts and assertions in `manifests/seed-model-identity/evals.jsonl`.
2. **Knowledge sources** — external or local reference material, retained with provenance and licensing metadata.
3. **Operational history** — SEED task and audit records; never treated as model-training data automatically.
4. **User content** — excluded from training by default; requires explicit policy and authorization.

## Evaluation gates

Before any model identity change is accepted:

- run the fixed English and Arabic behavior set;
- verify default-deny, approval, artifact-integrity, and tool-boundary cases;
- compare against the prior result set;
- record model/provider, prompt version, date, and environment;
- reject regressions in safety, honesty, or governance behavior.

## Future LoRA/fine-tuning plan

No training is currently authorized. If later approved, the workflow is:

1. approve the objective and target base model;
2. assemble only licensed, consented, provenance-complete data;
3. create an immutable dataset manifest and hashes;
4. establish a baseline evaluation;
5. train an isolated LoRA adapter without replacing the base model;
6. evaluate English, Arabic, refusal, uncertainty, and tool-governance behavior;
7. review safety and quality results;
8. register the adapter as a versioned artifact with rollback metadata;
9. deploy only after explicit approval and reproducible validation.
