// contextforge-project-init-owner = "ContextForge client harness"
// contextforge-project-init-hook = "scripts/opencode_project_init_hook.py"
import { spawnSync } from "node:child_process"

const PYTHON = process.env.CONTEXTFORGE_OPENCODE_HOOK_PYTHON ?? "python3"
const HOOK = process.env.CONTEXTFORGE_OPENCODE_HOOK ?? "/repo/scripts/opencode_project_init_hook.py"
const HOOK_EVENT = "experimental.chat.system.transform"

export const ContextForgeProjectInit = async () => {
  let injected = false

  return {
    [HOOK_EVENT]: async (input, output) => {
      if (injected) return

      const sessionID =
        input?.sessionID ??
        input?.session?.id ??
        input?.message?.sessionID ??
        `${process.pid}:${Date.now()}`
      const cwd = input?.cwd ?? input?.directory ?? process.cwd()

      const result = spawnSync(PYTHON, [HOOK], {
        input: JSON.stringify({
          hook_event_name: HOOK_EVENT,
          session_id: String(sessionID),
          cwd: String(cwd),
        }),
        encoding: "utf8",
        timeout: 10000,
        stdio: ["pipe", "pipe", "pipe"],
      })

      if (result.status !== 0 || !result.stdout?.trim()) return

      try {
        const payload = JSON.parse(result.stdout)
        const context = payload?.hookSpecificOutput?.additionalContext
        if (typeof context === "string" && Array.isArray(output?.system)) {
          output.system.push(context)
          injected = true
        }
      } catch {
        return
      }
    },
  }
}
