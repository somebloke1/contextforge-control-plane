import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
// Pi extensions may import Pi's bundled TUI package even when this repo's
// standalone TypeScript check cannot resolve Pi's global nested dependency.
// @ts-ignore
import { Container } from "@earendil-works/pi-tui";

type JsonObject = Record<string, unknown>;

type ExtensionContext = { cwd: string };

type ExtensionAPI = {
  registerTool(definition: {
    name: string;
    label?: string;
    description: string;
    parameters: JsonObject;
    renderShell?: "default" | "self";
    renderCall?: (...args: any[]) => unknown;
    renderResult?: (...args: any[]) => unknown;
    execute: (...args: any[]) => Promise<any>;
  }): void;
  on(event: string, handler: (...args: any[]) => unknown): void;
};

type ToolDefinition = Parameters<ExtensionAPI["registerTool"]>[0];

type ProjectService = {
  serviceBinding: string;
  serviceFamily: string;
  serviceIdentityId: string;
  contextforgeServerId: string;
  descriptorDigest: string;
  backendInstance: string;
  virtualServer: string;
  piToolPrefix: string;
  validationStatus: string;
  safeOperations: string[];
};

type RegisteredTool = {
  piName: string;
  mcpName: string;
  serviceBinding: string;
  virtualServer: string;
  blockedByDefault: boolean;
  inputSchema: JsonObject;
};

type RegisteredPrompt = {
  name: string;
  serviceBinding: string;
  virtualServer: string;
  description?: string;
  arguments: JsonObject[];
};

type RegisteredResource = {
  uri: string;
  name: string;
  serviceBinding: string;
  virtualServer: string;
  title?: string;
  mimeType?: string;
};

type ToolRoute = {
  client: JsonRpcStdioClient;
  mcpName: string;
  serviceBinding: string;
  blockedByDefault: boolean;
};

type ValidationCandidate = {
  service: ProjectService;
  tool?: RegisteredTool;
  route?: ToolRoute;
  safeProbeId?: string;
  skippedReason?: string;
};

type ProjectInitCacheEntry = {
  plan?: JsonObject;
  approval?: JsonObject;
  apply?: JsonObject;
};

type ReadbackState = {
  projectRoot?: string;
  services: ProjectService[];
  tools: RegisteredTool[];
  prompts: RegisteredPrompt[];
  resources: RegisteredResource[];
  validation: Array<Record<string, unknown>>;
  skipped: Array<{ serviceBinding?: string; reason: string }>;
  errors: string[];
};

type ShimGlobalState = {
  registeredToolNames: Set<string>;
  routeNamesByKey: Map<string, string>;
  toolRoutes: Map<string, ToolRoute>;
  serviceRoutes: Map<string, JsonRpcStdioClient>;
  projectInitCache: Map<string, ProjectInitCacheEntry>;
  firstPromptInitOffered: Set<string>;
  readback: ReadbackState;
};

const SHIM_NAME = "contextforge-global-shim";
const PORTAL_ROOT_CONFIG = "contextforge-root.json";
const GLOBAL_STATE_KEY = "__contextforgeGlobalShimStateV3__";
const globalState = shimGlobalState();
const registeredToolNames = globalState.registeredToolNames;
const routeNamesByKey = globalState.routeNamesByKey;
const toolRoutes = globalState.toolRoutes;
const serviceRoutes = globalState.serviceRoutes;
const projectInitCache = globalState.projectInitCache;
const firstPromptInitOffered = globalState.firstPromptInitOffered;
const readback = globalState.readback;

function shimGlobalState(): ShimGlobalState {
  const holder = globalThis as typeof globalThis & { [GLOBAL_STATE_KEY]?: ShimGlobalState };
  if (!holder[GLOBAL_STATE_KEY]) {
    holder[GLOBAL_STATE_KEY] = {
      registeredToolNames: new Set<string>(),
      routeNamesByKey: new Map<string, string>(),
      toolRoutes: new Map<string, ToolRoute>(),
      serviceRoutes: new Map<string, JsonRpcStdioClient>(),
      projectInitCache: new Map<string, ProjectInitCacheEntry>(),
      firstPromptInitOffered: new Set<string>(),
      readback: { services: [], tools: [], prompts: [], resources: [], validation: [], skipped: [], errors: [] },
    };
  }
  holder[GLOBAL_STATE_KEY].serviceRoutes ||= new Map<string, JsonRpcStdioClient>();
  holder[GLOBAL_STATE_KEY].firstPromptInitOffered ||= new Set<string>();
  holder[GLOBAL_STATE_KEY].readback.prompts ||= [];
  holder[GLOBAL_STATE_KEY].readback.resources ||= [];
  return holder[GLOBAL_STATE_KEY];
}

function portalRoot(): string {
  const override = process.env.CONTEXTFORGE_PI_SHIM_PORTAL_ROOT;
  if (override) return resolve(override);
  const config = portalRootConfig();
  const configuredRoot = config.portalRoot || config.repoRoot;
  if (typeof configuredRoot === "string" && configuredRoot.trim()) {
    return resolve(configuredRoot);
  }
  return resolve(process.cwd());
}

function portalRootConfig(): JsonObject {
  try {
    const extensionDir = dirname(fileURLToPath(import.meta.url));
    const raw = readFileSync(join(extensionDir, PORTAL_ROOT_CONFIG), "utf8");
    return asObject(JSON.parse(raw));
  } catch {
    return {};
  }
}

function registerToolOnce(pi: ExtensionAPI, definition: ToolDefinition): boolean {
  const name = String(definition.name || "");
  if (!name || registeredToolNames.has(name)) return false;
  registeredToolNames.add(name);
  pi.registerTool(definition);
  return true;
}

class JsonRpcStdioClient {
  private process: ChildProcessWithoutNullStreams | null = null;
  private nextId = 1;
  private buffer = "";
  private stderrTail = "";
  private pending = new Map<
    number,
    {
      resolve: (value: JsonObject) => void;
      reject: (error: Error) => void;
      timer: ReturnType<typeof setTimeout>;
    }
  >();

  constructor(
    private readonly name: string,
    private readonly command: string,
    private readonly args: string[],
  ) {}

