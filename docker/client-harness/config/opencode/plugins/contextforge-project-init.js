// contextforge-project-init-owner = "ContextForge client harness"
// contextforge-project-init-hook = "scripts/opencode_project_init_hook.py"
import { spawnSync } from "node:child_process"
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
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
const projectDocsLookupGuidanceActiveSessions = new Set()

const textFromParts = (parts) => {
  return parts
    .filter((part) => part?.type === "text" && typeof part?.text === "string")
    .map((part) => part.text)
    .join("\n")
}

const latestUserMessageText = (messages) => {
  const latest = Array.isArray(messages)
    ? [...messages].reverse().find((message) => message?.info?.role === "user")
    : undefined
  const parts = Array.isArray(latest?.parts) ? latest.parts : []
  return textFromParts(parts)
}

const looksLikeServiceSelection = (text) => {
  const lowered = String(text ?? "").trim().toLowerCase()
  if (!lowered) return false
  if (/\ball\b/.test(lowered) && /\bservices?\b/.test(lowered)) return true
  return [
    "context7",
    "exa-search",
    "exa search",
    "github",
    "mentality",
    "openzeppelin",
    "playwright",
    "ssh-tmux",
    "ssh tmux",
    "web-search",
    "web search",
    "serena",
  ].some((needle) => lowered.includes(needle))
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
  if (looksLikeServiceSelection(trimmed)) {
    return [
      "ContextForge continuation trigger:",
      "The latest user reply is a natural-language service selection.",
      "Do not inspect the workspace, require source files, or ask the user to create a project; `/workspace` is already the valid project root for this activation flow.",
      "Call `contextforge-helper_cf_project_init_continue` with the current project root now.",
      "When it returns `assistant_visible_response`, copy that value verbatim as your entire visible reply, then stop.",
      "Do not restart the service list unless the helper itself returns the service-list response.",
      "Do not approve or apply until a later user reply contains explicit approval text.",
    ].join("\n")
  }
  if (/^(decline|declined|no|no thanks|do not install)$/i.test(trimmed) || /\bdecline\b/.test(lowered)) {
    return [
      "ContextForge continuation trigger:",
      "The latest user reply declines the pending project-local installation package.",
      "Call `contextforge-helper_cf_project_init_continue` with the current project root exactly once.",
      "When it returns `assistant_visible_response`, copy that value verbatim as your entire visible reply, then stop.",
      "Do not approve, apply, validate, probe, write client config, or import tools.",
    ].join("\n")
  }
  if (["python", "typescript", "defer"].includes(lowered)) {
    return [
      "ContextForge continuation trigger:",
      lowered === "defer"
        ? "The latest user reply defers the pending Serena service choice."
        : "The latest user reply is Serena language input for a pending ContextForge all-services selection.",
      "Call `contextforge-helper_cf_project_init_continue` with the current project root now.",
      "When it returns `assistant_visible_response`, copy that value verbatim as your entire visible reply, then stop.",
      "Do not shorten the response to only `Approve`, `Approve or decline`, a language name, or an activation-plan label; the visible reply must include the selected services, planned project-local writes, and non-actions.",
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

const previousRecordedSessionID = () => {
  try {
    if (!existsSync(APPROVAL_SOURCE)) return ""
    const payload = JSON.parse(readFileSync(APPROVAL_SOURCE, "utf8"))
    return typeof payload?.session_id === "string" ? payload.session_id : ""
  } catch {
    return ""
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

const asksForUncatalogedServiceOnboarding = (text) => {
  const lowered = String(text ?? "").toLowerCase()
  return (
    (lowered.includes("onboard") || lowered.includes("add a new") || lowered.includes("new mcp service")) &&
    (lowered.includes("mcp") || lowered.includes("service"))
  )
}

const suppliesSourceOnlyOnboardingDetails = (text) => {
  const lowered = String(text ?? "").toLowerCase()
  return (
    asksForUncatalogedServiceOnboarding(text) ||
    ((lowered.includes("stdio") || lowered.includes("sse") || lowered.includes("http")) &&
      (lowered.includes("project-scoped") || lowered.includes("project scoped") || lowered.includes("scope")) &&
      (lowered.includes("plan") || lowered.includes("no credentials") || lowered.includes("credentials")))
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

const asksHowToUseProjectDocsLookupCapability = (text) => {
  const lowered = String(text ?? "").toLowerCase()
  const namesLookupCapability =
    lowered.includes("project docs lookup capability") ||
    lowered.includes("project documentation lookup capability") ||
    lowered.includes("docs lookup capability") ||
    lowered.includes("contextforge docs lookup guidance") ||
    lowered.includes("project docs lookup guidance")
  if (!namesLookupCapability) return false
  return /\b(how|use|using|workflow|should|guidance|explain)\b/.test(lowered)
}

const projectDocsLookupCapabilityResponse = () =>
  [
    "Use the project docs lookup capability as a two-step workflow:",
    "1. Identify the relevant OpenCode documentation entry when the target is ambiguous.",
    "2. Ask a concrete configuration question against that entry and answer from the docs result.",
    "For config-file questions, name the file, option, or behavior you care about before asking for the lookup.",
  ].join("\n")

const projectDocsLookupCapabilityInstruction = () =>
  [
    "Reply with exactly the following guidance and no other text.",
    "Do not call tools, do not add a preface, and do not mention internal tool, function, route, or server names.",
    projectDocsLookupCapabilityResponse(),
  ].join("\n")

const governanceLedgerForPrompt = (text) => {
  const lowered = String(text ?? "").toLowerCase()
  if (lowered.includes("decision") || lowered.includes("decisions")) return "decisions"
  if (lowered.includes("open question") || lowered.includes("open questions")) return "open-questions"
  if (lowered.includes("abeyant") || lowered.includes("intention") || lowered.includes("intentions")) return "abeyant-intentions"
  return ""
}

const governancePromptRequestsSpecificEntry = (text) => {
  const lowered = String(text ?? "").toLowerCase()
  return (
    lowered.includes("detail") ||
    lowered.includes("details") ||
    lowered.includes("specific") ||
    /\b(task|dec|oq|ai)-[a-z0-9-]+\b/.test(lowered)
  )
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

const helperResponseWithPayload = (cwd, operation, payload) => {
  const helper = process.env.CONTEXTFORGE_PROJECT_INIT_HELPER_CLI ?? "/repo/scripts/pi_project_init_helper_cli.py"
  const result = spawnSync(
    PYTHON,
    [
      helper,
      "--operation",
      operation,
      "--payload-json",
      JSON.stringify({ project_root: String(cwd), client_type: "opencode", ...payload }),
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
const recordReloadIfPending = (cwd) => helperResponseWithPayload(cwd, "record_project_init_client_reload", {})
const serviceOnboardingPlanResponse = (cwd) =>
  helperResponseWithPayload(cwd, "build_service_onboarding_plan", {
    candidateService: "calendar-notes",
    operatorGoal: "Read project notes and expose search over meeting summaries.",
    sourcePath: "./tools/calendar-notes",
    transportType: "stdio",
    localizationType: "project_scoped",
    functionalType: "search_retrieval",
    stateType: "project_metadata",
    approvalType: "source_only",
    credentialRequired: false,
    credentialBoundary: "No credentials yet.",
    expectedTools: ["search meeting summaries"],
    issue: "254",
  })

const serviceOnboardingIntakeResponse = () =>
  [
    "I can help onboard that as an uncataloged MCP service, but this should stay source-only until you approve a concrete runtime step.",
    "Please provide the source reference or local path, transport type, credential boundary, project or user scope, expected tools, lifecycle/cleanup expectations, and what proof plan you want before any install or exposure.",
    "I will not install, register, start, expose, validate, probe, import, or make the service visible to this client during the planning step.",
  ].join("\n")

export const ContextForgeProjectInit = async ({ directory } = {}) => {
  let injected = false

  return {
    "chat.message": async (input, output) => {
      const sessionID = input?.sessionID ?? output?.message?.sessionID ?? `${process.pid}:${Date.now()}`
      const cwd = directory ?? process.cwd()
      const parts = Array.isArray(output?.parts) ? output.parts : []
      const latestText = textFromParts(parts)
      if (!asksHowToUseProjectDocsLookupCapability(latestText)) {
        projectDocsLookupGuidanceActiveSessions.delete(String(sessionID))
        return
      }
      recordLatestUserMessage(sessionID, cwd, latestText)
      projectDocsLookupGuidanceActiveSessions.add(String(sessionID))
      if (Array.isArray(output?.parts)) {
        output.parts.splice(0, output.parts.length, {
          id: `prt_contextforge_project_docs_lookup_capability_instruction_${Date.now()}`,
          sessionID: String(sessionID),
          messageID: String(input?.messageID ?? output?.message?.id ?? `msg_contextforge_project_docs_lookup_capability_${Date.now()}`),
          type: "text",
          text: projectDocsLookupCapabilityInstruction(),
          synthetic: true,
        })
      }
    },
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
      const previousSessionID = previousRecordedSessionID()
      if (previousSessionID && previousSessionID !== String(sessionID)) {
        recordReloadIfPending(cwd)
      }
      recordLatestUserMessage(sessionID, cwd, latestText)
      const governanceLedger = governanceLedgerForPrompt(latestText)
      if (governanceLedger) {
        const wantsSpecificGovernanceEntry = governancePromptRequestsSpecificEntry(latestText)
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
                `Use exactly this list argument shape: {"repo":"${String(cwd)}","ledger":"${governanceLedger}"}.`,
                wantsSpecificGovernanceEntry
                  ? `If the user asked for details of a specific entry, then call the read-only governance read tool exposed by the mentality MCP server for the matching entry id. It may appear as mentality_governance_read, mentality-governance-read, or governance_read. Use exactly this read argument shape: {"repo":"${String(cwd)}","ledger":"${governanceLedger}","id":"ENTRY_ID_FROM_THE_USER_OR_LIST_RESULT"}.`
                  : "If the user only asks for a list or status summary, do not call the governance read tool.",
                "After the tool call returns, produce a visible final answer from the returned entries or entry detail and include entry ids or titles as source signal.",
                "Do not stop with an empty assistant message after a successful governance list or read tool call.",
                "If a read result returns an entry, answer with the entry id, title, status, and the relevant recorded detail.",
                "Do not use glob, grep, bash, project-state file inspection, or ledger-file reads as a substitute for the governance MCP tool.",
                "Do not call governance create, update, or delete.",
                "</contextforge-project-governance>",
              ].join("\n"),
              synthetic: true,
            },
          ],
        })
      }
      const exactCapabilityResponse = asksForProjectCapabilities(latestText) ? capabilitySummaryResponse(cwd) : ""
      const exactServiceOnboardingPlanResponse =
        !exactCapabilityResponse && suppliesSourceOnlyOnboardingDetails(latestText) && !asksForUncatalogedServiceOnboarding(latestText)
          ? serviceOnboardingPlanResponse(cwd)
          : ""
      const exactServiceOnboardingIntakeResponse =
        !exactCapabilityResponse &&
        !exactServiceOnboardingPlanResponse &&
        asksForUncatalogedServiceOnboarding(latestText)
          ? serviceOnboardingIntakeResponse()
          : ""
      const exactStateReadbackResponse = !exactCapabilityResponse && !exactServiceOnboardingPlanResponse && !exactServiceOnboardingIntakeResponse && asksForProjectStateReadback(latestText) ? stateReadbackResponse(cwd) : ""
      const exactAvailabilityResponse = !exactCapabilityResponse && !exactServiceOnboardingPlanResponse && !exactServiceOnboardingIntakeResponse && !exactStateReadbackResponse && asksForContextForgeTools(latestText) ? availabilityResponse(cwd) : ""
      const exactProjectDocsLookupCapabilityResponse =
        !exactCapabilityResponse &&
        !exactStateReadbackResponse &&
        !exactAvailabilityResponse &&
        (projectDocsLookupGuidanceActiveSessions.has(String(sessionID)) || asksHowToUseProjectDocsLookupCapability(latestText))
          ? projectDocsLookupCapabilityResponse()
          : ""
      if (exactServiceOnboardingPlanResponse || exactServiceOnboardingIntakeResponse) {
        const response = exactServiceOnboardingPlanResponse || exactServiceOnboardingIntakeResponse
        output.messages.splice(0, output.messages.length, {
          info: {
            id: `${messageID}_service_onboarding`,
            role: "user",
            sessionID: String(sessionID),
            time: { created: Date.now() },
          },
          parts: [
            {
              id: `prt_contextforge_service_onboarding_${Date.now()}`,
              sessionID: String(sessionID),
              messageID: `${messageID}_service_onboarding`,
              type: "text",
              text: [
                "<contextforge-service-onboarding>",
                "The user is asking to onboard an uncataloged MCP service in an already initialized ContextForge project.",
                "Reply with exactly the following text and no other text. Do not call tools. Do not summarize. Do not restart project init.",
                response,
                "</contextforge-service-onboarding>",
              ].join("\n"),
              synthetic: true,
            },
          ],
        })
        injected = true
        return
      }
      if (exactProjectDocsLookupCapabilityResponse) {
        projectDocsLookupGuidanceActiveSessions.add(String(sessionID))
        const assistantMessageID = `${messageID}_project_docs_lookup_capability_answer`
        const repeatMessageID = `${messageID}_project_docs_lookup_capability_repeat`
        output.messages.splice(
          0,
          output.messages.length,
          {
            info: {
              id: assistantMessageID,
              role: "assistant",
              sessionID: String(sessionID),
              time: { created: Date.now() },
            },
            parts: [
              {
                id: `prt_contextforge_project_docs_lookup_capability_answer_${Date.now()}`,
                sessionID: String(sessionID),
                messageID: assistantMessageID,
                type: "text",
                text: exactProjectDocsLookupCapabilityResponse,
                synthetic: true,
              },
            ],
          },
          {
            info: {
              id: repeatMessageID,
              role: "user",
              sessionID: String(sessionID),
              time: { created: Date.now() },
            },
            parts: [
              {
                id: `prt_contextforge_project_docs_lookup_capability_repeat_${Date.now()}`,
                sessionID: String(sessionID),
                messageID: repeatMessageID,
                type: "text",
                text: "Repeat the previous assistant message exactly, with no added text.",
                synthetic: true,
              },
            ],
          },
        )
        injected = true
        return
      }
      if (exactCapabilityResponse) {
        output.messages.splice(0, output.messages.length, {
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
        })
        injected = true
        return
      }
      if (exactStateReadbackResponse) {
        output.messages.splice(0, output.messages.length, {
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
        })
        injected = true
        return
      }
      if (exactAvailabilityResponse) {
        output.messages.splice(0, output.messages.length, {
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
        })
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
            "`/workspace` is a valid project root even when it is a virgin harness workspace containing no source files.",
            "Use the current OpenCode session transcript to decide whether this is the first project-init turn or a continuation.",
            "If the transcript already shows a service list, proposal, or approval request, continue from the latest user reply instead of restarting service selection.",
            "Do not call the `skill` tool for project init. The hidden project-init context and contextforge-helper tools are the authority for this flow.",
            "Do not narrate helper/tool calls, context checks, skill lookups, helper/tool names, or internal retry strategies in user-visible text. Present only the service menu, installation package or approval request, and final installed/new-session-required message.",
            "For service selection, decline/defer, and approval continuation, call only `contextforge-helper_cf_project_init_continue`. Do not call direct propose, approve, or apply tools in OpenCode.",
            "A numeric service selection such as `1` is never approval. After selecting/proposing services, stop and wait for explicit approval or decline.",
            "When continuation returns `assistant_visible_response`, copy that value verbatim as your entire visible reply before stopping. Do not reduce it to only `Approve`, `Approve or decline`, or an activation-plan label.",
            "On a turn where the latest user reply is only a numeric service selection, do not call any tool with approve or apply in its name. A rejected early approval call is a failed interaction, not progress.",
            "There are no separate OpenCode approval or apply tools. After the latest user reply contains explicit approval text such as `approve`, call `contextforge-helper_cf_project_init_continue` once; it performs helper-owned approval and installation.",
            "After a plain `decline` or `defer` reply, call `contextforge-helper_cf_project_init_continue` once so the helper records the project-local decision and returns the complete visible response.",
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
	                  "For ordinary refresh questions or questions that combine current ContextForge state with tools/capabilities, call only `contextforge-helper_cf_project_state_readback` for this project root. It already includes selected services, configured/imported tool policy, and the client/session boundary. Do not call availability or capability-summary tools afterward.",
	                  "For ordinary user questions asking what ContextForge tools are available, call `contextforge-helper_cf_project_tool_availability` for this project root, then copy its `assistant_visible_response` exactly as the complete visible answer and stop.",
	                  "For ordinary user questions asking what you can do in this project or what capabilities are available, call `contextforge-helper_cf_project_capability_summary` for this project root, then copy its `assistant_visible_response` exactly as the complete visible answer and stop.",
	                  "For ordinary user questions asking what ContextForge state is being used, call `contextforge-helper_cf_project_state_readback` for this project root, then copy its `assistant_visible_response` exactly as the complete visible answer and stop.",
	                  "For questions asking how to use the project docs lookup capability, docs lookup capability, or ContextForge docs lookup guidance, explain the ContextForge two-step workflow: resolve or select the relevant docs/library entry when needed, then ask a concrete docs query through the project-scoped ContextForge docs lookup tool. Do not answer the underlying configuration question yet, and do not use client-native or external documentation routes for this guidance question.",
	                  "For ordinary docs, library, package, API, or configuration lookup questions, use the relevant ContextForge service tool directly. For Context7 documentation requests, call the Context7 resolve-library-id tool first when a library id is needed, then call the Context7 query-docs tool as needed. Do not call contextforge-helper project-init continuation, availability, capability-summary, or state-readback routes before ordinary Context7 tool use.",
	                  "After calling one ordinary readback route, stop. Do not combine multiple readback tool outputs into a new answer.",
	                  "Do not add a preface such as \"I'll check\" and do not paraphrase, bulletize, shorten, or reclassify the availability, capability, or state-readback response.",
	                  "If a readback response contains `client/session boundary`, include that boundary in the visible reply. Never replace it with `available now` language.",
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
