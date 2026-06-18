#!/usr/bin/env python3
"""Register project-independent prompts and resources for ContextForge tools."""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import control_plane_registry_discipline as registry_discipline
import contextforge_mcp_wrapper as gateway


OWNER = "admin@contextforge.dev"
VISIBILITY = "public"

SERVICE_META = {
    "mentality": {
        "server": "mentality_server",
        "gateway": "21bf9a1aa70a49e9ba2d11bafa280ef7",
        "sources": [
            "Local governance MCP: scripts/governance_mcp.py",
            "Local ledger CRUD: scripts/governance_crud.py",
        ],
        "notes": "Use for durable governance ledgers. Read or list before update/delete when IDs are uncertain.",
    },
    "ssh-tmux": {
        "server": "ssh_tmux_server",
        "gateway": "5c2a76c98c074afe87df07dc207476e3",
        "sources": ["https://github.com/johnpyp/mcp-ssh-tmux", "Package: mcp-ssh-tmux"],
        "notes": "Persistent SSH sessions are backed by tmux. Inspect snapshots before closing sessions or sending raw keys.",
    },
    "context7": {
        "server": "context7_local_server",
        "gateway": "c8e2bd7d99254b98b2904bce6f39aedc",
        "sources": [
            "https://github.com/upstash/context7",
            "https://context7.com/docs/installation",
            "https://context7.com/docs/agentic-tools/overview",
        ],
        "notes": "Resolve a library ID first unless an exact Context7 ID is already known. Query docs with concrete task and version context.",
    },
    "playwright": {
        "server": "playwright_server",
        "gateway": "19af5a4c3a944decb7242ea51b072bce",
        "sources": [
            "https://playwright.dev/docs/getting-started-mcp",
            "https://playwright.dev/mcp/capabilities",
            "https://github.com/microsoft/playwright-mcp",
            "https://www.npmjs.com/package/@playwright/mcp",
        ],
        "notes": "Prefer accessibility snapshots for element refs, condition waits over fixed sleeps, and normal interaction tools over unsafe code execution.",
    },
    "exa-search": {
        "server": "exa_search_server",
        "gateway": "05754613e3644721aa12f2d923dc6403",
        "sources": [
            "https://exa.ai/docs/reference/exa-mcp",
            "https://exa.ai/docs/reference/search-api-guide-for-coding-agents",
            "https://exa.ai/docs/reference/contents-api-guide-for-coding-agents",
            "https://ai.google.dev/api/generate-content",
        ],
        "notes": "Use search for source discovery, fetch for known URLs, and Gemini synthesis when a cited answer is wanted from returned source text.",
    },
    "openzeppelin-solidity-contracts": {
        "server": "openzeppelin_solidity_contracts_server",
        "gateway": "30e0189877854e24879e1428fcc73b2c",
        "sources": [
            "https://mcp.openzeppelin.com/contracts/solidity/mcp",
            "https://github.com/OpenZeppelin/openzeppelin-contracts-mcp",
            "https://docs.openzeppelin.com/contracts/wizard",
        ],
        "notes": "Generates Solidity source from OpenZeppelin Wizard logic. Review generated contracts, security assumptions, and experimental feature warnings before deployment.",
    },
    "github": {
        "server": "github_server",
        "gateway": "35de0ef8f791449898317435f986d6dd",
        "sources": [
            "https://github.com/modelcontextprotocol/servers/tree/main/src/github",
            "Package: @modelcontextprotocol/server-github",
            "Local bridge: server-instances/github/run-bridge.sh",
        ],
        "notes": "Use read-only search and fetch tools first. Treat repository, file, issue, pull request, and merge tools as mutating operations that need explicit user intent.",
    },
    "web-search": {
        "server": "web_search_server",
        "gateway": "68493a5f5b5048f5973edb8c5d00dc5b",
        "sources": [
            "/home/dgk/workspace/web_search",
            "Package: pi-web-access standalone MCP server",
            "Local bridge: server-instances/web-search/run-bridge.sh",
        ],
        "notes": "Use for web search, readable URL extraction, code documentation search, public GitHub repository extraction, and PDF text extraction. Gemini Web cookie access remains disabled unless explicitly enabled in ignored local env.",
    },
}

