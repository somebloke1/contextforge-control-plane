# Queue Dry-Run Validation

Use `scripts/validate_queue_dry_run.py` when a stacked draft queue needs broad
local validation before merge approval.

The helper creates a disposable detached worktree under `/home/dgk/workspace`,
dry-merges the supplied queue heads in order, normalizes only that disposable
worktree's `.codex/config.toml` paths from the canonical checkout root to the
throwaway root, runs the requested test command, checks diff whitespace, scans
changed files for retired-name literals, and removes the worktree unless
`--keep-worktree` is supplied.

The normalization is intentionally scoped to the disposable worktree. It does
not weaken the canonical project-local `.codex/config.toml` contract, which
continues to pin `/home/dgk/workspace/cf-controlplane` for active Codex helper
commands. During the disposable test run, the helper sets
`CONTEXTFORGE_CONFIG_CONTRACT_ROOT` to the throwaway root so config-contract
tests validate the normalized copy rather than the canonical source file.

Example for the current activation-readiness queue:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/validate_queue_dry_run.py \
  --head de2b0efce0ceb07694260dfbfafe198ccad85c3c \
  --head 53386c7bed55bf728b2fe8e8d2c59e3e85ffcbde \
  --head bc2da26eded357cd27d3dabb16a78178c5d13aef \
  --head 2165347ee6ed85ac1108cc7911817cd95d75a61f \
  --head 405d6f077f553ca2fd2545fb401204c644aa5530 \
  --head 0298ab6804f612fd5df498b334d1cbc399403b41
```

The default test command is full unittest discovery:

```sh
/home/dgk/workspace/cf-controlplane/.venv/bin/python -m unittest discover -s tests -v
```

Pass a custom command after `--test-command` for a focused touched-suite run.
For example:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/validate_queue_dry_run.py \
  --head <head-1> \
  --head <head-2> \
  --test-command /home/dgk/workspace/cf-controlplane/.venv/bin/python -m unittest tests.test_project_init_scripts -v
```

This helper does not merge PRs, mark drafts ready, start Docker, mutate
runtime services, change global client config, execute helper apply/recovery,
provision Serena, rewrite project state, or touch legacy checkouts.
