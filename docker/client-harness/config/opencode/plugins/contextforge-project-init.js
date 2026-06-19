// contextforge-project-init-owner = "ContextForge client harness"
// contextforge-project-init-hook = "scripts/opencode_project_init_hook.py"
import { spawnSync } from "node:child_process"

const PYTHON =
  process.env.CONTEXTFORGE_OPENCODE_HOOK_PYTHON ??
  process.env.CONTEXTFORGE_HELPER_PYTHON ??
  "/opt/contextforge-helper-venv/bin/python"
const HOOK = process.env.CONTEXTFORGE_OPENCODE_HOOK ?? "/repo/scripts/opencode_project_init_hook.py"
const HOOK_EVENT = "experimental.chat.messages.transform"

export const ContextForgeProjectInit = async ({ directory } = {}) => {
  let injected = false

  return {
    [HOOK_EVENT]: async (_input, output) => {
      if (injected) return
      if (!Array.isArray(output?.messages) || output.messages.length === 0) return

      const latest = output.messages[output.messages.length - 1]
      const sessionID = latest?.info?.sessionID ?? `${process.pid}:${Date.now()}`
      const messageID = `msg_contextforge_project_init_${Date.now()}`
      const cwd = directory ?? process.cwd()

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
        if (typeof context === "string") {
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
          output.messages.unshift({
            info: {
              id: messageID,
              role: "user",
              sessionID: String(sessionID),
              time: { created: Date.now() },
            },
            parts: [
              {
                id: `prt_contextforge_project_init_${Date.now()}`,
                sessionID: String(sessionID),
                messageID: String(messageID),
                type: "text",
                text: `<contextforge-project-init>\n${trigger}\n\n${context}\n</contextforge-project-init>`,
                synthetic: true,
              },
            ],
          })
          injected = true
        }
      } catch {
        return
      }
    },
  }
}

export default ContextForgeProjectInit