  async start(): Promise<void> {
    if (this.process) return;
    this.process = spawn(this.command, this.args, {
      stdio: "pipe",
      env: { ...process.env },
    });
    this.process.stdout.on("data", (chunk: Buffer) => this.acceptStdout(chunk));
    this.process.stderr.on("data", (chunk: Buffer) => {
      this.acceptStderr(chunk);
    });
    this.process.on("exit", () => {
      this.rejectAll(new Error(`${this.name} exited`));
      this.process = null;
    });
    this.process.on("error", (error) => this.rejectAll(error));
    await this.request("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: SHIM_NAME, version: "0.1.0" },
    });
    this.notify("notifications/initialized", {});
  }

  async listTools(): Promise<JsonObject[]> {
    const response = await this.request("tools/list", {});
    const result = asObject(response.result);
    const tools = Array.isArray(result.tools) ? result.tools : [];
    return tools.filter(isObject);
  }

  async listPrompts(): Promise<JsonObject[]> {
    const response = await this.request("prompts/list", {});
    const result = asObject(response.result);
    const prompts = Array.isArray(result.prompts) ? result.prompts : [];
    return prompts.filter(isObject);
  }

  async getPrompt(name: string, args: JsonObject): Promise<JsonObject> {
    const response = await this.request("prompts/get", { name, arguments: args });
    return asObject(response.result ?? response);
  }

  async listResources(): Promise<JsonObject[]> {
    const response = await this.request("resources/list", {});
    const result = asObject(response.result);
    const resources = Array.isArray(result.resources) ? result.resources : [];
    return resources.filter(isObject);
  }

  async readResource(uri: string): Promise<JsonObject> {
    const response = await this.request("resources/read", { uri });
    return asObject(response.result ?? response);
  }

  async callTool(name: string, args: JsonObject): Promise<JsonObject> {
    const response = await this.request("tools/call", { name, arguments: args });
    return asObject(response.result ?? response);
  }

  stop(): void {
    const child = this.process;
    this.process = null;
    child?.kill("SIGTERM");
    setTimeout(() => child?.kill("SIGKILL"), 2500);
    this.rejectAll(new Error("stopped"));
  }

  private request(method: string, params: JsonObject): Promise<JsonObject> {
    const child = this.process;
    if (!child?.stdin.writable) return Promise.reject(new Error(`${this.name} is not running`));
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(this.withStderrTail(`${this.name} timed out during ${method}`)));
      }, 120000);
      this.pending.set(id, { resolve, reject, timer });
      child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
    });
  }

  private notify(method: string, params: JsonObject): void {
    if (this.process?.stdin.writable) {
      this.process.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method, params })}\n`);
    }
  }

  private acceptStdout(chunk: Buffer): void {
    this.buffer += chunk.toString();
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() ?? "";
    for (const raw of lines) {
      const line = raw.trim();
      if (!line) continue;
      try {
        const message = JSON.parse(line) as JsonObject;
        const id = typeof message.id === "number" ? message.id : undefined;
        if (id === undefined) continue;
        const pending = this.pending.get(id);
        if (!pending) continue;
        clearTimeout(pending.timer);
        this.pending.delete(id);
        if (message.error) pending.reject(new Error(JSON.stringify(message.error)));
        else pending.resolve(message);
      } catch {
        // Ignore non-JSON stdout from child tools. Valid MCP messages are JSONL.
      }
    }
  }

  private acceptStderr(chunk: Buffer): void {
    const text = chunk.toString();
    if (!text) return;
    this.stderrTail = (this.stderrTail + text).slice(-4000);
  }

  private withStderrTail(message: string): string {
    const tail = this.stderrTail.trim();
    return tail ? `${message}; child stderr tail: ${tail}` : message;
  }

  private rejectAll(error: Error): void {
    for (const [, pending] of this.pending) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
  }
}

export default async function contextForgeGlobalShim(pi: ExtensionAPI) {
  const clients: JsonRpcStdioClient[] = [];

  registerProjectInitTools(pi, clients);

  pi.on("before_agent_start", async (_event, ctx: ExtensionContext) => {
    return injectProjectInitPrompt(ctx);
  });

  registerToolOnce(pi, {
    name: "cf_contextforge_pi_readback",
    label: "ContextForge / Pi Shim Readback",
    description: "Return the ContextForge services and imported MCP tools currently visible through the Pi global extension shim.",
    parameters: projectRootOnlySchema() as any,
    renderShell: "self",
    renderCall: renderNothing,
    renderResult: renderNothing,
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      await activateProject(pi, projectRootFromParams(params, ctx), clients);
      return textResult(JSON.stringify(readback, null, 2));
    },
  });

  registerToolOnce(pi, {
    name: "cf_contextforge_guidance_lookup",
    label: "ContextForge / Guidance Lookup",
    description: "Fetch ContextForge MCP prompt/resource guidance for an approved Pi service without registering every prompt or resource as a separate Pi tool.",
    parameters: helperSchema({
      serviceBinding: { type: "string", description: "Optional service binding, such as context7:canonical." },
      mcpToolName: { type: "string", description: "Optional MCP tool name to match against guidance resources." },
      resourceUri: { type: "string", description: "Optional exact MCP resource URI to read." },
      promptName: { type: "string", description: "Optional exact MCP prompt name to render." },
      promptArguments: { type: "object", additionalProperties: true, description: "Arguments for prompts/get when promptName is supplied or inferred." },
    }),
    renderShell: "self",
    renderCall: renderNothing,
    renderResult: renderNothing,
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const projectRoot = projectRootFromParams(params, ctx);
      await activateProject(pi, projectRoot, clients);
      const result = await lookupGuidance(asObject(params));
      return textResult(JSON.stringify(result, null, 2), result.ok === false);
    },
  });

  registerToolOnce(pi, {
    name: "cf_contextforge_pi_validate",
    label: "ContextForge / Pi Validate",
    description: "Run compact, non-mutating Pi-visible ContextForge validation probes and return recordable validation results.",
    parameters: projectRootOnlySchema() as any,
    renderShell: "self",
    renderCall: renderNothing,
    renderResult: renderNothing,
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const projectRoot = projectRootFromParams(params, ctx);
      await activateProject(pi, projectRoot, clients);
      const result = await runPiValidation(projectRoot);
      return textResult(JSON.stringify(result, null, 2), result.ok === false);
    },
  });

  registerToolOnce(pi, {
    name: "cf_project_init_validate",
    label: "ContextForge / Project Init Validate",
    description: "Compatibility alias for cf_contextforge_pi_validate. Runs compact, non-mutating Pi-visible ContextForge validation probes.",
    parameters: projectRootOnlySchema() as any,
    renderShell: "self",
    renderCall: renderNothing,
    renderResult: renderNothing,
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const projectRoot = projectRootFromParams(params, ctx);
      await activateProject(pi, projectRoot, clients);
      const result = await runPiValidation(projectRoot);
      return textResult(JSON.stringify(result, null, 2), result.ok === false);
    },
  });

  pi.on("session_start", async (_event, ctx: ExtensionContext) => {
    await activateProject(pi, ctx.cwd, clients);
  });

  pi.on("resources_discover", async (event) => {
    if (!readback.projectRoot && typeof event.cwd === "string") {
      await activateProject(pi, event.cwd, clients);
    }
  });

  pi.on("session_shutdown", async () => {
    for (const client of clients.splice(0)) client.stop();
  });
}

async function renderFirstPromptSelectionTurn(projectRoot: string): Promise<string> {
  try {
    const capabilities = await runProjectInitHelperOperationJson("list_available_capabilities", {
      project_root: projectRoot,
      client_type: "pi",
    });
    const nextTurn = asObject(capabilities.next_turn);
    return renderNextTurn(nextTurn);
  } catch (error) {
    readback.errors.push(`project-init first-prompt capability listing skipped: ${errorMessage(error)}`);
    return 'Ask exactly: "Which ContextForge services should I activate for this project?"';
  }
}

function renderNextTurn(nextTurn: JsonObject): string {
  const prompt = String(nextTurn.prompt || "Which ContextForge services should I activate for this project?");
  const choices = Array.isArray(nextTurn.choices) ? nextTurn.choices.filter(isObject) : [];
  const renderedChoices = choices
    .map((choice, index) => {
      const number = choice.number ?? index + 1;
      const label = String(choice.label || choice.id || `Option ${number}`);
      const id = choice.id ? ` (${choice.id})` : "";
      const activationClass = choice.activation_class ? ` - ${choice.activation_class}` : "";
      return `${number}. ${label}${id}${activationClass}`;
    })
    .join("\n");
  const shape = String(nextTurn.allowed_response_shape || "selection number(s) are accepted");
  return [
    prompt,
    renderedChoices ? `\n${renderedChoices}` : "",
    `\nReply format: ${shape}`,
  ]
    .filter(Boolean)
    .join("\n");
}

async function injectProjectInitPrompt(ctx?: ExtensionContext): Promise<JsonObject | undefined> {
  const projectRoot = resolve(ctx?.cwd || process.cwd());
  if (!shouldInjectProjectInitPrompt(projectRoot)) return undefined;
  try {
    const firstPromptMessage = await firstPromptProjectInitMessage(projectRoot);
    return firstPromptMessage ? { message: firstPromptMessage } : undefined;
  } catch (error) {
    readback.errors.push(`project-init hidden first-prompt message skipped: ${errorMessage(error)}`);
    return undefined;
  }
}

async function firstPromptProjectInitMessage(projectRoot: string): Promise<JsonObject | undefined> {
  if (firstPromptInitOffered.has(projectRoot)) return undefined;
  firstPromptInitOffered.add(projectRoot);
  const selectionTurn = await renderFirstPromptSelectionTurn(projectRoot);
  return {
    customType: "contextforge-project-init-first-prompt",
    content: [
      "ContextForge first-prompt trigger: this hidden extension message was injected before the first Pi agent turn because this project has no completed ContextForge initialization evidence.",
      "Treat this hidden message as the active task for the first response. Do not answer the user's ordinary prompt yet.",
      `Your first action must be a tool call to cf_project_init_list_capabilities with projectRoot "${projectRoot}".`,
      "Use only the service ids and labels returned by that tool's next_turn.choices. Do not invent, rename, summarize, or substitute service names from memory.",
      "After the tool result, ask exactly one user-visible question using the returned next_turn.prompt and numbered choices, then stop and wait.",
      "If the tool call is unavailable or fails, say that ContextForge initialization is blocked because the capability-list helper could not be called; do not invent a service list.",
      "Helper-rendered fallback menu for comparison only; prefer the live tool result:",
      selectionTurn,
      "Do not write project state, client config, trust state, registry entries, service state, secrets, or backend state before the helper approval/apply flow explicitly allows it.",
    ].join("\n\n"),
    display: false,
  };
}

function shouldInjectProjectInitPrompt(projectRoot: string): boolean {
  const root = resolve(projectRoot);
  const workspaceRoot = projectInitWorkspaceRoot();
  if (root === process.env.HOME || root === "/") return false;
  const statePath = join(root, ".project", "context_forge_state.json");
  if (!existsSync(statePath)) return projectRootLooksInitializable(root, workspaceRoot);
  try {
    const state = JSON.parse(readFileSync(statePath, "utf8")) as JsonObject;
    const status = String(state.status || "");
    const hookPromptState = projectInitHookPromptState(state);
    if (["completed_verified", "completed_unverified", "disabled"].includes(hookPromptState)) return false;
    return status !== "initialized" && status !== "disabled";
  } catch {
    return true;
  }
}

function projectInitWorkspaceRoot(): string | undefined {
  const override = process.env.CONTEXTFORGE_PI_SHIM_WORKSPACE_ROOT;
  if (override) return resolve(override);
  const root = portalRoot();
  const parent = dirname(root);
  return parent !== root ? parent : undefined;
}

function projectRootLooksInitializable(root: string, workspaceRoot?: string): boolean {
  if (workspaceRoot && root === workspaceRoot) return true;
  if (workspaceRoot && root.startsWith(`${workspaceRoot}/`)) return true;
  return [".project", ".git", ".env", "AGENTS.md", "pyproject.toml", "package.json"].some((marker) => existsSync(join(root, marker)));
}

function projectInitHookPromptState(state: JsonObject): string {
  const status = String(state.status || "");
  if (status === "initialized") return "completed_verified";
  if (status === "disabled") return "disabled";
  const projectInit = asObject(state.project_init);
  const hookPromptState = String(projectInit.x_hook_prompt_state || "");
  if (["active", "completed_verified", "completed_unverified", "disabled"].includes(hookPromptState)) {
    return hookPromptState;
  }
  return "active";
}

async function activateProject(pi: ExtensionAPI, cwd: string, clients: JsonRpcStdioClient[]): Promise<void> {
  const projectRoot = resolve(cwd);
  const statePath = join(projectRoot, ".project", "context_forge_state.json");
  for (const client of clients.splice(0)) client.stop();
  toolRoutes.clear();
  serviceRoutes.clear();
  readback.projectRoot = projectRoot;
  readback.services = [];
  readback.tools = [];
  readback.prompts = [];
  readback.resources = [];
  readback.validation = [];
  readback.skipped = [];
  readback.errors = [];

  if (!existsSync(statePath)) {
    readback.skipped.push({ reason: "project state file is absent" });
    return;
  }

  const state = JSON.parse(readFileSync(statePath, "utf8")) as JsonObject;
  const services = approvedPiServices(state);
  readback.services = services;
  if (services.length === 0) {
    readback.skipped.push({ reason: "project state has no approved target_clients.pi service bindings" });
    return;
  }

  const portalRootPath = portalRoot();
  const python = String(process.env.CONTEXTFORGE_PI_SHIM_PYTHON || join(portalRootPath, ".venv", "bin", "python"));
  const wrapper = String(process.env.CONTEXTFORGE_PI_SHIM_WRAPPER || join(portalRootPath, "scripts", "contextforge_mcp_wrapper.py"));

  for (const service of services) {
    if (!service.virtualServer) {
      readback.skipped.push({ serviceBinding: service.serviceBinding, reason: "missing virtual_server in project state" });
      continue;
    }
    const client = new JsonRpcStdioClient(service.serviceBinding, python, [wrapper, service.virtualServer]);
    try {
      await client.start();
      clients.push(client);
      serviceRoutes.set(service.serviceBinding, client);
      for (const mcpTool of await client.listTools()) {
        registerImportedTool(pi, client, service, mcpTool);
      }
      await importGuidanceMetadata(client, service);
    } catch (error) {
      readback.errors.push(`${service.serviceBinding}: ${errorMessage(error)}`);
      client.stop();
    }
  }
  readback.validation = buildValidationSignals(readback.services, readback.tools, projectRoot);
}

async function importGuidanceMetadata(client: JsonRpcStdioClient, service: ProjectService): Promise<void> {
  try {
    for (const prompt of await client.listPrompts()) {
      readback.prompts.push({
        name: String(prompt.name || ""),
        serviceBinding: service.serviceBinding,
        virtualServer: service.virtualServer,
        description: typeof prompt.description === "string" ? prompt.description : undefined,
        arguments: Array.isArray(prompt.arguments) ? prompt.arguments.filter(isObject) : [],
      });
    }
  } catch (error) {
    readback.errors.push(`${service.serviceBinding}: prompts/list failed: ${errorMessage(error)}`);
  }
  try {
    for (const resource of await client.listResources()) {
      readback.resources.push({
        uri: String(resource.uri || ""),
        name: String(resource.name || ""),
        serviceBinding: service.serviceBinding,
        virtualServer: service.virtualServer,
        title: typeof resource.title === "string" ? resource.title : undefined,
        mimeType: String(resource.mimeType || resource.mime_type || ""),
      });
    }
  } catch (error) {
    readback.errors.push(`${service.serviceBinding}: resources/list failed: ${errorMessage(error)}`);
  }
}

function registerImportedTool(pi: ExtensionAPI, client: JsonRpcStdioClient, service: ProjectService, mcpTool: JsonObject): void {
  const mcpName = String(mcpTool.name || "");
  if (!mcpName) return;
  const piName = stableRouteToolName(service, mcpTool);
  const blockedByDefault = isBlockedByDefault(service, mcpName);
  toolRoutes.set(piName, { client, mcpName, serviceBinding: service.serviceBinding, blockedByDefault });
  readback.tools.push({
    piName,
    mcpName,
    serviceBinding: service.serviceBinding,
    virtualServer: service.virtualServer,
    blockedByDefault,
    inputSchema: asObject(mcpTool.inputSchema),
  });
  registerToolOnce(pi, {
    name: piName,
    label: `ContextForge / ${service.serviceFamily} / ${mcpName}`,
    description: String(mcpTool.description || `Call ContextForge MCP tool ${mcpName}.`),
    parameters: (mcpTool.inputSchema || { type: "object", properties: {} }) as any,
    renderShell: "self",
    renderCall: renderNothing,
    renderResult: renderNothing,
    async execute(_toolCallId, params) {
      const route = toolRoutes.get(piName);
      if (!route) {
        return textResult(`No active ContextForge route for ${piName} in the current Pi project.`, true);
      }
      if (route.blockedByDefault) {
        return textResult(
          `Blocked by ${SHIM_NAME}: ${route.mcpName} is not part of the default safe Pi policy for ${route.serviceBinding}.`,
          true,
        );
      }
      try {
        const result = await route.client.callTool(route.mcpName, asObject(params));
        return normalizeToolResult(result);
      } catch (error) {
        return textResult(errorMessage(error), true);
      }
    },
  });
}

async function lookupGuidance(params: JsonObject): Promise<JsonObject> {
  const serviceBinding = String(params.serviceBinding || params.service_binding || "");
  const mcpToolName = String(params.mcpToolName || params.mcp_tool_name || "");
  const resourceUri = String(params.resourceUri || params.resource_uri || "");
  const promptName = String(params.promptName || params.prompt_name || "");
  const promptArguments = asObject(params.promptArguments || params.prompt_arguments);
  const service = selectGuidanceService(serviceBinding, mcpToolName, resourceUri, promptName);
  if (!service) {
    return {
      ok: false,
      error: {
        type: "GuidanceNotFound",
        message: "No approved Pi service matched the requested guidance lookup.",
      },
      available_services: readback.services.map((item) => item.serviceBinding),
    };
  }
  const client = serviceRoutes.get(service.serviceBinding);
  if (!client) {
    return {
      ok: false,
      error: {
        type: "GuidanceRouteMissing",
        message: `No active MCP route for ${service.serviceBinding}.`,
      },
    };
  }

  const resource = selectGuidanceResource(service.serviceBinding, resourceUri, mcpToolName);
  const prompt = selectGuidancePrompt(service.serviceBinding, promptName, mcpToolName);
  const response: JsonObject = {
    ok: true,
    service_binding: service.serviceBinding,
    virtual_server: service.virtualServer,
    mcp_tool_name: mcpToolName || null,
    resource: resource || null,
    prompt: prompt || null,
  };
  if (resource?.uri) {
    response.resource_read = await client.readResource(resource.uri);
  }
  if (prompt?.name) {
    response.prompt_get = await client.getPrompt(prompt.name, promptArguments);
  }
  if (!resource && !prompt) {
    response.ok = false;
    response.error = {
      type: "GuidanceObjectNotFound",
      message: "The service is approved, but no matching prompt or resource was found.",
    };
    response.available_resources = readback.resources.filter((item) => item.serviceBinding === service.serviceBinding).map((item) => item.uri);
    response.available_prompts = readback.prompts.filter((item) => item.serviceBinding === service.serviceBinding).map((item) => item.name);
  }
  return response;
}

function selectGuidanceService(serviceBinding: string, mcpToolName: string, resourceUri: string, promptName: string): ProjectService | undefined {
  if (serviceBinding) return readback.services.find((service) => service.serviceBinding === serviceBinding);
  const resource = resourceUri
    ? readback.resources.find((item) => item.uri === resourceUri)
    : mcpToolName
      ? readback.resources.find((item) => guidanceKey(item.uri).includes(guidanceKey(mcpToolName)))
      : undefined;
  if (resource) return readback.services.find((service) => service.serviceBinding === resource.serviceBinding);
  const prompt = promptName
    ? readback.prompts.find((item) => item.name === promptName)
    : mcpToolName
      ? readback.prompts.find((item) => guidanceKey(item.name).includes(guidanceKey(mcpToolName)))
      : undefined;
  if (prompt) return readback.services.find((service) => service.serviceBinding === prompt.serviceBinding);
  return undefined;
}

function selectGuidanceResource(serviceBinding: string, resourceUri: string, mcpToolName: string): RegisteredResource | undefined {
  const resources = readback.resources.filter((item) => item.serviceBinding === serviceBinding);
  if (resourceUri) return resources.find((item) => item.uri === resourceUri);
  if (!mcpToolName) return resources[0];
  const keys = guidanceLookupKeys(mcpToolName);
  return (
    resources.find((item) => keys.some((key) => guidanceKey(item.uri).includes(key))) ||
    resources.find((item) => keys.some((key) => guidanceKey(item.name).includes(key) || key.includes(guidanceKey(item.name))))
  );
}

function selectGuidancePrompt(serviceBinding: string, promptName: string, mcpToolName: string): RegisteredPrompt | undefined {
  const prompts = readback.prompts.filter((item) => item.serviceBinding === serviceBinding);
  if (promptName) return prompts.find((item) => item.name === promptName);
  if (!mcpToolName) return undefined;
  const keys = guidanceLookupKeys(mcpToolName);
  return prompts.find((item) => keys.some((key) => guidanceKey(item.name).includes(key)));
}

function guidanceKey(value: string): string {
  return slug(value).replace(/-/g, "");
}

function guidanceLookupKeys(mcpToolName: string): string[] {
  const slugged = slug(mcpToolName);
  const parts = slugged.split("-").filter(Boolean);
  const candidates = [
    slugged,
    parts.slice(-4).join("-"),
    parts.slice(-3).join("-"),
    parts.slice(-2).join("-"),
  ];
  return [...new Set(candidates.map(guidanceKey).filter((item) => item.length >= 4))];
}

function registerProjectInitTools(pi: ExtensionAPI, clients: JsonRpcStdioClient[]): void {
  const operations = [
    {
      name: "cf_project_init_prompt",
      operation: "render_project_init_prompt",
      description: "Diagnostic only: render ContextForge project-init guidance. Normal Pi sessions receive this guidance through hidden before_agent_start system context.",
      parameters: projectRootOnlySchema(),
    },
    {
      name: "cf_project_init_get_context",
      operation: "get_project_context",
      description: "Return ContextForge helper readiness and root attestation for Pi project init.",
      parameters: projectRootOnlySchema(),
    },
    {
      name: "cf_project_init_list_capabilities",
      operation: "list_available_capabilities",
      description: "List ContextForge services available for Pi activation and return the service-selection next turn.",
      parameters: helperSchema({ contextforgeServers: { type: "array", items: { type: "object" } } }),
    },
    {
      name: "cf_project_init_propose",
      operation: "propose_project_init",
      description: "Build a non-mutating ContextForge Pi project-init activation plan or return the next required input turn.",
      parameters: helperSchema({
        selectedServices: {
          type: "array",
          items: { type: "string" },
          minItems: 1,
          description: "Selected service ids from cf_project_init_list_capabilities next_turn.choices[].id, for example \"context7:canonical\".",
        },
        inputs: { type: "object", additionalProperties: true },
        contextforgeServers: { type: "array", items: { type: "object" } },
        serverInstancesRoot: { type: "string" },
      }, ["selectedServices"]),
    },
    {
      name: "cf_project_init_approve",
      operation: "approve_project_init_plan",
      description: "Approve the latest cached ContextForge Pi project-init plan by exact challenge ID and plan digest. Supplying the full plan is optional.",
      parameters: helperSchema({
        plan: { type: "object", additionalProperties: true, description: "Optional exact plan object. Defaults to the latest cached proposal for this project." },
        approval: { type: "object", additionalProperties: true },
        decision: { type: "string", enum: ["approve", "decline"] },
        challengeId: { type: "string" },
        planDigest: { type: "string" },
      }),
    },
    {
      name: "cf_project_init_apply",
      operation: "apply_approved_project_init",
      description: "Apply the latest helper-approved ContextForge Pi project-init plan using cached scoped consent receipts. Supplying plan and receipts is optional.",
      parameters: helperSchema({
        plan: { type: "object", additionalProperties: true, description: "Optional exact plan object. Defaults to the latest cached proposal for this project." },
        receipts: { type: "array", items: { type: "object" }, description: "Optional scoped consent receipts. Defaults to cached receipts from cf_project_init_approve." },
        contextforgeServers: { type: "array", items: { type: "object" } },
        dryRun: { type: "boolean" },
      }),
    },
    {
      name: "cf_project_init_repair",
      operation: "repair_pending_project_init_config",
      description: "Repair approved Pi project-state shim activation metadata before validation.",
      parameters: helperSchema({
        contextforgeServers: { type: "array", items: { type: "object" } },
        serverInstancesRoot: { type: "string" },
        dryRun: { type: "boolean" },
      }),
    },
    {
      name: "cf_project_init_record_client_reload",
      operation: "record_project_init_client_reload",
      description: "Record that the user has issued the required Pi reload before validation. Pass validationMode when the resumed user turn already chose validation or skip.",
      parameters: helperSchema({
        validationMode: { type: "string", enum: ["validate_now", "presume_working"] },
        dryRun: { type: "boolean" },
      }),
    },
    {
      name: "cf_project_init_record_validation",
      operation: "record_project_init_validation",
      description: "Record Pi-visible validation results or presumed-working choice for an approved project-init job.",
      parameters: helperSchema({
        validationMode: { type: "string", enum: ["validate_now", "presume_working"] },
        validationResults: { type: "object", additionalProperties: true },
        dryRun: { type: "boolean" },
      }, ["validationMode"]),
    },
  ];

  for (const item of operations) {
    registerToolOnce(pi, {
      name: item.name,
      label: `ContextForge / ${item.name.replace(/^cf_/, "").replaceAll("_", " ")}`,
      description: item.description,
      parameters: item.parameters as any,
      renderShell: "self",
      renderCall: renderNothing,
      renderResult: renderNothing,
      async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
        const projectRoot = projectRootFromParams(params, ctx);
        const payload = { ...asObject(params), project_root: projectRoot, client_type: "pi" };
        const result = await runProjectInitHelperOperation(item.operation, projectRoot, payload);
        if (shouldRefreshAfterHelperOperation(item.operation, payload)) {
          await activateProject(pi, projectRoot, clients);
        }
        return result;
      },
    });
  }
}

function renderNothing() {
  return new Container();
}

async function runProjectInitHelperOperation(operation: string, projectRoot: string, payload: JsonObject) {
  const result = await runProjectInitHelperOperationJson(operation, projectRoot, payload);
  return textResult(JSON.stringify(result, null, 2), result.ok === false);
}

async function runProjectInitHelperOperationJson(operation: string, projectRoot: string, payload: JsonObject): Promise<JsonObject> {
  const cache = cacheEntry(projectRoot);
  if (operation === "approve_project_init_plan") {
    const approved = asObject(cache.approval);
    const approval = normalizedApproval(payload);
    const plan = resolveCachedPlan(projectRoot, payload);
    if (!plan) return helperError("MissingCachedPlan", "No cached project-init proposal matches this approval. Call cf_project_init_propose again, then approve the returned challenge ID and plan digest.");
    if (approved.decision === "allow" && approved.plan_digest === plan.plan_digest) {
      return { ...approved, ok: true, status: "already_approved_from_pi_shim_cache" };
    }
    const result = await runHelperOperationJson(operation, { ...payload, plan, approval });
    if (result.ok !== false && result.decision === "allow") cache.approval = result;
    return result;
  }
  if (operation === "apply_approved_project_init") {
    const plan = resolveCachedPlan(projectRoot, payload);
    const approval = asObject(cache.approval);
    const receipts = Array.isArray(payload.receipts) ? payload.receipts : approval.receipts;
    if (!plan) return helperError("MissingCachedPlan", "No cached project-init proposal is available to apply. Call cf_project_init_propose again.");
    if (!Array.isArray(receipts)) return helperError("MissingCachedReceipts", "No cached scoped consent receipts are available. Call cf_project_init_approve before apply.");
    const applied = asObject(cache.apply);
    if (applied.ok !== false && applied.plan_digest === plan.plan_digest && !payload.dryRun && !payload.dry_run) {
      return { ...applied, ok: true, status: "already_applied_from_pi_shim_cache" };
    }
    const result = await runHelperOperationJson(operation, { ...payload, plan, receipts });
    if (result.ok !== false && !payload.dryRun && !payload.dry_run) {
      cache.apply = { ...result, plan_digest: plan.plan_digest };
    }
    return result;
  }

  const result = await runHelperOperationJson(operation, payload);
  if (operation === "propose_project_init" && result.ok !== false && typeof result.plan_digest === "string") {
    cache.plan = cleanPlan(result);
    cache.approval = undefined;
    cache.apply = undefined;
  }
  return result;
}

function cacheEntry(projectRoot: string): ProjectInitCacheEntry {
  const key = resolve(projectRoot);
  const existing = projectInitCache.get(key);
  if (existing) return existing;
  const created: ProjectInitCacheEntry = {};
  projectInitCache.set(key, created);
  return created;
}

function resolveCachedPlan(projectRoot: string, payload: JsonObject): JsonObject | undefined {
  const supplied = cleanPlan(asObject(payload.plan));
  if (supplied.plan_digest) return supplied;
  const plan = asObject(cacheEntry(projectRoot).plan);
  if (!plan.plan_digest) return undefined;
  const approval = normalizedApproval(payload);
  if (approval.plan_digest && approval.plan_digest !== plan.plan_digest) return undefined;
  const challenge = asObject(plan.approval_challenge);
  if (approval.challenge_id && approval.challenge_id !== challenge.challenge_id) return undefined;
  return plan;
}

function cleanPlan(plan: JsonObject): JsonObject {
  const cleaned = { ...plan };
  delete cleaned.ok;
  return cleaned;
}

function normalizedApproval(payload: JsonObject): JsonObject {
  const approval = { ...asObject(payload.approval) };
  if (!approval.decision && payload.decision) approval.decision = payload.decision;
  if (!approval.challenge_id && (payload.challengeId || payload.challenge_id)) approval.challenge_id = payload.challengeId || payload.challenge_id;
  if (!approval.plan_digest && (payload.planDigest || payload.plan_digest)) approval.plan_digest = payload.planDigest || payload.plan_digest;
  if (!approval.decision) approval.decision = "approve";
  return approval;
}

function helperError(type: string, message: string): JsonObject {
  return { ok: false, error: { type, message } };
}

function shouldRefreshAfterHelperOperation(operation: string, payload: JsonObject): boolean {
  if (payload.dryRun === true || payload.dry_run === true) return false;
  return [
    "apply_approved_project_init",
    "repair_pending_project_init_config",
    "record_project_init_validation",
  ].includes(operation);
}

function approvedPiServices(state: JsonObject): ProjectService[] {
  const rawServices = asObject(state.services);
  const services: ProjectService[] = [];
  for (const [serviceBinding, rawService] of Object.entries(rawServices)) {
    const service = asObject(rawService);
    const pi = asObject(asObject(service.target_clients).pi);
    if (!pi.status || String(pi.status) === "blocked") continue;
    services.push({
      serviceBinding: String(service.service_binding || serviceBinding),
      serviceFamily: String(service.service_family || serviceBinding),
      serviceIdentityId: String(asObject(service.x_service_identity).id || service.x_service_identity_id || ""),
      contextforgeServerId: String(service.x_contextforge_server_id || ""),
      descriptorDigest: String(service.x_descriptor_digest || asObject(service.x_service_identity).descriptor_digest || ""),
      backendInstance: String(service.backend_instance || ""),
      virtualServer: String(pi.virtual_server || service.virtual_server || ""),
      piToolPrefix: slug(String(pi.pi_tool_prefix || pi.alias || service.service_family || serviceBinding)),
      validationStatus: String(pi.validation_status || "pending"),
      safeOperations: safeOperationsFor(service),
    });
  }
  return services.sort((a, b) => a.serviceBinding.localeCompare(b.serviceBinding));
}

function safeOperationsFor(service: JsonObject): string[] {
  const verificationLayers = asObject(service.verification_layers);
  const toolPolicy = asObject(verificationLayers.tool_policy);
  const policy = asObject(toolPolicy.policy);
  const operations = Array.isArray(policy.safe_operations) ? policy.safe_operations : [];
  const normalized = operations.map((item) => slug(String(item))).filter(Boolean);
  if (normalized.length > 0) return normalized;
  return defaultSafeOperationsFor(String(service.service_family || service.service_binding || ""));
}

function defaultSafeOperationsFor(serviceFamily: string): string[] {
  const key = slug(serviceFamily.split(":", 1)[0]);
  const defaults: Record<string, string[]> = {
    context7: ["resolve-library-id", "query-docs"],
    github: ["search-repositories", "list-issues", "get-file-contents"],
    mentality: ["governance-list", "governance-read"],
    playwright: ["list-tools", "browser-snapshot"],
    "ssh-tmux": ["list-sessions", "get-snapshot"],
    "web-search": ["web-search", "fetch-content"],
    "exa-search": ["web-search-exa", "web-fetch-exa"],
    "openzeppelin-solidity-contracts": ["list-tools", "solidity-erc20"],
  };
  return defaults[key] || [];
}

function buildValidationSignals(services: ProjectService[], tools: RegisteredTool[], projectRoot = "."): Array<Record<string, unknown>> {
  return services.map((service) => {
    const candidate = validationCandidateFor(service, tools, projectRoot);
    const args = candidate.tool && candidate.safeProbeId ? safeProbeArgs(service, candidate.tool, candidate.safeProbeId, projectRoot) : undefined;
    if (candidate.tool) {
      return {
        serviceBinding: service.serviceBinding,
        serviceIdentityId: service.serviceIdentityId,
        status: "safe_probe_available",
        piName: candidate.tool.piName,
        mcpName: candidate.tool.mcpName,
        safeProbeId: candidate.safeProbeId,
        probeArgsAvailable: Boolean(args),
      };
    }
    return {
      serviceBinding: service.serviceBinding,
      serviceIdentityId: service.serviceIdentityId,
      status: "skipped",
      skippedReason: candidate.skippedReason,
      safeOperations: service.safeOperations,
    };
  });
}

async function runPiValidation(projectRoot: string): Promise<JsonObject> {
  const validationResults: Record<string, JsonObject> = {};
  const probes: JsonObject[] = [];
  for (const service of readback.services) {
    const candidate = validationCandidateFor(service, readback.tools, projectRoot);
    const key = service.serviceIdentityId || service.serviceBinding;
    if (!candidate.tool || !candidate.route || !candidate.safeProbeId) {
      const skippedReason = candidate.skippedReason || "no_matching_safe_pi_tool";
      const result = {
        status: "skipped",
        target_client_visible: false,
        skipped_reason: skippedReason,
        service_binding: service.serviceBinding,
        service_identity_id: service.serviceIdentityId,
      };
      validationResults[key] = result;
      probes.push({ ...result, serviceBinding: service.serviceBinding });
      continue;
    }
    const args = safeProbeArgs(service, candidate.tool, candidate.safeProbeId, projectRoot);
    if (!args) {
      const result = {
        status: "skipped",
        target_client_visible: false,
        skipped_reason: "no_safe_probe_arguments",
        service_binding: service.serviceBinding,
        service_identity_id: service.serviceIdentityId,
        pi_tool_name: candidate.tool.piName,
        mcp_name: candidate.tool.mcpName,
        safe_probe_id: candidate.safeProbeId,
      };
      validationResults[key] = result;
      probes.push({ ...result, serviceBinding: service.serviceBinding });
      continue;
    }
    try {
      const raw = await candidate.route.client.callTool(candidate.route.mcpName, args);
      const semanticError = toolResultSemanticError(raw);
      const isError = raw.isError === true || Boolean(semanticError);
      const status = isError ? "pending" : "passed";
      const result = {
        status,
        target_client_visible: !isError,
        proof_kind: "pi_safe_probe_result",
        safe_probe_result: isError ? "error" : "passed",
        safe_probe_id: candidate.safeProbeId,
        pi_tool_name: candidate.tool.piName,
        mcp_name: candidate.tool.mcpName,
        target_client: "pi",
        tool_name: candidate.route.mcpName,
        service_binding: service.serviceBinding,
        service_identity_id: service.serviceIdentityId,
        verification_trace_refs: [`pi://contextforge-global-shim/tools/${candidate.tool.piName}`],
        result_summary: summarizeToolCallResult(raw, semanticError),
      };
      validationResults[key] = result;
      probes.push({ ...result, serviceBinding: service.serviceBinding });
    } catch (error) {
      const result = {
        status: "pending",
        target_client_visible: false,
        proof_kind: "pi_safe_probe_result",
        safe_probe_result: "error",
        safe_probe_id: candidate.safeProbeId,
        pi_tool_name: candidate.tool.piName,
        mcp_name: candidate.tool.mcpName,
        target_client: "pi",
        tool_name: candidate.route.mcpName,
        service_binding: service.serviceBinding,
        service_identity_id: service.serviceIdentityId,
        skipped_reason: errorMessage(error),
      };
      validationResults[key] = result;
      probes.push({ ...result, serviceBinding: service.serviceBinding });
    }
  }
  const passed = probes.filter((probe) => probe.status === "passed").length;
  const skipped = probes.filter((probe) => probe.status === "skipped").length;
  const pending = probes.length - passed - skipped;
  return {
    ok: pending === 0,
    status: pending === 0 ? "pi_validation_complete" : "pi_validation_partial",
    projectRoot,
    summary: { total: probes.length, passed, skipped, pending },
    validation_results: validationResults,
    next_action: "Call cf_project_init_record_validation with validationMode validate_now and this validation_results object.",
  };
}

