// contextforge-project-init-owner = "ContextForge client harness"
// contextforge-project-init-hook = "scripts/opencode_project_init_hook.py"
import { spawnSync } from "node:child_process"
import { mkdirSync, writeFileSync } from "node:fs"
import { dirname } from "node:path"

const PYTHON =
  process.env.CONTEXTFORGE_OPENCODE_HOOK_PYTHON ??
  process.env.CONTEXTFORGE_HELPER_PYTHON ??
  "/opt/contextforge-helper-venv/bin/python"
const HOOK = process.env.CONTEXTFORGE_OPENCODE_HOOK ?? "/repo/scripts/opencode_project_init_hook.py"
const HOOK_EVENT = "experimental.chat.messages.transform"
const DENY_RAW_WORKSPACE_MUTATION = (process.env.CONTEXTFORGE_OPENCODE_DENY_RAW_WORKSPACE_MUTATION ?? "1") !== "0"
const APPROVAL_SOURCE =
  process.env.CONTEXTFORGE_OPENCODE_APPROVAL_SOURCE ??
  `${process.env.CONTEXTFORGE_PROJECT_INIT_RUN_ROOT ?? "/home/agent/.local/state/contextforge-client-harness-runtime/project-init"}/opencode-latest-user-message.json`

const latestUserMessageText = (messages) => {
  const latest = Array.isArray(messages)
    ? [...messages].reverse().find((message) => message?.info?.role === "user")
    : undefined
  const parts = Array.isArray(latest?.parts) ? latest.parts : []
  return parts
    .filter((part) => part?.type === "text" && typeof part?.text === "string")
    .map((part) => part.text)
    .join("\n")
}

const recordLatestUserMessage = (sessionID, cwd, text) => {
  try {
    mkdirSync(dirname(APPROVAL_SOURCE), { recursive: true })
    writeFileSync(
      APPROVAL_SOURCE,
      JSON.stringify(
        {
          client_type: "opencode",
          session_id: String(sessionID),
          cwd: String(cwd),
          text: String(text ?? ""),
          recorded_at: new Date().toISOString(),
        },
        null,
        2,
      ) + "\n",
      { mode: 0o600 },
    )
  } catch {
    return
  }
}

export const ContextForgeProjectInit = async ({ directory } = {}) => {
  let injected = false

  return {
    "permission.ask": async (input, output) => {
      if (!DENY_RAW_WORKSPACE_MUTATION) return
      const values = [
        input?.type,
        input?.title,
        input?.metadata?.tool,
        input?.metadata?.name,
        input?.metadata?.command,
      ]
        .filter((value) => typeof value === "string")
        .map((value) => value.toLowerCase())
      if (values.some((value) => value === "bash" || value === "write" || value === "edit")) {
        output.status = "deny"
      }
    },
    [HOOK_EVENT]: async (_input, output) => {
      if (!Array.isArray(output?.messages) || output.messages.length === 0) return

      const latest = output.messages[output.messages.length - 1]
      const sessionID = latest?.info?.sessionID ?? `${process.pid}:${Date.now()}`
      const messageID = `msg_contextforge_project_init_${Date.now()}`
      const cwd = directory ?? process.cwd()
      recordLatestUserMessage(sessionID, cwd, latestUserMessageText(output.messages))
      if (injected) return

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
          const freshInitialization = context.includes("Lifecycle: missing / fresh_initialization")
          const commonTrigger = [
            "Use contextforge-helper project-init tools for activation writes; never use bash, write, or edit to create activation files.",
            "After an approved apply, if the helper says reload or new session is required, report that instruction and stop.",
            "Do not call reload or validation record tools until the user has started or resumed a session and asked to validate or skip.",
          ]
          const trigger = (
            freshInitialization
              ? [
                  "ContextForge first-prompt trigger:",
                  "The current project is not initialized for ContextForge.",
                  "The helper-discovered service choices are included below in this hidden context.",
                  "Before answering the user's ordinary message, ask exactly:",
                  '"Which ContextForge services should I activate for this project?"',
                  "Immediately include the numbered helper-discovered service list from this context.",
                  "Then stop and wait for the user's selection.",
                  "Do not write project state or configuration yet.",
                  ...commonTrigger,
                ]
              : [
                  "ContextForge continuation trigger:",
                  "The current project already has ContextForge project-init state.",
                  "Do not ask which services to activate.",
                  "Do not restart service selection.",
                  "If this context says resume_validation, reload_required, or pending_reload and the user's current message asks to validate or skip, first call cf_project_init_record_client_reload with client_type opencode and validation_mode validate_now or presume_working.",
                  "If the helper then asks for validation and the user's current message asked to validate, continue with the helper validation/readback path.",
                  "If the user's current message asked to skip or presume working, record that helper-visible choice instead of validating.",
                  ...commonTrigger,
                ]
          ).join("\n")
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
