# Investigation: Static port 9108 for Serena per-project instances

**Issue:** [#33](https://github.com/somebloke1/contextforge-control-plane/issues/33)  
**Date:** 2026-06-16  
**Investigator:** Copilot Agent

## Summary

The Serena service has **two distinct modes of operation**, and there is a **critical mismatch between the canonical operator instance and the per-project provisioning system**:

1. **Canonical instance** (operator repo): `server-instances/serena-cf-controlplane-d46fe58a2a20/` uses **hardcoded port 9108** and is a singleton
2. **Per-project instances**: Managed by `scripts/manage_serena_project_instance.py`, which **dynamically reserves ports from 9110-9199** per instance

The issue is that the canonical `run-server.sh` is **not reused** by the per-project provisioning system—each per-project instance gets its own generated `run-server.sh`. However, the canonical script is a potential source of confusion and operational risk.

## Current Architecture

### Per-Project Serena Provisioning (The Active System)

**File:** `scripts/manage_serena_project_instance.py`

This is the authoritative per-project instance manager. Key findings:

#### Port Reservation Strategy

```python
PORT_RANGE = range(9110, 9200)  # Line 43

def reserve_port(preferred: int | None = None) -> int:
    used = used_manifest_ports()
    if preferred is not None and preferred not in used and not socket_port_open(preferred):
        return preferred
    for port in PORT_RANGE:
        if port in used:
            continue
        if socket_port_open(port):
            continue
        return port
    raise RuntimeError("no free Serena port in reserved range 9110-9199")
```

**Assessment:**
- ✅ **Dynamic port allocation** for each per-project instance
- ✅ **Collision detection**: Checks both manifest history and live listening sockets
- ✅ **Deterministic reserve order**: Scans 9110-9199 in sequence
- ✅ **Error handling**: Raises if no ports available (max 90 concurrent instances)

#### Instance Generation

```python
def create(args: argparse.Namespace) -> int:
    # ...
    port = reserve_port()  # Reserve unique port
    instance_dir = REPO_ROOT / "server-instances" / identity.instance_slug
    write_executable(instance_dir / "run-server.sh", run_server_text(identity, port, instance_dir))
    # ...
```

**Pattern:** Each project gets a fresh `run-server.sh` with its reserved port built-in.

#### Systemd Unit Generation

- **Per-instance units**: `contextforge-serena-<slug>.service` (no templating)
- **Generated on-demand** by `service_text(identity, instance_dir)` function
- **Dependency ordering**: Units want `contextforge-gateway.service`

**Location:** `~/.config/systemd/user/contextforge-serena-<slug>.service`

### Canonical Operator Instance (The Outlier)

**Directory:** `server-instances/serena-cf-controlplane-d46fe58a2a20/`

This is a **manually-maintained singleton** for the operator repository:

```bash
# server-instances/serena-cf-controlplane-d46fe58a2a20/run-server.sh
exec serena start-mcp-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 9108 \          # ← HARDCODED
  --context codex \
  --project "/home/dgk/workspace/legacy-controlplane-slices/repo-local-skills-and-governance" \
  --open-web-dashboard false
```

**Status:** 
- ✅ Works for the single operator instance
- ❌ Not parametrized (env vars, CLI args)
- ❌ Not used by the per-project provisioning pipeline
- ⚠️ **Port 9108 is within the per-project range (9110-9199 is intended, but 9108 is adjacent)**

## Risk Analysis

### Scenario 1: Multiple per-project instances (SAFE)

**Current status:** Each per-project instance via `manage_serena_project_instance.py` gets:
- Unique port from 9110-9199
- Unique systemd unit name
- Unique instance directory
- Unique manifest with recorded port

✅ **No collision risk** — per-project provisioning is well-designed.

**Evidence:** Design decisions dec-20260529-0047 and dec-20260529-0048 in DECISIONS.md document concurrent instance creation with unique slugs and dynamic ports.

### Scenario 2: Canonical instance migration to per-project system (RISKY)

If someone tries to **regenerate or move** the canonical `serena-cf-controlplane-d46fe58a2a20` instance through the per-project system:

1. `manage_serena_project_instance.py` would **skip port 9108** (already in use by the running singleton)
2. It would allocate 9110 or higher
3. The operator would then have two running Serena instances: one on 9108 (old), one on 9110+ (new)
4. ContextForge gateway registration would conflict or the old instance would hang orphaned

**Likelihood:** Low, but the gap exists in operational documentation.

### Scenario 3: Port range overflow (RARE)

If more than 90 concurrent per-project Serena instances are provisioned:

```python
raise RuntimeError("no free Serena port in reserved range 9110-9199")
```

✅ Fails fast with clear error.

## Detailed Findings

### Finding 1: Port Range Separation Not Enforced

**Risk:** Canonical instance (9108) and per-project range (9110-9199) are adjacent but not explicitly separated in code.

**Current mitigations:**
- Canonical instance is manually created and rarely touched
- Per-project range starts at 9110 by design
- Collision detection checks live sockets

**Gap:** No code-level enforcement that 9108 should never be auto-allocated to a new instance.

### Finding 2: Run-server.sh Is Instance-Specific

**Current code in `manage_serena_project_instance.py`:**

```python
def run_server_text(identity: Any, port: int, instance_dir: Path) -> str:
    # Generates instance-specific run-server.sh with hardcoded port
```

✅ **Per-project scripts are already parametrized** — each one is generated with its own port.

The canonical `server-instances/serena-cf-controlplane-d46fe58a2a20/run-server.sh` is **separate and manual**, not affected by the per-project generation logic.

### Finding 3: Systemd Units Are Per-Instance, Not Templated

**Current:** `contextforge-serena-<slug>.service` (one file per instance)  
**Not:** `contextforge-serena@.service` (systemd template)

**Trade-offs:**
- ✅ Simpler to reason about (no systemd instance parameter syntax)
- ✅ Works on older systemd versions
- ❌ Slightly more disk I/O (one unit file per instance)

**Assessment:** Acceptable design; templates are an optimization, not a necessity.

### Finding 4: Port Allocation Is Checked But Not Reserved

**Risk:** Between `reserve_port()` returning and the service actually binding, a race condition could occur on a heavily-loaded system.

```python
def reserve_port(preferred: int | None = None) -> int:
    # Checks if port is in manifests and not open in sockets
    # Returns immediately
    # ...

def verify_systemd_service(instance_slug: str) -> None:
    # Service starts ~25 seconds later
    # Port binding happens asynchronously
```

**Current mitigation:** `wait_for_port(port)` (30-second timeout) ensures the port actually opened before proceeding.

**Assessment:** Safe for single-threaded creation. No guarantee against external processes binding the port during the window, but collision with other Serena instances is prevented by the manifest lock.

### Finding 5: Manifest Lock Prevents Concurrent Creation

```python
with LOCK_PATH.open("a+", encoding="utf-8") as lock_handle:
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    # Critical section: reserve_port, write manifest, enable systemd
```

**File:** `run/serena-instance-manager.local.lock`

✅ **Mutual exclusion** prevents two concurrent creations from allocating the same port.

## Recommendations

### Priority 1: Document the Operator Instance Status (IMMEDIATE)

**Action:** Add a note to `server-instances/serena-cf-controlplane-d46fe58a2a20/README.md` clarifying:

1. This is a **singleton manual instance** for the operator repository
2. It is **not regenerated by `manage_serena_project_instance.py`**
3. Its hardcoded port 9108 is **reserved and should not be used** for per-project instances
4. If regenerating this instance, **use the per-project manager** and expect port migration

**File to update:** `server-instances/serena-cf-controlplane-d46fe58a2a20/README.md`

### Priority 2: Update Port Allocation Exclude List (MEDIUM)

**Action:** In `scripts/manage_serena_project_instance.py`, explicitly reserve 9108 as operator-only:

```python
PORT_RANGE = range(9110, 9200)  # ← Already skips 9108
OPERATOR_RESERVED_PORTS = {9108}  # ← Add explicit constant
```

Then document the reasoning in comments.

**Rationale:** Self-documenting code prevents accidental port reuse if PORT_RANGE is changed.

### Priority 3: Add Pre-Flight Operator Port Check (MEDIUM)

**Action:** When creating a per-project instance, check if the operator instance is running on 9108:

```python
def reserve_port(preferred: int | None = None) -> int:
    used = used_manifest_ports()
    # Also check for running canonical instance
    if socket_port_open(9108):
        used.add(9108)
    # ...
```

**Rationale:** Ensures no accidental collisions with the canonical instance if it's not reflected in manifests.

### Priority 4: Add Operational Runbooks (MEDIUM)

**Action:** Create `SERENA_OPERATIONAL_GUIDE.md` covering:

1. **Single canonical instance** (`serena-cf-controlplane-d46fe58a2a20`):
   - How to restart it without affecting per-project instances
   - Manual port override if 9108 becomes unavailable
   
2. **Per-project instances**:
   - How to list all instances and their ports
   - How to verify port allocation is consistent
   - Cleanup if a systemd unit fails to deactivate

3. **Port management**:
   - What happens when 9110-9199 is exhausted
   - How to extend the range or use a different strategy

**Severity:** Medium — informational for operators.

### Priority 5: Verify Current Instance Consistency (ONGOING)

**Action:** Add a verification script that audits:

```python
def audit_serena_instances() -> list[dict[str, Any]]:
    """
    Cross-check:
    1. All serena-*/instance.json files
    2. All systemd units contextforge-serena-*.service
    3. All live listening ports
    4. All project root mappings in manifests
    """
```

**Frequency:** Run during CI/CD or on-demand to detect drift.

## Acceptance Criteria for Issue #33

✅ **Completed by existing code:**
- Per-project instances use dynamic ports (9110-9199)
- Collision detection and manifest tracking are in place
- Port allocation is checked against live sockets and history
- Systemd units are created per-instance with proper dependencies

⚠️ **Needs clarification (this investigation):**
- Canonical instance (9108) is not regenerated by per-project system
- Port ranges are separated but not explicitly guarded
- No cross-check between operator instance and per-project instances during allocation

🔧 **Recommended follow-up work:**
1. Update `server-instances/serena-cf-controlplane-d46fe58a2a20/README.md` with status clarification
2. Add `OPERATOR_RESERVED_PORTS` constant to make exclusions explicit
3. Enhance `reserve_port()` to check running operator instance
4. Create operational runbook for port/instance management
5. Add `audit_serena_instances()` verification script

## Conclusion

The **per-project Serena provisioning system is well-designed** and handles dynamic port allocation safely. The **canonical operator instance is a separate, manually-maintained singleton** that does not interfere with per-project instances.

The issue identified in #33 is **not a functional bug**, but rather an **operational clarity and documentation gap**. The static port 9108 works for the operator instance because:

1. It is instantiated exactly once per operator repository
2. It is not regenerated through the per-project pipeline
3. Its port is outside the per-project allocation range (9110-9199)

**Recommended priority:** Add clarifying documentation and explicit guards in code to prevent future confusion or misuse during maintenance or refactoring.

---

**References:**
- `scripts/manage_serena_project_instance.py` (PORT_RANGE, reserve_port, create)
- `DECISIONS.md` (dec-20260529-0047, dec-20260529-0048)
- `server-instances/serena-cf-controlplane-d46fe58a2a20/` (Canonical instance)
- `server-instances/serena-cf-controlplane-d46fe58a2a20/instance.json` (Port 9108 assignment)