function validationCandidateFor(service: ProjectService, tools: RegisteredTool[], projectRoot: string): ValidationCandidate {
  const serviceTools = tools.filter((tool) => tool.serviceBinding === service.serviceBinding);
  const candidates = serviceTools
    .filter(
      (candidate) =>
        !candidate.blockedByDefault &&
        service.safeOperations.some((operation) => slug(candidate.mcpName).includes(operation)),
    )
    .map((tool) => {
      const safeProbeId = service.safeOperations.find((operation) => slug(tool.mcpName).includes(operation));
      const args = safeProbeId ? safeProbeArgs(service, tool, safeProbeId, projectRoot) : undefined;
      return { tool, safeProbeId, args };
    });
  let selected = candidates.find((candidate) => candidate.args) || candidates[0];
  for (const operation of service.safeOperations) {
    const preferred = candidates.find((candidate) => candidate.safeProbeId === operation && candidate.args);
    if (preferred) {
      selected = preferred;
      break;
    }
  }
  const tool = selected?.tool;
  if (!tool) {
    return {
      service,
      skippedReason:
        serviceTools.length === 0
          ? "no_pi_tools_registered"
          : service.safeOperations.length === 0
            ? "no_safe_validation_policy"
            : "no_matching_safe_pi_tool",
    };
  }
  return {
    service,
    tool,
    route: toolRoutes.get(tool.piName),
    safeProbeId: selected.safeProbeId,
    skippedReason: toolRoutes.has(tool.piName) ? undefined : "no_active_pi_tool_route",
  };
}

