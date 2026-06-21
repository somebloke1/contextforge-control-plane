---
name: schematic-abstract-diagrams
description: Create human-readable schematic diagrams for solution elements and relationships. Use when a request needs a graph, Mermaid/ASCII/table hybrid, cardinality labels, ordered relationships, or a review artifact that makes ownership and claim boundaries explicit.
---

# Schematic Abstract Diagrams

Use this skill when terms and relationships co-define each other and the output must explain a system rather than decorate it. It is a fit for project/service graphs, client-projection models, queue or lifecycle orderings, dependency meshes, and review diagrams where hidden claim leaps would be misleading.

## Build The Diagram

1. Name the real entities first.
2. Make relationships first-class labeled edges.
3. Show order explicitly when sequence matters.
4. Mark claim boundaries when one layer must not be read as proof of another.
5. Keep labels short enough to scan in one glance.
6. Add a short caption that says whether the artifact is accepted, selected,
   candidate, or review-only.

When the subject is broad, build a small review pack instead of one dense
diagram:

- one overall queue or lifecycle map;
- one relationship model for the core abstraction;
- one claim-boundary table or checklist.

Use multiple views when that is the only way to keep the result readable.

## Choose The Form

- Mermaid: use when the structure is graph-shaped, the audience needs a shareable diagram, and the labels fit on edges.
- ASCII: use for quick inline review, narrow surfaces, or when Mermaid would hide the reasoning.
- Table: use for cardinalities, comparison matrices, or when the main question is mapping rather than topology.
- Rendered visual: use when the artifact must be inspected visually at higher fidelity, but keep the same labels and claim boundaries.

For Mermaid, treat each fenced code block as independent: define any `classDef`
used by `:::className` inside that same block.

## Label Relationships

Always label edges with what the relation means: `owns`, `contains`, `depends on`, `derives from`, `projects to`, `reads back as`, `gates`, `before`, or `after`. Do not leave edges unlabeled when the meaning is disputed or easy to misread.

Use cardinality and ratio labels when they add meaning:

- `1:1`
- `1:many`
- `1:n`
- `many:many`
- `n:m`
- `1:3`
- bounded constants such as `<=3`

Use ordinal labels for order: `1st`, `2nd`, `then`, `next`, `before`, `after`.

## Avoid Misleading Diagrams

- Do not imply ownership that is not explicit.
- Do not collapse per-client projection into project-global truth.
- Do not use an unlabeled arrow for a contested relationship.
- Do not hide a claim leap behind a generic `relates to`.
- Do not use a diagram when a table is the clearer truth surface.

## Self-Critique

Before shipping, ask:

- does each diagram say what is accepted, selected, candidate, or review-only?
- do the labels explain the relation without relying on surrounding prose?
- does the ordering show queue position, causality, or both?
- did any edge overclaim proof, ownership, or completeness?
- would a reviewer learn the same thing faster from a table?

## Output Check

Before finishing, verify that the diagram answers:

- what exists,
- how it relates,
- what is ordered,
- what is `1:1`, `1:many`, or `many:many`,
- what is only a review claim rather than acceptance.
