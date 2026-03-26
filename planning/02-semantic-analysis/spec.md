# 02 — Semantic Analysis Engine

## Purpose

Build the analytical layer that examines the extracted document graph to answer five core questions about deal document relationships. These are Claude Code workflows that read the graph data, perform analysis, and write results back to the graph.

## Context

See `requirements.md` in the project root for full project context. Key points:

- **Architecture:** Claude Code reads the JSON data file produced by split 01, runs analysis prompts, and writes analysis results back to the same file (or a companion file) that the visualization (split 03) renders.
- **Core pain points:** Document hierarchy (which doc controls what) and cross-reference conflicts (inconsistencies between docs) are the highest-priority analyses.
- **Users:** Solo legal professional at a real estate company reviewing deal documents.
- **Current state:** No systematic approach exists — issues are caught ad hoc today.

## Deliverables

### 1. Document Hierarchy Analysis (HIGH PRIORITY)

Determine which document controls which issues and the subordination chain.

- For a given legal issue (e.g., "capital call procedures", "default remedies", "distribution waterfall"), identify which document is the controlling authority
- Map the hierarchy: controlling doc → documents that defer to it → documents that merely reference it
- Detect provisions where two documents both claim authority on the same issue
- Output: hierarchy tree per issue area, with citations to specific provisions

### 2. Cross-Reference Conflict Detection (HIGH PRIORITY)

Find inconsistencies between documents that create legal risk.

- Identify all cross-references between documents (Doc A §3.2 references Doc B §7.1)
- Validate that referenced sections exist and say what the referencing document claims they say
- Detect contradictions: where Doc A says one thing and Doc B says something different about the same topic
- Flag circular references (A references B which references A)
- Flag dangling references (reference to a section that doesn't exist or was renumbered)
- Output: conflict report with severity (critical/warning/info), affected documents, specific provisions, and description

### 3. Defined Term Tracking

Map the provenance and usage of defined terms across the document set.

- Identify where each term is defined (its "birth" document and section)
- Track where the term is used in other documents
- Detect inconsistencies: same term defined differently in different documents
- Detect orphaned definitions (defined but never used) and undefined usage (used but never defined in the referenced source)
- Output: term map with definition source, usage locations, and inconsistency flags

### 4. Conditions Precedent Chain Mapping

Map the dependency chains for closing conditions.

- Extract conditions precedent from each document
- Build the chain: what must be true/delivered before what
- Identify the critical path (longest chain of dependencies)
- Flag circular conditions (impossible to satisfy)
- Output: ordered list of conditions with dependencies, critical path highlighted

### 5. Execution Sequence Derivation

Derive the closing checklist from the dependency graph.

- Determine the correct order for document execution based on conditions precedent, cross-references, and dependencies
- Group documents that can be executed simultaneously
- Identify signing dependencies (Doc A must be signed before Doc B)
- Output: closing timeline/checklist with execution order and groupings

### Analysis Results Format

Define how analysis results are stored so the visualization (split 03) can render them. This format should:
- Attach to the existing graph data model (defined in split 01)
- Support incremental updates (re-running one analysis without losing others)
- Include metadata: when the analysis was run, what documents were included, confidence levels
- Be renderable as both graph annotations and standalone reports

## Dependencies

- **Depends on 01-data-model-extraction:** Needs the JSON schema and populated graph data. The analysis operates on the extracted data model.
- **Provides to 03-interactive-visualization:** Analysis results in a defined format that the visualization renders (conflict markers, hierarchy overlays, term flow paths, execution sequence).

## Key Design Decisions for /deep-plan

- How to handle analysis of large document sets (20+ docs) within Claude's context window
- Whether analyses are independent (run separately) or build on each other
- How to present confidence levels for analysis results (some findings are certain, others are inferences)
- Granularity of citations — section-level vs. paragraph-level references to source documents
- How to handle re-analysis when the user edits the graph (which analyses need to re-run?)
- Priority ordering: hierarchy and conflict detection first, others follow

## Reference

The prototype at `Reference/Legal Mapping Idea.txt` has a basic "Analyze All" feature that finds cross-document relationships. The semantic analysis here goes much deeper — not just finding relationships but analyzing their implications.