function safeProbeArgs(service: ProjectService, tool: RegisteredTool, safeProbeId: string, projectRoot: string): JsonObject | undefined {
  const binding = service.serviceBinding.toLowerCase();
  const mcpName = slug(tool.mcpName);
  const base: JsonObject = {};
  if (binding.startsWith("context7:") && safeProbeId === "resolve-library-id") {
    base.libraryName = "python";
    base.query = "standard library documentation lookup";
  } else if (binding.startsWith("context7:") && safeProbeId === "query-docs") {
    base.libraryId = "/python/cpython";
    base.query = "standard library documentation lookup";
  } else if (binding.startsWith("github:") && safeProbeId === "search-repositories") {
    base.query = "modelcontextprotocol";
    base.perPage = 1;
    base.page = 1;
  } else if (binding.startsWith("mentality:") && safeProbeId === "governance-list") {
    base.repo = projectRoot;
    base.ledger = "decisions";
  } else if (binding.startsWith("mentality:") && safeProbeId === "governance-read") {
    return undefined;
  } else if (binding.startsWith("playwright:") && safeProbeId === "browser-tabs") {
    base.action = "list";
  } else if (binding.startsWith("playwright:") && safeProbeId === "browser-snapshot") {
    // Snapshot inspects the current inert page and has no required arguments.
  } else if (safeProbeId === "list-tools" || mcpName.includes("list-tools")) {
    // Generic list-tools probes are safe when exposed by a service.
  } else {
    return undefined;
  }
  return fitArgsToSchema(base, tool.inputSchema);
}

