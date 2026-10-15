# Corporate Helper: shared message queue and master routing

Status: tested contract/core rules, not a deployed messaging service.

## Deployment model
Install the same versioned helper package on every human workstation. Local capture, microphone, browser/native messaging and machine controls execute locally. Shared Drive operations, recipient lookup, queue transitions, message routing and other uniform business rules are handed to the authenticated master through verified HTTPS over a Corporate Helper-managed SSH tunnel. Deployment hostname, port, reply domain, Drive folder ID and secrets are private configuration, not public source defaults.

IsIam compares the enrolled node identity and signed master identity, not DNS resolution, public IP, NAT address or a self-declared flag. Exact release compatibility means version plus source/build digest. A matching release is necessary for fallback, not permission to write concurrently.

Before a request leaves a workstation, persist its request ID and route. The master returns a durable receipt containing request ID, authenticated worker GUID, operation, result hash and Drive file ID. An acknowledgement means committed and reconciled, not merely received. On timeout, query the same request ID. UNKNOWN blocks replay. A fallback executor needs an exclusive, fenced lease from shared authority and exact release agreement. If authority is unreachable, hold pending work. Exactly-once delivery is not asserted: ambiguous provider sends require reconciliation.

## Browser-to-helper request
A completed response in an authorized paired chat may carry:

```json
{"protocol":"corporate-helper/1","request_id":"22222222-2222-4222-8222-222222222222","tool":"sms.enqueue","arguments":{"recipient":"Example contact","text":"Example message"}}
```

The worker GUID comes from the authenticated session mapping, never an arbitrary JSON field. Unknown tools, extra fields, invalid arguments and duplicate IDs are rejected or reconciled. A GUID is a routing identifier, not a credential. The reply map retains worker GUID, provider, conversation reference and authorized paired helper(s). Offline conversations receive durable pending replies; browser automation delivery remains to be implemented.

## Queue files
One authoritative Google Drive channel folder contains incoming and outgoing records. Locate it by stable Drive folder ID so renaming cannot break policy. Files are text/plain email records with headers and message body.

Filename: YYYYMMDDTHHMMSSffffffZ.(out).SENDER-GUID.txt; inbound uses (in). Timestamp is controller UTC with microsecond precision, sortable lexically. Request ID/Message-ID is the deduplication key; filenames are not locks and Drive permits duplicate names. The production writer must resolve timestamp collisions and persist its request-to-file mapping under serialized/fenced execution.

Outbound: AI -> human. Top headers include X-Worker-GUID, X-Request-ID, queue state, direction and created UTC. The processor adds Worker-GUID to the body. Resolve names through the private directory; never derive a carrier from a nickname or assume an example number's current carrier. Use Reply-To: WORKER-GUID.sms@configured-domain. Sender address uses an authenticated mail account configured separately.

Inbound: human -> AI. Preserve raw source email, provider ID, sender/contact GUID, target worker GUID, request/conversation correlation and verification result. Incoming filename uses the human sender/contact GUID, not a fabricated AI sender identity. Unknown senders or ambiguous conversations are held for resolution. Prefer a new correlated reply record; do not overwrite the original.

A single shared SMS number requires a bidirectional phone/SMS provider or an authorized phone gateway. Replies to that number are routed by explicit worker/conversation context and thread mapping; if ambiguous, ask the sender which worker. Email Reply-To alone does not provide a shared phone number or guarantee carrier reply routing. Domain MX/mailbox routing for GUID.sms aliases is separate configuration; publishing a header does not create a mailbox.

## State and audit
QUEUED -> CLAIMED -> PROVIDER_ACCEPTED -> DELIVERED when supported, with FAILED and UNKNOWN states. Preserve append-only transition/audit receipts. SMTP acceptance and email dispatch do not prove handset delivery. The master records who requested, which helper relayed, who executed, when, why, outcome and reply route. Queueing does not itself send a message.

## Objectives exception
All _readme.txt files are exempt from paired .objectives generation. All direct children of the authoritative SMS queue folder are exempt. Match by folder ID, not loose substring matching. Do not exempt unrelated documents or alter existing objectives files. The predicate in shared/queue_contract.py is implemented and tested; the existing filesystem save gate still needs to invoke it before companion generation. Policy declaration is not deployment evidence.

## Carrier adapter
Legacy carrier email transport is replaceable and disabled until verified. Verizon official notice: https://www.verizon.com/support/vtext-vzwpix-shutdown/ . Legacy Vtext/VZWPix is being retired, with anticipated completion March 31, 2027 and possible earlier failures. It is not a guaranteed business SMS channel. No carrier address or personal contact is published here.

## Tests and remaining work
Run python3 -m unittest discover -s tests -p test_queue_contract.py -v. Ten contract tests cover authenticated worker binding, unsupported commands, header injection, email format, UTC sorting, exemptions, uncertain outcomes, exact-release/fenced fallback, master identity and reply routing. These do not test live SMTP, Drive concurrency, browser automation, actual failover, or phone delivery.

Remaining adapters: durable Drive queue writer and idempotency ledger, fenced master lease/receipts, save-gate integration, mailbox ingest and GUID alias routing, shared phone-number provider, recipient directory, browser JSON/result transport, deployment/update verification and end-to-end tests. Do not reactivate the old SMS dispatcher against this queue until duplicate prevention and transport selection are verified.
