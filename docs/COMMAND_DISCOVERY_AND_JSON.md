# Corporate Helper: command discovery and JSON interface

Design agreed with Joe, 2026-10-15. Destination: Channels / Corporate Helper.

## Status

Documentation maintenance directive: update the documents in Channels / Corporate Helper as work proceeds. Every feature or command change must update its relevant instructions, JSON schemas and examples, configuration and deployment steps, installed version/status, verification results, and remaining work. Clearly distinguish planned, implemented, deployed, and verified behavior. Update existing files in place to preserve their identity and history; do not leave obsolete instructions presented as current. Documentation updates are part of completing the change.

Update 2026-10-15: Corporate Helper 0.2.0 is deployed on Alpine; its HTTPS health response was read with certificate verification. The browser-specific registry, helper_help, and five session-scoped tools are implemented at authenticated POST /browser/mcp. Corporate Extension 0.3.0 implements a Gemini chat JSON adapter; installation and native Gemini/Supermium interaction remain to be verified. The DiskPart-style contextual console and tunnel/pipeline commands remain planned. The existing operator /mcp interface is separate. Eight combined extension/helper core tests pass; TLS integration verification is recorded in the deployment status.

## Contextual console

The console behaves like DiskPart: help or ? lists commands for the current context. Entering a module changes context. help <command> explains arguments and examples; back returns to the parent; exit closes the console. status describes the current context.

Proposed contexts: tunnels, pipeline, browser. The root also exposes helper status. List unavailable modules explicitly as unavailable with a reason; never imply that a proposed operation is executable.

Example:

```text
corporate-helper> tunnels
corporate-helper/tunnels> help
list         Show configured tunnels
status       Show connection status
connect      Connect a tunnel
disconnect   Disconnect a tunnel
back         Return to the main menu
corporate-helper/tunnels> help connect
```

## One command registry

Define each command once. The same definition supplies console help, HTTPS discovery, and MCP tool descriptions and input schemas. Each entry includes its stable identifier, context, description, required and optional arguments, types, allowed values, defaults, examples, permissions, read/write effects, availability and reason, handler, and success/error output schemas. Record installed helper version and schema version in discovery results.

Discovery must reflect the authenticated caller's permissions. A description or example does not grant execution rights. Validate arguments at execution against the same schema. Reject unknown commands and arguments with actionable errors; never reinterpret text as arbitrary shell code.

## Explicit JSON instruction

For every command, provide its purpose, exact tool name, argument schema, full request example, success example, error example, permissions, and whether it changes state. Discovery is available on demand so a worker does not need to remember the interface permanently.

MCP uses JSON-RPC 2.0. A native MCP client first performs the protocol initialization and capability negotiation supported by the installed server. Then it can discover tools:

```json
{"jsonrpc":"2.0","id":"help-1","method":"tools/list","params":{}}
```

Browser endpoint status call:

```json
{"jsonrpc":"2.0","id":"status-1","method":"tools/call","params":{"name":"helper_status","arguments":{}}}
```

Browser endpoint read-only help tool:

```json
{"jsonrpc":"2.0","id":"help-2","method":"tools/call","params":{"name":"helper_help","arguments":{"context":"browser","command":"browser_request_snapshot"}}}
```

Implemented helper_help arguments (contexts helper and browser only): an object with optional string context and command; reject additional properties. Omitting both returns root help. A context returns that context's commands. A command returns its complete instructions; ambiguous or unknown names return an explicit error. The tool never executes the command it describes.

Illustrative MCP tool success response (not observed runtime output):

```json
{"jsonrpc":"2.0","id":"status-1","result":{"content":[{"type":"text","text":"{\"status\":\"running\"}"}],"isError":false}}
```

Illustrative malformed-parameters response:

```json
{"jsonrpc":"2.0","id":"status-1","error":{"code":-32602,"message":"Invalid params: arguments must be an object"}}
```

Distinguish protocol errors from tool execution failures. Tool failures use the negotiated MCP tool-result format and give a useful, sanitized reason. Never return credentials in errors or examples.

## Browser chat adapter

A sandboxed chat model emits structured JSON in its conversation. Corporate Extension identifies a complete request, validates it, and forwards it through an authenticated connection to Corporate Helper. The adapter uses the existing SRP/HMAC browser transport and returns the correlated result through the chat's supported interface. Printing JSON alone does not execute anything. The Gemini adapter is implemented. It requires a corporate_helper envelope around the RPC object and a per-chat grant from the extension popup. It stages corporate_helper_result JSON and submits using the native empty composer/Send control when identified. Fallback insertion remains available. Native browser interaction is not yet verified. See JACK_START_HERE.txt for exact instructions.

Authenticate the worker independently of any GUID claimed in chat text. Enforce explicit supported-tool permissions. Track request identity and duplicate execution, especially for writes; reconcile uncertain completion before retrying. Distinguish pending, completed, failed, and uncertain results. Process intended assistant request blocks, not arbitrary quoted page text.

Administrative web posting forms remain loopback-only (127.0.0.1). Remote worker access uses authenticated authorized endpoints over HTTPS. These are separate scopes of access.

## Implementation and verification checklist

- Inventory installed handlers before exposing them.
- Add the shared registry and contextual console.
- Generate explicit help, schemas, and examples from that registry.
- Expose authorized discovery through HTTPS and MCP.
- Build authenticated browser chat request/result forwarding.
- Verify help matches real handlers; reject malformed/unknown input.
- Verify permission filtering, unavailable modules, duplicate-write handling, and result correlation.
- Test Jack discovering help, requesting status, and receiving the actual result end to end.

## Review

Potential flaw: examples could be mistaken for installed features. Correction: mark proposed names and responses throughout; publish installed availability from runtime discovery. Re-evaluation: implementation is described above; no successful live Jack chat round-trip is claimed.