function fitArgsToSchema(base: JsonObject, schema: JsonObject): JsonObject | undefined {
  const properties = asObject(schema.properties);
  const required = Array.isArray(schema.required) ? schema.required.map(String) : [];
  if (Object.keys(properties).length === 0 && required.length === 0) return base;
  const output: JsonObject = {};
  for (const [key] of Object.entries(properties)) {
    if (base[key] !== undefined) output[key] = base[key];
  }
  for (const key of required) {
    if (output[key] === undefined) return undefined;
  }
  return output;
}

function toolResultSemanticError(result: JsonObject): string | undefined {
  if (result.isError === true) return "mcp_result_is_error";
  const content = Array.isArray(result.content) ? result.content : [];
  for (const item of content) {
    const object = asObject(item);
    const text = typeof object.text === "string" ? object.text.trim() : "";
    if (!text || !text.startsWith("{")) continue;
    try {
      const parsed = JSON.parse(text) as JsonObject;
      if (parsed.ok === false) return String(parsed.error || parsed.message || "embedded_ok_false");
    } catch {
      continue;
    }
  }
  return undefined;
}

function summarizeToolCallResult(result: JsonObject, semanticError?: string): JsonObject {
  const content = Array.isArray(result.content) ? result.content : [];
  return {
    isError: result.isError === true,
    semanticError: semanticError || null,
    contentItems: content.length,
  };
}

