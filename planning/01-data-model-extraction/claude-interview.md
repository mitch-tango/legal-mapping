# Interview Transcript — Data Model & Document Extraction

## Q1: Extraction Trigger — How do you envision triggering extraction?
**Answer:** Both approaches — single file path for adding incrementally, folder-based batch for initial deal setup.

## Q2: Data Layout — Where should deal-graph.json live?
**Answer:** One JSON per deal, in a separate data folder (e.g., `/deals/deal-name/deal-graph.json` with documents referenced by path).

## Q3: Re-extraction — How to handle a document that's already been extracted?
**Answer:** Ask me each time — prompt whether to replace or version when a duplicate is detected.

## Q4: PDF Quality — Are documents mostly text-based or scanned?
**Answer:** About 80% text-based PDFs (generated from Word or electronic signing), 20% scanned image PDFs.

## Q5: Deal Scale — How many documents, how long?
**Answer:** Number of docs varies from 5 to ~50. The longest are 100+ pages, but most are 3-30 pages.

## Q6: Implementation Approach — Python scripts vs. Claude Code prompts?
**Answer:** Defers to our recommendation. (We'll recommend hybrid: Python scripts for extraction, Claude Code for orchestration and edge cases.)

## Q7: Relationship Thoroughness — Comprehensive vs. smart matching?
**Answer:** Smart matching — only compare new document against likely related docs based on document type and references. Faster, may miss subtle links but acceptable trade-off.

## Q8: Defined Term Detail — Full text or term + source?
**Answer:** Term + source only — just the term name, defining document, and section reference. Look up full text in the source doc when needed.

## Q9: Text Storage — Store clause text or references only?
**Answer:** References only — store "Section 4.2(b)" and keep the JSON lean. Look up text in source when needed.

## Q10: Confidence Scoring — Simple scale or numeric?
**Answer:** Keep high/medium/low — simple and intuitive for filtering in the UI.

## Q11: Additional Document Types
**Answer:** Add: easement agreements, condominium declarations, lease agreements, license agreements, construction contracts.

## Q12: Additional Relationship Types
**Answer:** Add 8 new types to the taxonomy:
- **amends** — Document A amends Document B
- **assigns** — Document A assigns rights/obligations from Document B
- **guarantees** — Document A guarantees obligations in Document B
- **secures** — Document A provides security/collateral for Document B
- **supersedes** — Document A entirely replaces Document B
- **restricts** — Document A restricts rights or use established in Document B
- **consents_to** — Document A provides consent/approval for an action in Document B
- **indemnifies** — Document A provides indemnification for claims related to Document B
- **restates** — Document A restates Document B (amended and restated)

Full taxonomy is now 15 types (original 7 + 8 new).

## Q13: Extraction Depth — What to extract from each document?
**Answer:** Flag key provisions too — beyond metadata and relationships, also identify and tag critical sections (defaults, termination, closing conditions, reps & warranties).

## Q14: Party Name Normalization
**Answer:** Auto-normalize with uncertain match flagging — AI groups party references across docs using canonical name + aliases, but flags low-confidence matches for review.

## Q15: File I/O for HTML Visualization
**Answer:** Defers to our recommendation. (File System Access API or drag-and-drop are both viable; this is a Split 03 concern.)

## Q16: Top Pain Points
**Answer:** All four pain points are important, but the top two are:
1. **Finding cross-reference chains** — following references across 3-4 documents to understand the full picture
2. **Explaining the deal structure** — communicating to counsel, investors, or partners how all the docs fit together
