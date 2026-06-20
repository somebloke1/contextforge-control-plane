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
let governancePromptActiveUntil = 0

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

const projectInitContinuationHint = (text) => {
  const trimmed = String(text ?? "").trim()
  const lowered = trimmed.toLowerCase()
  if (/^(?:\d+|[\d,\s]+)$/.test(trimmed)) {
    return [
      "ContextForge continuation trigger:",
      "The latest user reply is a service-selection number.",
      "Do not answer with only the selected service id.",
      "Call `contextforge-helper_cf_project_init_continue` with the current project root now.",
      "When it returns `assistant_visible_response`, copy that value verbatim as your entire visible reply, then stop.",
      "Do not shorten the plan to only `Approve`, `Approve or decline`, or an activation-plan label; the visible reply must include the planned project-local writes and non-actions.",
      "Do not approve or apply until a later user reply contains explicit approval text.",
    ].join("\n")
  }
  if (/^(approve|approved|yes approve|i approve)$/i.test(trimmed) || /\bapprove\b/.test(lowered)) {
    return [
      "ContextForge continuation trigger:",
      "The latest user reply is explicit approval.",
      "Call `contextforge-helper_cf_project_init_continue` with the current project root exactly once.",
      "When it reports installation success, tell the user the selected ContextForge tools are installed and that a new OpenCode session from this project root is required before the tools register, then stop.",
      "Do not call validation, probe, reload-acknowledgement, bash, write, or edit tools.",
    ].join("\n")
  }
  return ""
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

const asksForContextForgeTools = (text) => {
  const lowered = String(text ?? "").toLowerCase()
  return lowered.includes("contextforge") && lowered.includes("tool") && (lowered.includes("available") || lowered.includes("what"))
}

const asksForProjectCapabilities = (text) => {
  const lowered = String(text ?? "").toLowerCase()
  return (
    lowered.includes("what can you do") ||
    (lowered.includes("capabilities") && (lowered.includes("project") || lowered.includes("contextforge")))
  )
}

const asksForProjectStateReadback = (text) => {
  const lowered = String(text ?? "").toLowerCase()
  return (
    lowered.includes("contextforge") &&
    (
      lowered.includes("state are you using") ||
      lowered.includes("state") ||
      lowered.includes("readback") ||
      lowered.includes("current project")
    )
  )
}

const governanceLedgerForPrompt = (text) => {
  const lowered = String(text ?? "").toLowerCase()
  if (lowered.includes("decision") || lowered.includes("decisions")) return "decisions"
  if (lowered.includes("open question") || lowered.includes("open questions")) return "open-questions"
  if (lowered.includes("abeyant") || lowered.includes("intention") || lowered.includes("intentions")) return "abeyant-intentions"
  return ""
}

const helperResponse = (cwd, operation) => {
  const helper = process.env.CONTEXTFORGE_PROJECT_INIT_HELPER_CLI ?? "/repo/scripts/pi_project_init_helper_cli.py"
  const result = spawnSync(
    PYTHON,
    [
      helper,
      "--operation",
      operation,
      "--payload-json",
      JSON.stringify({ project_root: String(cwd), client_type: "opencode" }),
    ],
    {
      encoding: "utf8",
      timeout: 10000,
      stdio: ["pipe", "pipe", "pipe"],
    },
  )
  if (result.status !== 0 || !result.stdout?.trim()) return ""
  try {
    const payload = JSON.parse(result.stdout)
    return String(payload?.assistant_visible_response || payload?.message || "")
  } catch {
    return ""
  }
}

const availabilityResponse = (cwd) => helperResponse(cwd, "get_project_tool_availability")
const capabilitySummaryResponse = (cwd) => helperResponse(cwd, "get_project_capability_summary")
const stateReadbackResponse = (cwd) => helperResponse(cwd, "get_project_state_readback")

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
      if (
        Date.now() < governancePromptActiveUntil &&
        values.some((value) => value === "read" || value === "glob" || value === "grep" || value.includes("context_forge_state.json") || value.includes("decisions.md"))
      ) {
        output.status = "deny"
      }
    },
    [HOOK_EVENT]: async (_input, output) => {
      if (!Array.isArray(output?.messages) || output.messages.length === 0) return

      const latest = output.messages[output.messages.length - 1]
      const sessionID = latest?.info?.sessionID ?? `${process.pid}:${Date.now()}`
      const messageID = `msg_contextforge_project_init_${Date.now()}`
      const cwd = directory ?? process.cwd()
      const latestText = latestUserMessageText(output.messages)
      recordLatestUserMessage(sessionID, cwd, latestText)
      const governanceLedger = governanceLedgerForPrompt(latestText)
      if (governanceLedger) {
        governancePromptActiveUntil = Date.now() + 120000
        output.messages.unshift({
          info: {
            id: `${messageID}_governance`,
            role: "user",
            sessionID: String(sessionID),
            time: { created: Date.now() },
          },
          parts: [
            {
              id: `prt_contextforge_project_governance_${Date.now()}`,
              sessionID: String(sessionID),
              messageID: `${messageID}_governance`,
              type: "text",
              text: [
                "<contextforge-project-governance>",
                "The user is asking an ordinary governance question for an already initialized ContextForge project.",
                "Do not ask which services to activate and do not restart project init.",
                `Call the read-only ContextForge MCP governance list tool exposed by the mentality MCP server. In OpenCode it may appear as mentality_governance_list, mentality-governance-list, or governance_list under the mentality server.`,
                `Use exactly this tool argument shape: {"repo":"${String(cwd)}","ledger":"${governanceLedger}"}.`,
                "After the tool call returns, answer concisely from the returned entries and include entry ids or titles as source signal.",
                "Do not use read, glob, grep, bash, project-state file inspection, or ledger-file reads as a substitute for the governance MCP tool.",
                "Do not call governance create, update, or delete.",
                "</contextforge-project-governance>",
              ].join("\n"),
              synthetic: true,
            },
          ],
        })
      }
      const exactCapabilityResponse = asksForProjectCapabilities(latestText) ? capabilitySummaryResponse(cwd) : ""
      const exactStateReadbackResponse = !exactCapabilityResponse && asksForProjectStateReadback(latestText) ? stateReadbackResponse(cwd) : ""
      const exactAvailabilityResponse = !exactCapabilityResponse && !exactStateReadbackResponse && asksForContextForgeTools(latestText) ? availabilityResponse(cwd) : ""
      if (exactCapabilityResponse) {
        output.messages = [{
          info: {
            id: `${messageID}_capabilities`,
            role: "user",
            sessionID: String(sessionID),
            time: { created: Date.now() },
          },
          parts: [
            {
              id: `prt_contextforge_project_capabilities_${Date.now()}`,
              sessionID: String(sessionID),
              messageID: `${messageID}_capabilities`,
              type: "text",
              text: [
                "<contextforge-project-capabilities>",
                "The user is asking an ordinary project capability question for an already initialized ContextForge project.",
                "Reply with exactly the following line and no other text. Do not call tools. Do not summarize. Do not convert it to bullets. Do not reword class labels.",
                exactCapabilityResponse,
                "</contextforge-project-capabilities>",
              ].join("\n"),
              synthetic: true,
            },
          ],
        }]
        injected = true
        return
      }
      if (exactStateReadbackResponse) {
        output.messages = [{
          info: {
            id: `${messageID}_state_readback`,
            role: "user",
            sessionID: String(sessionID),
            time: { created: Date.now() },
          },
          parts: [
            {
              id: `prt_contextforge_project_state_readback_${Date.now()}`,
              sessionID: String(sessionID),
              messageID: `${messageID}_state_readback`,
              type: "text",
              text: [
                "<contextforge-project-state-readback>",
                "The user is asking an ordinary current-state question for an already initialized ContextForge project.",
                "Reply with exactly the following line and no other text. Do not call tools. Do not summarize.",
                exactStateReadbackResponse,
                "</contextforge-project-state-readback>",
              ].join("\n"),
              synthetic: true,
            },
          ],
        }]
        injected = true
        return
      }
      if (exactAvailabilityResponse) {
        output.messages = [{
          info: {
            id: `${messageID}_availability`,
            role: "user",
            sessionID: String(sessionID),
            time: { created: Date.now() },
          },
          parts: [
            {
              id: `prt_contextforge_project_availability_${Date.now()}`,
              sessionID: String(sessionID),
              messageID: `${messageID}_availability`,
              type: "text",
              text: [
                "<contextforge-project-availability>",
                "The user is asking an ordinary available-tools question for an already initialized ContextForge project.",
                "Reply with exactly the following line and no other text. Do not call tools. Do not summarize.",
                exactAvailabilityResponse,
                "</contextforge-project-availability>",
              ].join("\n"),
              synthetic: true,
            },
          ],
        }]
        injected = true
        return
      }
      const continuationHint = projectInitContinuationHint(latestText)
      if (continuationHint) {
        output.messages.unshift({
          info: {
            id: `${messageID}_continuation`,
            role: "user",
            sessionID: String(sessionID),
            time: { created: Date.now() },
          },
          parts: [
            {
              id: `prt_contextforge_project_init_continuation_${Date.now()}`,
              sessionID: String(sessionID),
              messageID: `${messageID}_continuation`,
              type: "text",
              text: `<contextforge-project-init-continuation>\n${continuationHint}\n</contextforge-project-init-continuation>`,
              synthetic: true,
            },
          ],
        })
      }
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
            "Use the current OpenCode session transcript to decide whether this is the first project-init turn or a continuation.",
            "If the transcript already shows a service list, proposal, or approval request, continue from the latest user reply instead of restarting service selection.",
            "Do not call the `skill` tool for project init. The hidden project-init context and contextforge-helper tools are the authority for this flow.",
            "Do not narrate helper/tool calls, context checks, skill lookups, helper/tool names, or internal retry strategies in user-visible text. Present only the service menu, installation package or approval request, and final installed/new-session-required message.",
            "For service selection and approval continuation, call only `contextforge-helper_cf_project_init_continue`. Do not call direct propose, approve, or apply tools in OpenCode.",
            "A numeric service selection such as `1` is never approval. After selecting/proposing services, stop and wait for explicit approval or decline.",
            "When continuation returns `assistant_visible_response`, copy that value verbatim as your entire visible reply before stopping. Do not reduce it to only `Approve`, `Approve or decline`, or an activation-plan label.",
            "On a turn where the latest user reply is only a numeric service selection, do not call any tool with approve or apply in its name. A rejected early approval call is a failed interaction, not progress.",
            "There are no separate OpenCode approval or apply tools. After the latest user reply contains explicit approval text such as `approve`, call `contextforge-helper_cf_project_init_continue` once; it performs helper-owned approval and installation.",
            "After continuation reports installation succeeded, report that the selected ContextForge tools are installed and that a new session is required before the tools register, then stop.",
            "Do not call any further project-init tools after installation succeeds.",
            "Do not answer, resume, or return to the user's original ordinary prompt after project init reaches the installed/new-session-required boundary.",
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
	                  "For ordinary available-tools questions, do not call list_available_capabilities or cf_project_init_continue. Those are first-run/init-continuation tools.",
	                  "For ordinary user questions asking what ContextForge tools are available, call `contextforge-helper_cf_project_tool_availability` for this project root, then copy its `assistant_visible_response` exactly as the complete visible answer and stop.",
	                  "For ordinary user questions asking what you can do in this project or what capabilities are available, call `contextforge-helper_cf_project_capability_summary` for this project root, then copy its `assistant_visible_response` exactly as the complete visible answer and stop.",
	                  "For ordinary user questions asking what ContextForge state is being used, call `contextforge-helper_cf_project_state_readback` for this project root, then copy its `assistant_visible_response` exactly as the complete visible answer and stop.",
	                  "Do not add a preface such as \"I'll check\" and do not paraphrase, bulletize, shorten, or reclassify the availability, capability, or state-readback response.",
	                  "The availability, capability, and state-readback reports are read-only. Do not propose, approve, apply, repair, validate, probe, onboard services, or mutate project-init state during an ordinary normal-use question.",
                  "If this context says installed, completed_unverified, reload_required, or pending_reload, tell the user the selected ContextForge tools are installed and a new OpenCode session from this project root is required before the tools register, then stop.",
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