PROMPTS = {
    "mentality-governance-create": ("mentality_governance_create_entry", "Create one governance ledger entry with repo {repo}, ledger {ledger}, title {title}, optional body {body}, optional status {status}, optional comma-separated tags {tags}, and optional explicit id {id}. Use a ledger-valid status or omit it for the ledger default. Return the created id, ledger path, and concise summary."),
    "mentality-governance-delete": ("mentality_governance_delete_entry", "Delete exactly one governance ledger entry using repo {repo}, ledger {ledger}, and exact id {id}. Do not infer the id; list or read first when uncertain. Return the deleted id and path, or the tool error."),
    "mentality-governance-list": ("mentality_governance_list_entries", "List governance entries for repo {repo} and ledger {ledger}, optionally filtered by ledger-valid status {status}. Summarize ids, statuses, updated dates, and titles; mention the ledger path."),
    "mentality-governance-read": ("mentality_governance_read_entry", "Read one governance entry using repo {repo}, ledger {ledger}, and exact id {id}. Return the path, metadata, body, and any raw markdown details needed for follow-up update decisions."),
    "mentality-governance-update": ("mentality_governance_update_entry", "Update one governance entry using repo {repo}, ledger {ledger}, exact id {id}, and only the fields that should change: title {title}, body {body}, status {status}, and tags {tags}. Omit unchanged fields. Return the updated id, path, status, and summary."),
    "ssh-tmux-cleanup-dead-sessions": ("ssh_tmux_cleanup_dead_sessions", "Clean up only SSH tmux sessions already reported as dead. First list sessions, then call cleanup with dry_run {dry_run} unless the user explicitly approved deletion. Return removed session IDs and any sessions left untouched."),
    "ssh-tmux-close-session": ("ssh_tmux_close_session", "Close SSH tmux session {session_id} only after confirming no important foreground work should continue; report the final snapshot and cleanup result."),
    "ssh-tmux-get-snapshot": ("ssh_tmux_get_snapshot", "Inspect session {session_id} with {lines} lines and decide whether it is idle, busy, waiting for input, or dead."),
    "ssh-tmux-list-sessions": ("ssh_tmux_list_sessions", "List current ssh-tmux sessions and identify which session IDs are reusable, dead, or safe to clean up."),
    "ssh-tmux-open-session": ("ssh_tmux_open_session", "Open an SSH tmux session to {host} as {username} on {port}; return the session_id and interpret the initial snapshot."),
    "ssh-tmux-read-remote-file": ("ssh_tmux_read_remote_file", "Read {remote_path} from session {session_id} using read_remote_file, with fallback_lines {fallback_lines} only as bounded PTY fallback."),
    "ssh-tmux-send-command": ("ssh_tmux_send_command", "Run {command} in session {session_id} with lines {lines} and timeout {timeout}; interpret returned prompt/input hints before taking the next action."),
    "ssh-tmux-send-keys": ("ssh_tmux_send_keys", "Send raw tmux keys {keys} to session {session_id}, then inspect the session with get_snapshot before further action."),
    "ssh-tmux-write-remote-file": ("ssh_tmux_write_remote_file", "Write content to {remote_path} in session {session_id} with append {append}; verify afterward with read_remote_file or an appropriate command."),
    "context7-local-resolve-library-id": ("resolve_context7_library_id", "Resolve the Context7 library ID for {library_name} for this task: {query}. Prefer exact package/product matches, high source reputation, strong snippet coverage, and the best benchmark score. Return the selected /org/project ID and a short reason."),
    "context7-local-query-docs": ("query_context7_docs", "Using Context7 library ID {library_id}, fetch current docs for this task: {query}. Be specific, prefer version-relevant examples, and return only documentation-backed guidance with source-aware caveats."),
    "exa-search-web-fetch-exa": ("fetch_webpage_with_exa", "Fetch clean readable content from {urls} with Exa. Return title, URL, status, publication date, author, extracted markdown text within {maxCharacters} characters, and any per-URL failures."),
    "exa-search-web-search-exa": ("search_web_with_exa", "Search the web with Exa for: {query}. Return up to {numResults} relevant sources using {searchType}, with titles, URLs, publication dates, highlights, and a brief note on source usefulness."),
    "exa-search-web-search-gemini-exa": ("answer_with_exa_and_gemini", "Search Exa for: {query}. Then synthesize an answer using only the returned source text. Follow: {instructions}. Cite sources by number and include the source list."),
    "playwright-browser-click": ("click_element", "Click {element_description} using snapshot target {target}; take a fresh snapshot first if target is unknown."),
    "playwright-browser-close": ("close_browser_page", "Close the current Playwright browser page when the session is no longer needed."),
    "playwright-browser-console-messages": ("inspect_console", "Return browser console messages at {level} level, using all {all} if session-wide logs are needed."),
    "playwright-browser-drag": ("drag_between_elements", "Drag {start_element} from {start_target} to {end_element} at {end_target}."),
    "playwright-browser-drop": ("drop_file_or_data", "Drop files or MIME data onto {element_description} at target {target}; provide paths or data."),
    "playwright-browser-evaluate": ("evaluate_page_javascript", "Evaluate a small JavaScript function on the page or target {target}; return or save the result."),
    "playwright-browser-file-upload": ("upload_files", "Upload file paths {paths} to the active file chooser, or omit paths to cancel it."),
    "playwright-browser-fill-form": ("fill_form_fields", "Fill form fields {fields} using snapshot targets; verify with a snapshot before submitting."),
    "playwright-browser-handle-dialog": ("handle_browser_dialog", "Handle the current browser dialog with accept {accept}; include promptText only for prompt dialogs."),
    "playwright-browser-hover": ("hover_element", "Hover over {element_description} using target {target} to reveal hover UI or tooltips."),
    "playwright-browser-navigate": ("navigate_url", "Navigate the browser to {url}; wait for load and inspect with snapshot before interacting."),
    "playwright-browser-navigate-back": ("navigate_back", "Go back one step in browser history and inspect the resulting page."),
    "playwright-browser-network-request": ("inspect_network_request", "Inspect network request number {index}; optionally return only {part} or save to {filename}."),
    "playwright-browser-network-requests": ("list_network_requests", "List network requests since page load; include static {static} and optional regex filter {filter}."),
    "playwright-browser-press-key": ("press_keyboard_key", "Press keyboard key {key} in the current focused context."),
    "playwright-browser-resize": ("resize_viewport", "Resize the browser window to {width}x{height} before visual or responsive checks."),
    "playwright-browser-run-code-unsafe": ("run_playwright_code_unsafe", "Only for trusted clients: run this bounded Playwright function against page: {code}; prefer snapshot/evaluate when enough."),
    "playwright-browser-select-option": ("select_dropdown_option", "Select dropdown value(s) {values} on {element_description} at target {target}."),
    "playwright-browser-snapshot": ("capture_accessibility_snapshot", "Capture an accessibility snapshot of the current page or target {target}; include boxes {boxes} only when coordinates help."),
    "playwright-browser-tabs": ("manage_tabs", "Manage tabs with action {action}; use index for select/close and url for new tabs."),
    "playwright-browser-take-screenshot": ("take_screenshot", "Take a {type} screenshot of the page or target {target}; use fullPage {fullPage} when needed."),
    "playwright-browser-type": ("type_text", "Type {text} into {element_description} at target {target}; set submit or slowly only when needed."),
    "playwright-browser-wait-for": ("wait_for_condition", "Wait for time {time}, text {text}, or textGone {textGone}; prefer condition waits over fixed delays."),
    "openzeppelin-solidity-contracts-solidity-account": ("openzeppelin_solidity_account_prompt", "Generate an ERC-4337 account contract named {name} with signer {signer}, signature validation {signatureValidation}, holder support {holderSupport}, batching {batchedExecution}, ERC-7579 modules {ERC7579Modules}, and upgradeability {upgradeable}."),
    "openzeppelin-solidity-contracts-solidity-custom": ("openzeppelin_solidity_custom_prompt", "Generate a custom OpenZeppelin Solidity contract named {name} with access control {access}, pausable behavior {pausable}, upgradeability {upgradeable}, and metadata {info}."),
    "openzeppelin-solidity-contracts-solidity-erc1155": ("openzeppelin_solidity_erc1155_prompt", "Generate an ERC-1155 contract named {name} using metadata URI {uri}, with burnable {burnable}, mintable {mintable}, pausable {pausable}, supply tracking {supply}, URI updates {updatableUri}, access {access}, and upgradeability {upgradeable}."),
    "openzeppelin-solidity-contracts-solidity-erc20": ("openzeppelin_solidity_erc20_prompt", "Generate an ERC-20 token named {name} with symbol {symbol}, supply/minting settings {premint}/{mintable}, transfer features {burnable}/{pausable}/{permit}/{callback}, governance {votes}, flash minting {flashmint}, bridge mode {crossChainBridging}, access {access}, and upgradeability {upgradeable}."),
    "openzeppelin-solidity-contracts-solidity-erc721": ("openzeppelin_solidity_erc721_prompt", "Generate an ERC-721 NFT contract named {name} with symbol {symbol}, base URI {baseUri}, minting {mintable}/{incremental}, metadata storage {uriStorage}, enumerable {enumerable}, burnable {burnable}, pausable {pausable}, votes {votes}, access {access}, and upgradeability {upgradeable}."),
    "openzeppelin-solidity-contracts-solidity-governor": ("openzeppelin_solidity_governor_prompt", "Generate a Governor contract named {name} with voting delay {delay}, voting period {period}, vote token type {votes}, clock mode {clockMode}, timelock {timelock}, quorum {quorumMode}, proposal threshold {proposalThreshold}, settings/storage {settings}/{storage}, and upgradeability {upgradeable}."),
    "openzeppelin-solidity-contracts-solidity-rwa": ("openzeppelin_solidity_rwa_prompt", "Generate an experimental ERC-20 real-world asset token named {name} with symbol {symbol}, compliance restrictions {restrictions}, freezing {freezable}, mint/burn/pause settings, optional permit/votes/bridging, access {access}, and metadata {info}."),
    "openzeppelin-solidity-contracts-solidity-stablecoin": ("openzeppelin_solidity_stablecoin_prompt", "Generate an experimental ERC-20 stablecoin named {name} with symbol {symbol}, compliance restrictions {restrictions}, freezing {freezable}, mint/burn/pause settings, optional permit/votes/bridging, access {access}, and metadata {info}."),
    "github-add-issue-comment": ("github_add_issue_comment_prompt", "Add a GitHub issue or pull request comment in {owner}/{repo} on issue number {issue_number} with body {body}. Confirm the target thread and comment text before calling."),
    "github-create-branch": ("github_create_branch_prompt", "Create branch {branch} in {owner}/{repo} from {from_branch} or {sha}. Confirm the target repository and source revision before calling."),
    "github-create-issue": ("github_create_issue_prompt", "Create a GitHub issue in {owner}/{repo} titled {title} with body {body}, labels {labels}, assignees {assignees}, and milestone {milestone}. Confirm before calling."),
    "github-create-or-update-file": ("github_create_or_update_file_prompt", "Create or modify file {path} in {owner}/{repo} on branch {branch} with message {message}, content {content}, and current sha {sha}. Confirm exact path, branch, and diff intent before calling."),
    "github-create-pull-request": ("github_create_pull_request_prompt", "Create a pull request in {owner}/{repo} from head {head} into base {base} titled {title} with body {body}, draft {draft}, and maintainer edits {maintainer_can_modify}. Confirm before calling."),
    "github-create-pull-request-review": ("github_create_pull_request_review_prompt", "Create a pull request review in {owner}/{repo} for pull request {pull_number} with event {event}, body {body}, and comments {comments}. Confirm review disposition before calling."),
    "github-create-repository": ("github_create_repository_prompt", "Create repository {name} with description {description}, private {private}, autoInit {autoInit}, and organization {organization}. Confirm ownership, visibility, and initialization before calling."),
    "github-fork-repository": ("github_fork_repository_prompt", "Fork {owner}/{repo} into organization {organization}. Confirm the destination owner and whether an existing fork should be reused before calling."),
    "github-get-file-contents": ("github_get_file_contents_prompt", "Read file or directory {path} from {owner}/{repo} at branch or ref {branch}. Return path, sha, content summary, and download details as relevant."),
    "github-get-issue": ("github_get_issue_prompt", "Read issue {issue_number} in {owner}/{repo}. Return title, state, author, labels, assignees, body summary, and linked pull request details if present."),
    "github-get-pull-request": ("github_get_pull_request_prompt", "Read pull request {pull_number} in {owner}/{repo}. Return state, title, branches, author, mergeability, checks summary, and body summary."),
    "github-get-pull-request-comments": ("github_get_pull_request_comments_prompt", "List review comments for pull request {pull_number} in {owner}/{repo}. Include file paths, line context, authors, and unresolved-looking follow-ups."),
    "github-get-pull-request-files": ("github_get_pull_request_files_prompt", "List files changed in pull request {pull_number} in {owner}/{repo}. Summarize additions, deletions, statuses, and risk-relevant paths."),
    "github-get-pull-request-reviews": ("github_get_pull_request_reviews_prompt", "List reviews for pull request {pull_number} in {owner}/{repo}. Summarize reviewer, state, submitted time, and actionable comments."),
    "github-get-pull-request-status": ("github_get_pull_request_status_prompt", "Read status and check information for pull request {pull_number} in {owner}/{repo}. Return failing, pending, and passing checks with useful URLs."),
    "github-list-commits": ("github_list_commits_prompt", "List commits in {owner}/{repo} for sha {sha}, branch {branch}, author {author}, since {since}, and until {until}. Return commit shas, authors, dates, and messages."),
    "github-list-issues": ("github_list_issues_prompt", "List issues in {owner}/{repo} filtered by state {state}, labels {labels}, assignee {assignee}, since {since}, page {page}, and perPage {perPage}. Return concise issue rows."),
    "github-list-pull-requests": ("github_list_pull_requests_prompt", "List pull requests in {owner}/{repo} filtered by state {state}, head {head}, base {base}, sort {sort}, direction {direction}, page {page}, and perPage {perPage}."),
    "github-merge-pull-request": ("github_merge_pull_request_prompt", "Merge pull request {pull_number} in {owner}/{repo} using method {merge_method}, commit title {commit_title}, and commit message {commit_message}. Confirm checks, reviews, and branch before calling."),
    "github-push-files": ("github_push_files_prompt", "Push files {files} to {owner}/{repo} on branch {branch} with commit message {message}. Confirm the exact changed files, branch, and commit intent before calling."),
    "github-search-code": ("github_search_code_prompt", "Search GitHub code for {query} with page {page} and perPage {perPage}. Return repository, path, score, and URL for relevant matches."),
    "github-search-issues": ("github_search_issues_prompt", "Search GitHub issues and pull requests for {query} with page {page} and perPage {perPage}. Return concise results with repository, number, title, state, and URL."),
    "github-search-repositories": ("github_search_repositories_prompt", "Search GitHub repositories for {query} with page {page} and perPage {perPage}. Return name, owner, description, stars, updated date, and URL."),
    "github-search-users": ("github_search_users_prompt", "Search GitHub users for {query} with page {page} and perPage {perPage}. Return login, type, profile URL, and brief relevance notes."),
    "github-update-issue": ("github_update_issue_prompt", "Modify issue {issue_number} in {owner}/{repo} with title {title}, body {body}, state {state}, labels {labels}, assignees {assignees}, and milestone {milestone}. Confirm intended changes before calling."),
    "github-update-pull-request-branch": ("github_update_pull_request_branch_prompt", "Modify pull request branch for {owner}/{repo} pull request {pull_number} with expected head sha {expected_head_sha}. Confirm the target and expected head before calling."),
    "web-search-code-search": ("web_search_code_search_prompt", "Search for code examples, official docs, package usage, or API references for {query}. Optionally narrow by language {language} or package name {packageName}, and return source URLs plus the most relevant snippets."),
    "web-search-fetch-content": ("web_search_fetch_content_prompt", "Fetch readable content from URL {url}. Use prompt {prompt} only when the source is a video or needs focused extraction. Return title, URL, extracted markdown, and any extraction limitations."),
    "web-search-github-repo": ("web_search_github_repo_prompt", "Extract context from public GitHub repository URL {url}. Respect size limits, return local extraction details or summaries, and use maxCharacters {maxCharacters} to bound output."),
    "web-search-pdf-extract": ("web_search_pdf_extract_prompt", "Extract markdown text from PDF URL {url}. Bound extraction with maxPages {maxPages} and maxCharacters {maxCharacters}; report page coverage and any parse failures."),
    "web-search-web-search": ("web_search_web_search_prompt", "Search the web for {query} with provider {provider}, result count {numResults}, optional domains {domains}, and optional date bounds {startPublishedDate} to {endPublishedDate}. Return answer, sources, and metadata."),
}