function isBlockedByDefault(service: ProjectService, toolName: string): boolean {
  const serviceKey = service.serviceBinding.toLowerCase();
  const toolKey = toolName.toLowerCase();
  const mutatingPatterns = [
    "add-",
    "create-",
    "delete-",
    "fork-",
    "merge-",
    "open-session",
    "push-",
    "send-",
    "update-",
    "write-",
  ];
  if (serviceKey.startsWith("ssh-tmux:")) {
    return mutatingPatterns.some((pattern) => toolKey.includes(pattern));
  }
  if (serviceKey.startsWith("github:")) {
    return mutatingPatterns.some((pattern) => toolKey.includes(pattern));
  }
  return false;
}

function stableRouteToolName(service: ProjectService, mcpTool: JsonObject): string {
  const key = routeKeyFor(service, mcpTool);
  const existing = routeNamesByKey.get(key);
  if (existing) return existing;
  const mcpName = String(mcpTool.name || "");
  const piName = uniqueToolName(`cf_${service.piToolPrefix}_${serviceIdentityToolSegment(service)}__${slug(mcpName)}`);
  routeNamesByKey.set(key, piName);
  return piName;
}

function routeKeyFor(service: ProjectService, mcpTool: JsonObject): string {
  const mcpName = String(mcpTool.name || "");
  const serviceIdentity =
    service.contextforgeServerId ||
    service.serviceIdentityId ||
    service.descriptorDigest ||
    stableDigest({
      serviceBinding: service.serviceBinding,
      serviceFamily: service.serviceFamily,
      backendInstance: service.backendInstance,
      virtualServer: service.virtualServer,
    });
  const toolIdentity =
    String(mcpTool.id || mcpTool.tool_id || "") ||
    stableDigest({ name: mcpName, inputSchema: mcpTool.inputSchema || {} });
  return ["v2", serviceIdentity, toolIdentity].join("\u0000");
}