Potential flaw: separate help documents can drift. Correction: use a single registry for execution validation and all discovery surfaces. Re-evaluation: implementation must test consistency before deployment.

## Current browser tool scope

helper_status, helper_help, browser_status, browser_request_snapshot, browser_snapshot_result. All are restricted to the authenticated paired session; captures additionally require enabled tabs. Other sessions and operator credentials are not exposed. Enrollment does not establish an independent worker GUID. Read-only captures are limited to 12,000 redacted visible-text characters. No screen images or pipeline writes are enabled.

Deployment verification: all 16 installed Alpine helper tests passed, including actual verified HTTPS/SRP/browser JSON integration. Five extension Node tests passed locally. The deployment administration request timed out before returning a final receipt; subsequent verified live health and an independent installed-code test run confirmed service version 0.2.0 and passing tests. No deployment request was repeated. Native Gemini/Supermium round-trip remains unverified.

2026-10-15 extension 0.3.1: fixed layout observer feedback by retaining hidden panel state across DOM mutations; only an off/settings transition restores styles. Regression: 20 DOM mutations cause no repeated hide/restore; off restores once. Six extension tests pass. Popup now exposes the chat-only on/off switch with other controls under collapsed Settings. Reload extension and Gemini tab to unload 0.3.0 scripts. Live browser confirmation pending.

2026-10-15 extension 0.3.2: main popup now has exactly On/Off and Settings. On/Off controls both chat-only layout and Gemini JSON grants. Status probes /browser/mcp ping using session HMAC; it reports helper reachability rather than claiming SSH tunnel ownership. Configuration opens separately while preserving the target chat tab. Seven extension tests pass. The Windows tunnel supervisor remains missing; existing PuTTY tunnel must remain open.

## Founder correction: automatic means automatic (2026-10-15)

The hourly manual pairing workflow and instructions to keep PuTTY open do not satisfy the requested product. Versions through 0.3.2 are development previews, not an accepted automatic deployment. Do not ask the founder to install another UI-only revision as though it completes the request.

Acceptance requires: one installation/enrollment; retained machine enrollment using the native helper; automatic authentication renewal after session expiry; reconnect after browser, helper, computer and master restarts; Windows boot startup; SSH tunnel supervision with 30-second retries; automatic authorization of the active supported chat when On; exactly two main controls (On/Off and Settings); and an authenticated connection status. No recurring address/identity/password entry, hourly pairing, separate per-chat JSON switch, or manually maintained PuTTY window.

The implementation must verify these acceptance cases on the actual Windows Server 2003/Supermium machine before claiming completion. Automatic enrollment and tunnel supervision remain unfinished. Current tools reach Alpine and read enabled Windows browser tabs; they do not provide a Windows shell or native installation channel. A native Windows helper installation is required for SSH supervision and OS-protected enrollment storage.

## 0.4.0 automatic architecture — latest direction, 2026-10-15

This supersedes the earlier interpretation that clients authenticate to the master. Only the master initiates/authenticates helper-to-helper connections, and only to literal IPv4 addresses on its actual LAN subnet. Verified current interface: 10.0.0.195/24, network 10.0.0.0/24. Non-master helpers listen, discover the advertised master, and send connectionless readiness replies. They never dial another helper. Discovery grants no access. Native authenticated requests require the exact master certificate pin and an actual same-subnet source address. The master verifies the enrolled peer certificate pin as well. No DNS/proxy/redirect/Internet fallback is used for peer connections.

The Windows-initiated SSH supervisor design is superseded for this helper control channel: it would contradict the master-only initiation rule. The replacement is a master-initiated TLS 1.2 channel, discovered over UDP 18768 and served by the Windows helper on its LAN address TCP 18766. The local native host uses authenticated loopback TLS IPC on 127.0.0.1:18765. Administrative/local posting remains loopback-only. Existing SSH forwards and the Gateway are preserved; unrelated SSH tunnel automation is not claimed.

Corporate Extension 0.4.0 uses Chrome native messaging to its local helper only. There is no browser pairing/password form or one-hour enrollment. Machine enrollment is retained with Windows DPAPI, restricted to the installer account and SYSTEM. Installer configures an ONSTART task, listener watchdog, LAN-scoped firewall entries and a stable extension ID. Master OpenRC service starts at boot, advertises discovery, binds the source interface and validates the current subnet before every connection/exchange. Failed peer connections retry after 30 seconds. IP changes trigger listener/master restarts with retained enrollment.

The main popup has exactly On/Off and Settings. When On, an active Gemini chat is enabled automatically. Non-Gemini JSON DOM adapters remain unimplemented. Nine native Python tests and nine extension tests pass locally. The native code is written for Python 3.4 syntax/API compatibility; the bundle includes the official x86 Python 3.4.4 MSI to avoid runtime setup fields. Windows Server 2003 DPAPI, installer/task/firewall/native-host launch and real Supermium behavior remain to verify on the physical machine. A private personalized installer is produced on Alpine and saved only in Channels / Corporate Helper; it must not be published to GitHub or reused for another machine.

Only five read-only tools are exposed. All request, text-capture and deduplication state remains in memory. Device identity does not establish a persistent worker GUID. Public source contains no enrollment secrets. Certificate expiry/rotation and enrollment of additional machines require subsequent lifecycle work; no indefinite certificate lifetime is claimed.

Review: fixed the previously reversed connection direction; removed recurring pairing fields; fail-closed actual subnet policy checked before socket creation; pinned master and peer proofs; non-master code has no LAN connection initiator; API schemas and native frame bounds tested. BusyBox lacks ip -j; inventory now parses its real numeric output with a regression test. Production acceptance remains blocked on Windows-native verification.
