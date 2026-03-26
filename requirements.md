# Legal Document Mapping Tool — Requirements

## Vision

A legal document intelligence layer for deal closings. Not just a diagram, but a semantic dependency graph that visualizes how legal documents in a deal interrelate — answering critical questions about document hierarchy, defined term flows, conditions precedent chains, cross-reference conflicts, and execution sequencing.

## Core Questions the System Must Answer

1. **Document Control Hierarchy** — Which document controls a given issue, and which ones defer to it?
2. **Defined Term Provenance** — Where are defined terms born, and where do they travel across documents?
3. **Conditions Precedent Chains** — What must be true in Doc A before Doc B can be triggered?
4. **Cross-Reference Conflicts** — Where do documents conflict or create risk through inconsistent cross-references?
5. **Execution Sequencing** — What's the correct execution sequence for a closing?

## Context

This tool is for use in deal sprints / closings — high-pressure periods where attorneys and deal teams need to rapidly understand the full document landscape and how pieces connect. The primary users are attorneys, paralegals, and deal coordinators at a real estate company (New City Properties).

## Existing Reference

A prototype HTML file exists (`Reference/Legal Mapping Idea.txt`) that demonstrates the concept as a single-page D3.js force-directed graph. Key features of the prototype:

- Deal management (create deals, add documents)
- PDF upload with Claude API extraction of document metadata (parties, defined terms, obligations, summary)
- Relationship type taxonomy: controls, references, subordinates_to, defines_terms_for, triggers, conditions_precedent, incorporates
- D3 force-directed graph visualization with zoom/drag
- Detail panel showing document info, defined terms, obligations, and relationships
- "Analyze All" cross-document relationship discovery
- Confidence scoring on extracted relationships (high/medium/low)
- Edge labels and directional arrows
- LocalStorage persistence

## What's Needed Beyond the Prototype

The prototype is a sketch. The real system needs:

- **Richer semantic analysis** — Not just pairwise relationships, but multi-hop dependency chains and conflict detection
- **Defined term tracking** — Follow a term from its defining document through all documents that use it, flagging inconsistencies
- **Conditions precedent visualization** — Show the chain/sequence, not just pairwise links
- **Execution timeline** — A closing checklist view derived from the dependency graph
- **Conflict/risk detection** — Automated flagging of inconsistent cross-references, conflicting defined terms, or circular dependencies
- **Better UX for deal teams** — The prototype is developer-oriented; needs to be usable by attorneys and paralegals
- **Persistence and collaboration** — Multiple users working on the same deal

## Open Questions / Build vs. Buy

The approach is open. Options include:

1. **Custom-built web application** — Extending the prototype concept into a full application
2. **Existing graph/visualization platforms** — Heptabase, Miro, or similar tools that support nodes, edges, and some programmability
3. **Legal AI software** — Existing legal tech that may already solve parts of this (e.g., document analysis, deal management)
4. **Hybrid approach** — Using existing services for visualization/collaboration while building custom AI extraction layer

Key considerations:
- Must handle real PDF documents and extract meaningful relationships
- Visualization must be interactive and dynamic (not static diagrams)
- Need semantic understanding of legal document relationships (not just keyword matching)
- Should support the specific relationship taxonomy relevant to deal closings
- Team collaboration is important
- Data sensitivity — these are confidential legal documents

## Document Types Commonly Encountered

- Joint Venture Agreements
- Operating Agreements
- Construction/Permanent Loan Agreements
- Guaranties (Completion, Payment, etc.)
- Environmental Indemnities
- Purchase and Sale Agreements
- Ground Leases
- Promissory Notes
- Deeds of Trust
- Intercreditor Agreements
- Subordination Agreements
- Management Agreements
- Development Agreements
- Title Insurance Policies
- Organizational documents (LLC agreements, etc.)