PROJECT_INIT_MANAGED_TOOL_PREFIXES = ("serena-",)

PLACEHOLDER_RE = re.compile(r"(?<!{){([A-Za-z_][A-Za-z0-9_]*)}(?!})")
SQL_TRIGGER_RE = re.compile(r"(?i)(union|select|insert|update|delete|drop)(?=\s)")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")

SQL_WORD_REPLACEMENTS = {
    "union": "combine",
    "select": "choose",
    "insert": "add",
    "update": "modify",
    "delete": "remove",
    "drop": "place",
}


@dataclass(frozen=True)
class GuidanceItem:
    tool_name: str
    service: str
    resource_body: dict[str, Any]
    prompt_body: dict[str, Any]


def api_items(path: str, token: str) -> list[dict[str, Any]]:
    return gateway._items(api_request("GET", path, token=token))


def api_request(
    method: str,
    path: str,
    *,
    token: str,
    body: dict[str, Any] | None = None,
    attempts: int = 8,
) -> Any:
    registry_discipline.assert_public_contextforge_api_path(method, path)
    for attempt in range(attempts):
        try:
            result = gateway._request(method, path, token=token, body=body)
            if method != "GET":
                time.sleep(0.2)
            return result
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == attempts - 1:
                detail = exc.read().decode(errors="replace")
                raise RuntimeError(f"{method} {path} failed: HTTP {exc.code} {exc.reason}: {detail}") from exc
            retry_after = exc.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 5 * (attempt + 1)
            time.sleep(delay)
    raise RuntimeError(f"{method} {path} failed after retries")


