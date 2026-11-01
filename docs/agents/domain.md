# Domain Docs

How engineering skills should consume this repo's domain documentation.

## Before exploring

- Read root `GLOSSARY.md`, if it exists.
- Read root `GLOSSARY-MAP.md`, if it exists, and then the glossary files relevant to the topic.
- Read relevant decisions in `docs/adr/`.

If these files do not exist, proceed silently. Do not flag their absence or suggest creating them upfront. Create them when domain terms or decisions are resolved.

## Layout

This is a single-context repo:

- `GLOSSARY.md` — domain vocabulary
- `docs/adr/` — architecture decision records
- `src/` — source code

## Use the glossary vocabulary

Use domain terms as defined in `GLOSSARY.md`. If a concept is missing, reconsider the terminology or note the gap for domain modeling.

## Flag ADR conflicts

If a proposed change contradicts an existing ADR, surface the conflict explicitly rather than silently overriding it.
