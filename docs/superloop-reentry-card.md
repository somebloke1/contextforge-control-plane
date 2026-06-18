# SuperLoop Re-entry Card

`scripts/superloop_reentry_card.py` renders a compact, read-only resume card
for resumed operators. The card summarizes:

- local branch/base relationship (`git` ancestry and clean/dirty state),
- active issue / PR / project scope placeholders or explicit IDs,
- evidence authority sources used to build the card,
- a fixed prohibited-surface list aligned to the ContextForge controller
  boundaries,
- the next safe action.

The helper is read-only. It does not call GitHub APIs, mutate Project #6, run
Docker, touch runtime services, update project-init state, or change global
client configuration.

## Usage

```bash
python scripts/superloop_reentry_card.py \
  --issue 191 --issue-title "Add compact SuperLoop re-entry card" --issue-state open \
  --pr 123 --pr-state merged \
  --project-item "#6" --project-state "in_progress" \
  --controller-run-id "codex-thread:..." \
  --worker-agent-id "codex-agent:..."
```

Use `--format json` for machine-readback.