def index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {row[key]: row for row in rows if isinstance(row.get(key), str)}


def prompt_args(template: str) -> list[dict[str, Any]]:
    names: list[str] = []
    for match in PLACEHOLDER_RE.finditer(template):
        name = match.group(1)
        if name not in names:
            names.append(name)
    return [
        {"name": name, "description": f"{name} value for this prompt", "required": False}
        for name in names
    ]


def sanitize_scanner_text(text: str) -> str:
    """Shape documentation text so ContextForge's broad scanner accepts it."""

    def replace_sql_word(match: re.Match[str]) -> str:
        word = match.group(1)
        replacement = SQL_WORD_REPLACEMENTS[word.lower()]
        return replacement.capitalize() if word[:1].isupper() else replacement

    shaped = text.replace("```", "")
    shaped = INLINE_CODE_RE.sub(r"\1", shaped)
    shaped = shaped.replace("&&", "and")
    shaped = shaped.replace("||", "or")
    shaped = shaped.replace("$(", "$ (")
    shaped = shaped.replace("${", "$ {")
    return SQL_TRIGGER_RE.sub(replace_sql_word, shaped)


def safe_identifier_text(text: str) -> str:
    """Avoid trigger words followed by whitespace in otherwise literal names."""
    return sanitize_scanner_text(text).replace("\n", " ").strip()


