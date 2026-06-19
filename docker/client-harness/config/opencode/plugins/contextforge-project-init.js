// contextforge-project-init-owner = "ContextForge client harness"
// contextforge-project-init-hook = "scripts/opencode_project_init_hook.py"
import { spawnSync } from "node:child_process"

const PYTHON =
  process.env.CONTEXTFORGE_OPENCODE_HOOK_PYTHON ??
  process.env.CONTEXTFORGE_HELPER_PYTHON ??
  "/opt/contextforge-helper-venv/bin/python"
const HOOK = process.env.CONTEXTFORGE_OPENCODE_HOOK ?? "/repo/scripts/opencode_project_init_hook.py"
const HOOK_EVENT = "chat.message"

export const ContextForgeProjectInit = async ({ directory } = {}) => {
  let injected = false

  return {
    [HOOK_EVENT]: async (input, output) => {
      if (injected) return

      const sessionID =
        input?.sessionID ??
        input?.session?.id ??
        input?.message?.sessionID ??
        `${process.pid}:${Date.now()}`
      const cwd = input?.cwd ?? input?.directory ?? directory ?? process.cwd()

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
        const messageID = output?.message?.id ?? output?.parts?.[0]?.messageID
        if (typeof context === "string" && Array.isArray(output?.parts) && messageID) {
          const trigger = [
            "ContextForge first-prompt trigger:",
            "The current project is not initialized for ContextForge.",
            "The helper-discovered service choices are included below in this hidden context.",
            "Before answering the user's ordinary message, ask exactly:",
            '"Which ContextForge services should I activate for this project?"',
            "Immediately include the numbered helper-discovered service list from this context.",
            "Then stop and wait for the user's selection.",
            "Do not write project state or configuration yet.",
          ].join("\n")
          output.parts.unshift({
            id: `prt_contextforge_project_init_${Date.now()}`,
            sessionID: String(sessionID),
            messageID: String(messageID),
            type: "text",
            text: `<contextforge-project-init>\n${trigger}\n\n${context}\n</contextforge-project-init>`,
            synthetic: true,
          })
          injected = true
        }
      } catch {
        return
      }
    },
  }
}
