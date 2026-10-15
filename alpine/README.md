# Corporate Helper: Alpine browser-broker migration candidate

This first migration replaces the existing authenticated browser broker on its current loopback HTTPS endpoint. It preserves SRP enrollment, certificate, operator API and MCP tools. It does not replace the live external Gateway tunnel or pipeline services.

The server uses a bounded raw TLS socket transport (32 concurrent sockets, 8 KiB headers, 64 KiB body, 10 second socket timeout). It accepts one HTTP request per connection, rejects duplicate headers, request pipelining and chunked framing, and requires TLS 1.2 or newer. Administrative status is authenticated and loopback-only. Configuration forms and writes are not yet implemented. Node handles connections asynchronously; a dedicated application worker pool is pending.

Existing pairing labels and key derivation retain their old protocol identifier for compatibility; new application names are generic. Machine-specific enrollment and keys remain outside source code. No credentials are included in this package.

Run `doas python3 -I /opt/peostectica-projects/corporate-helper/alpine/install.py` in the Alpine terminal after staging. The installer verifies package hashes, runs SRP and HTTPS tests as the service account, switches the browser service, checks health, and enables boot startup. It restores the old browser service on switch failure. Active in-memory browser sessions must pair again after the switch, but the enrolled identity/password remains valid. OpenRC restarts a crashed broker after 30 seconds; this is not yet an SSH retry implementation.

Do not stop the peostectica-tunnel Gateway service. Do not use the unrelated supermium_bridge script as a replacement: it assumes plain HTTP at a public hostname and has no retry loop. After the new broker passes its health check, the installer stops this obsolete service if running and removes its boot entry; it retains the script and restores the prior service state on installation failure.

Pending: Windows native service and tunnel supervision; active-tab extension toggle; unattended enrollment renewal; authenticated controller discovery; firewall administration; worker pool; repository publication. The current SSH client role belongs on Windows; no second tunnel mapping has been verified.

Validation: run `node --test test.cjs https-test.cjs`. The HTTPS test creates temporary test credentials, verifies TLS, authenticates SRP, advertises an eligible tab, requests a snapshot through MCP, returns it, and checks revocation. This simulates a browser client; it does not certify the installed extension or Windows compatibility.

GitHub repository name: corporate-helper. URL: pending creation.

Browser JSON upgrade 0.2.0: signed POST /browser/mcp offers session-scoped helper_status, helper_help, browser_status, browser_request_snapshot and browser_snapshot_result. Existing operator /mcp remains separate. Sixteen installed tests pass; live health verified. Corporate Extension 0.3.0 supplies the Gemini chat adapter. See Channels / Corporate Helper / JACK_START_HERE.txt. install.py is for initial installations only; existing deployments use the founder-audited fixed upgrade routine with tests and rollback.