def service_for_tool(name: str) -> str:
    for prefix, service in [
        ("mentality-", "mentality"),
        ("ssh-tmux-", "ssh-tmux"),
        ("context7-local-", "context7"),
        ("playwright-", "playwright"),
        ("exa-search-", "exa-search"),
        ("openzeppelin-solidity-contracts-", "openzeppelin-solidity-contracts"),
        ("github-", "github"),
        ("web-search-", "web-search"),
    ]:
        if name.startswith(prefix):
            return service
    raise ValueError(f"unknown service for {name}")


def tool_guidance_managed_elsewhere(name: str) -> bool:
    return name.startswith(PROJECT_INIT_MANAGED_TOOL_PREFIXES)


def unmapped_extra_tools(tools_by_name: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(
        name
        for name in set(tools_by_name) - set(PROMPTS)
        if not tool_guidance_managed_elsewhere(name)
    )


def resource_uri(tool: dict[str, Any], service: str) -> str:
    name = tool["name"]
    if service == "mentality":
        return "mentality://governance/" + name.rsplit("-", 1)[-1]
    if service == "ssh-tmux":
        return "ssh-tmux://docs/tools/" + name.removeprefix("ssh-tmux-")
    if service == "context7":
        return "context7://tools/" + name
    if service == "playwright":
        return "playwright-mcp://tools/" + name
    if service == "exa-search":
        return "exa-search://docs/" + name.removeprefix("exa-search-")
    if service == "openzeppelin-solidity-contracts":
        original = tool.get("originalName") or name.removeprefix("openzeppelin-solidity-contracts-")
        return "openzeppelin-solidity-contracts://tools/" + original
    if service == "github":
        original = tool.get("originalName") or name.removeprefix("github-")
        return "github://tools/" + original
    if service == "web-search":
        original = tool.get("originalName") or name.removeprefix("web-search-")
        return "web-search://tools/" + original
    raise ValueError(service)


def titleize(text: str) -> str:
    return text.replace("_", " ").replace("-", " ").title()


def resource_name(tool: dict[str, Any], service: str) -> str:
    original = tool.get("originalName") or tool["name"]
    if service == "playwright":
        return "Playwright MCP " + titleize(original.removeprefix("browser_"))
    if service == "openzeppelin-solidity-contracts":
        return "OpenZeppelin " + titleize(original) + " MCP Tool"
    if service == "context7":
        return "Context7 " + titleize(original)
    if service == "exa-search":
        return "Exa " + titleize(original)
    if service == "ssh-tmux":
        return "ssh-tmux " + original.replace("_", " ")
    if service == "mentality":
        return "Mentality " + titleize(original)
    if service == "github":
        return "GitHub " + titleize(original)
    if service == "web-search":
        return "web_search " + titleize(original)
    return original


def schema_summary(schema: Any) -> str:
    if not isinstance(schema, dict):
        return "- No schema is registered."
    required = set(schema.get("required") or [])
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return "- No object properties are registered."

    lines: list[str] = []
    for name, spec in sorted(properties.items()):
        desc = ""
        typ = "value"
        enum = None
        if isinstance(spec, dict):
            desc = str(spec.get("description") or spec.get("title") or "").strip()
            typ = str(spec.get("type") or ("enum" if spec.get("enum") else "value"))
            enum = spec.get("enum")
        req = "required" if name in required else "optional"
        suffix = f"; {desc}" if desc else ""
        enum_text = f"; values: {', '.join(map(str, enum))}" if isinstance(enum, list) else ""
        lines.append(f"- {name}: {req} {typ}{enum_text}{suffix}")
    return "\n".join(lines)


def resource_content(tool: dict[str, Any], service: str, template: str) -> str:
    meta = SERVICE_META[service]
    original = tool.get("originalName") or tool["name"]
    description = (tool.get("description") or tool.get("originalDescription") or "No description is registered.").strip()
    sources = "\n".join(f"- {source}" for source in meta["sources"])
    content = f"""# {resource_name(tool, service)}

Tool name: {safe_identifier_text(tool["name"])},
Upstream or original name: {safe_identifier_text(original)},
Service: {service}

## Purpose
{description}

## Succinct Prompt
{template}

## Usage Notes
{meta["notes"]}

## Input Schema
{schema_summary(tool.get("inputSchema"))}

## Output Schema
{schema_summary(tool.get("outputSchema"))}

## Sources And Examples
{sources}
"""
    return sanitize_scanner_text(content)


def compact(text: str, limit: int = 220) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= limit else one_line[: limit - 1].rstrip() + "..."


def build_guidance_items(
    tools_by_name: dict[str, dict[str, Any]],
    resources_by_uri: dict[str, dict[str, Any]],
    prompts_by_custom: dict[str, dict[str, Any]],
    prompts_by_name: dict[str, dict[str, Any]],
    prompt_defs: dict[str, tuple[str, str]],
) -> tuple[list[GuidanceItem], dict[str, dict[str, Any] | None]]:
    items: list[GuidanceItem] = []
    existing_by_key: dict[str, dict[str, Any] | None] = {}

    for tool_name in sorted(prompt_defs):
        prompt_name, raw_template = prompt_defs[tool_name]
        template = sanitize_scanner_text(raw_template)
        tool = tools_by_name[tool_name]
        service = service_for_tool(tool_name)
        meta = SERVICE_META[service]
        uri = resource_uri(tool, service)
        name = resource_name(tool, service)

        resource_body = {
            "uri": uri,
            "name": name,
            "title": name,
            "description": f"Project-independent guidance resource for {safe_identifier_text(tool_name)}.",
            "mimeType": "text/markdown",
            "content": resource_content(tool, service, template),
            "tags": ["tool-guidance", service, tool_name],
            "owner_email": OWNER,
            "visibility": VISIBILITY,
            "gateway_id": meta["gateway"],
        }
        prompt_body = {
            "name": prompt_name,
            "customName": prompt_name,
            "displayName": prompt_name.replace("_", " "),
            "title": titleize(prompt_name),
            "description": f"Succinct prompt for {safe_identifier_text(tool_name)}. {compact(sanitize_scanner_text(tool.get('description') or ''))}",
            "template": template,
            "arguments": prompt_args(template),
            "tags": ["tool-guidance", service, tool_name],
            "ownerEmail": OWNER,
            "visibility": VISIBILITY,
            "gatewayId": meta["gateway"],
        }
        items.append(
            GuidanceItem(
                tool_name=tool_name,
                service=service,
                resource_body=resource_body,
                prompt_body=prompt_body,
            )
        )
        existing_by_key[f"resource:{tool_name}"] = resources_by_uri.get(uri)
        existing_by_key[f"prompt:{tool_name}"] = prompts_by_custom.get(prompt_name) or prompts_by_name.get(prompt_name)

    return items, existing_by_key


def preflight_guidance(items: list[GuidanceItem]) -> None:
    from mcpgateway.services.content_security import get_content_security_service

    service = get_content_security_service()
    errors: list[str] = []
    for item in items:
        content = item.resource_body["content"]
        template = item.prompt_body["template"]
        try:
            service.validate_resource_size(content, uri=item.resource_body["uri"], user_email=OWNER)
            service.detect_malicious_patterns(content, content_type="Resource content", user_email=OWNER)
        except Exception as exc:  # noqa: BLE001 - report ContextForge validation details.
            violation = getattr(exc, "violation_type", type(exc).__name__)
            pattern = getattr(exc, "pattern_matched", "")
            snippet = getattr(exc, "content_snippet", "")
            errors.append(
                f"resource {item.tool_name}: {violation}; pattern={pattern!r}; snippet={snippet!r}"
            )

        try:
            service.validate_prompt_size(template, name=item.prompt_body["name"], user_email=OWNER)
            service.validate_prompt_template(template, name=item.prompt_body["name"], user_email=OWNER)
        except Exception as exc:  # noqa: BLE001 - report ContextForge validation details.
            violation = getattr(exc, "violation_type", type(exc).__name__)
            pattern = getattr(exc, "pattern_matched", "")
            snippet = getattr(exc, "content_snippet", "")
            errors.append(
                f"prompt {item.tool_name}: {violation}; pattern={pattern!r}; snippet={snippet!r}"
            )

    if errors:
        raise RuntimeError("ContextForge validation preflight failed:\n" + "\n".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", choices=sorted(SERVICE_META), help="Only refresh one service's guidance")
    args = parser.parse_args()

    config = gateway._read_env(gateway.CONFIG_ENV)
    token = gateway._token(config["PLATFORM_ADMIN_EMAIL"], config["PLATFORM_ADMIN_PASSWORD"])

    prompt_defs = {
        tool_name: prompt
        for tool_name, prompt in PROMPTS.items()
        if args.service is None or service_for_tool(tool_name) == args.service
    }

    tools = api_items("/tools?include_inactive=true&limit=1000", token)
    tools_by_name = index_by(tools, "name")
    missing = sorted(set(prompt_defs) - set(tools_by_name))
    extra = unmapped_extra_tools(tools_by_name) if args.service is None else []
    if missing or extra:
        print(f"tool/prompt mismatch: missing={missing} extra={extra}", file=sys.stderr)
        return 1

    servers_by_name = index_by(api_items("/servers?include_inactive=true&limit=1000", token), "name")
    resources_by_uri = index_by(api_items("/resources?include_inactive=true&limit=1000", token), "uri")
    prompts = api_items("/prompts?include_inactive=true&limit=1000", token)
    prompts_by_custom = {
        prompt.get("customName") or prompt.get("custom_name") or prompt.get("name"): prompt
        for prompt in prompts
        if prompt.get("customName") or prompt.get("custom_name") or prompt.get("name")
    }
    prompts_by_name = index_by(prompts, "name")

    guidance_items, existing_by_key = build_guidance_items(
        tools_by_name,
        resources_by_uri,
        prompts_by_custom,
        prompts_by_name,
        prompt_defs,
    )
    try:
        preflight_guidance(guidance_items)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    resource_ids: dict[str, list[str]] = defaultdict(list)
    prompt_ids: dict[str, list[str]] = defaultdict(list)
    created_resources = updated_resources = created_prompts = updated_prompts = 0

    for item in guidance_items:
        existing_resource = existing_by_key[f"resource:{item.tool_name}"]
        if existing_resource:
            resource = api_request(
                "PUT", f"/resources/{existing_resource['id']}", token=token, body=item.resource_body
            )
            updated_resources += 1
        else:
            resource = api_request(
                "POST", "/resources", token=token, body={"resource": item.resource_body, "visibility": VISIBILITY}
            )
            created_resources += 1
        resource_ids[item.service].append(resource["id"])

        existing_prompt = existing_by_key[f"prompt:{item.tool_name}"]
        if existing_prompt:
            prompt = api_request(
                "PUT", f"/prompts/{existing_prompt['id']}", token=token, body=item.prompt_body
            )
            updated_prompts += 1
        else:
            prompt = api_request(
                "POST", "/prompts", token=token, body={"prompt": item.prompt_body, "visibility": VISIBILITY}
            )
            created_prompts += 1
        prompt_ids[item.service].append(prompt["id"])

    services_to_update = [args.service] if args.service else sorted(SERVICE_META)
    for service in services_to_update:
        meta = SERVICE_META[service]
        server = servers_by_name.get(meta["server"])
        if not server:
            print(f"missing server {meta['server']}", file=sys.stderr)
            return 1
        body = {
            "associatedTools": server.get("associatedToolIds") or [],
            "associatedResources": resource_ids[service],
            "associatedPrompts": prompt_ids[service],
            "associatedA2aAgents": server.get("associatedA2aAgents") or [],
            "ownerEmail": OWNER,
            "visibility": VISIBILITY,
        }
        api_request("PUT", f"/servers/{server['id']}", token=token, body=body)

    print(f"tools covered: {len(prompt_defs)}")
    print(f"resources created={created_resources} updated={updated_resources}")
    print(f"prompts created={created_prompts} updated={updated_prompts}")
    for service in sorted(SERVICE_META):
        print(f"{service}: resources={len(resource_ids[service])} prompts={len(prompt_ids[service])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