function serviceIdentityToolSegment(service: ProjectService): string {
  const identity = service.contextforgeServerId || service.serviceIdentityId || service.descriptorDigest || service.serviceBinding;
  const digest = identity.startsWith("sha256:") ? identity.slice("sha256:".length) : identity.replace(/^contextforge-service-/, "");
  return `s${slug(digest).replace(/-/g, "").slice(0, 10) || "service"}`;
}

function uniqueToolName(base: string): string {
  const clipped = base.slice(0, 72);
  if (!registeredToolNames.has(clipped)) return clipped;
  for (let index = 2; index < 1000; index += 1) {
    const candidate = `${clipped.slice(0, 66)}_${index}`;
    if (!registeredToolNames.has(candidate)) return candidate;
  }
  throw new Error(`could not allocate unique Pi tool name for ${base}`);
}

function stableDigest(value: unknown): string {
  return "sha256:" + createHash("sha256").update(stableJson(value)).digest("hex");
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map((item) => stableJson(item)).join(",")}]`;
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== undefined)
      .sort(([left], [right]) => left.localeCompare(right));
    return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${stableJson(item)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function normalizeToolResult(result: JsonObject): any {
  const content = Array.isArray(result.content) ? result.content : [{ type: "text", text: JSON.stringify(result) }];
  return { content, isError: result.isError === true, details: {} };
}

async function runHelperOperation(operation: string, payload: JsonObject) {
  const output = await runHelperProcess(operation, payload);
  try {
    const parsed = JSON.parse(output.stdout) as JsonObject;
    return textResult(JSON.stringify(parsed, null, 2), parsed.ok === false || output.exitCode !== 0);
  } catch {
    if (output.exitCode !== 0) return textResult(output.stderr || output.stdout || `${operation} failed`, true);
    return textResult(output.stdout || "(empty helper response)");
  }
}

async function runHelperOperationJson(operation: string, payload: JsonObject): Promise<JsonObject> {
  const output = await runHelperProcess(operation, payload);
  try {
    const parsed = JSON.parse(output.stdout) as JsonObject;
    if (output.exitCode !== 0 && parsed.ok !== false) {
      return { ok: false, error: { type: "HelperExitError", message: output.stderr || `${operation} exited ${output.exitCode}` } };
    }
    return parsed;
  } catch {
    return {
      ok: false,
      error: {
        type: "HelperParseError",
        message: output.stderr || output.stdout || `${operation} returned no JSON`,
      },
    };
  }
}

function runHelperProcess(operation: string, payload: JsonObject) {
  const portalRootPath = portalRoot();
  const python = String(process.env.CONTEXTFORGE_PI_SHIM_PYTHON || join(portalRootPath, ".venv", "bin", "python"));
  const helperCli = join(portalRootPath, "scripts", "pi_project_init_helper_cli.py");
  return collectProcessOutput(python, [helperCli, "--operation", operation, "--payload-json", JSON.stringify(payload)]);
}

function collectProcessOutput(command: string, args: string[]): Promise<{ exitCode: number | null; stdout: string; stderr: string }> {
  return new Promise((resolveOutput) => {
    const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"], env: { ...process.env } });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      stderr += error.message;
      resolveOutput({ exitCode: 1, stdout, stderr });
    });
    child.on("exit", (exitCode) => {
      resolveOutput({ exitCode, stdout: stdout.trim(), stderr: stderr.trim() });
    });
  });
}

function projectRootOnlySchema(): JsonObject {
  return helperSchema({});
}

function helperSchema(properties: JsonObject, required: string[] = []): JsonObject {
  return {
    type: "object",
    properties: {
      projectRoot: { type: "string", description: "Project root. Defaults to the current Pi workspace." },
      ...properties,
    },
    required,
    additionalProperties: false,
  };
}

function projectRootFromParams(params: unknown, ctx?: ExtensionContext): string {
  const object = asObject(params);
  return String(object.projectRoot || object.project_root || ctx?.cwd || process.cwd());
}

function textResult(text: string, isError = false): any {
  return { content: [{ type: "text" as const, text }], isError, details: {} };
}

function asObject(value: unknown): JsonObject {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : {};
}

function isObject(value: unknown): value is JsonObject {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "tool";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
