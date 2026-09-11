# ConfigCrawler — Expand Protocol Search Scope
## Integration Task — Existing Project

ConfigCrawler is ALREADY under active development.

Do NOT rebuild the project.
Do NOT redesign the architecture.
Do NOT create a new application.
Do NOT replace existing search/scraping/extraction systems.

The goal of this task is ONLY to expand the existing ConfigCrawler search scope so that the current engine can discover, extract, classify and validate additional protocol/config types.

---

# OBJECTIVE

Extend the EXISTING ConfigCrawler implementation to support the following protocol families as searchable targets.

## Xray / V2Ray

- VLESS
- VLESS Reality
- VMess
- Trojan
- VLESS TCP
- VLESS WebSocket
- VLESS gRPC
- VLESS TLS
- VLESS XTLS / Vision
- VMess TCP
- VMess WebSocket
- VMess TLS
- Trojan TLS
- Trojan WebSocket
- Trojan gRPC

## VPN

- IKEv2
- IKEv2 MSCHAPv2
- WireGuard
- OpenVPN
- L2TP
- L2TP/IPsec
- SoftEther
- PPTP

## SSH / Tunnel

- SSH Tunnel
- SSH Direct
- SSH Proxy
- SSH Payload
- SSH Proxy Payload
- SSH TLS
- SSH TLS Proxy
- SSH TLS Payload
- SSH DNSTT

---

# IMPORTANT

These protocols must become part of the EXISTING search system.

Do NOT simply add them as labels in the GUI.

The search engine must actually be able to search for their configurations.

The existing functionality must continue working exactly as before.

---

# SEARCH DISCOVERY

Extend the EXISTING query-generation mechanism.

For each protocol, add relevant search terms, aliases and configuration indicators.

Examples:

### VLESS

- free vless config
- free vless nodes
- vless subscription
- vless configs
- vless reality
- vless reality config
- vless reality nodes
- vless websocket
- vless grpc
- vless tls
- vless://

### VMess

- free vmess config
- free vmess nodes
- vmess subscription
- vmess configs
- vmess://
- free v2ray config
- free v2ray nodes

### Trojan

- free trojan config
- free trojan nodes
- trojan subscription
- trojan tls
- trojan websocket
- trojan grpc
- trojan://

### WireGuard

- free wireguard config
- free wireguard server
- free wireguard nodes
- wireguard config
- wireguard .conf
- PrivateKey
- PublicKey
- Endpoint

### OpenVPN

- free openvpn config
- free openvpn server
- free ovpn
- openvpn config
- .ovpn
- client.ovpn
- remote
- dev tun

### IKEv2

- free ikev2 config
- free ikev2 server
- ikev2 vpn
- ikev2 mschapv2
- ikev2 certificate

### L2TP

- free l2tp vpn
- free l2tp ipsec
- l2tp config
- l2tp server

### SoftEther

- free softether vpn
- softether server
- softether config
- softether vpn server

### PPTP

- free pptp vpn
- pptp server
- pptp config

### SSH

- free ssh account
- free ssh server
- free ssh config
- ssh tunnel
- ssh proxy
- ssh payload
- ssh tls
- ssh dnstt
- ssh tunnel github

---

# PROTOCOL DETECTION

Extend the EXISTING protocol detection mechanism.

Detection must work from the actual configuration content, not only from the page title.

Examples:

vless://
→ VLESS

vmess://
→ VMess

trojan://
→ Trojan

WireGuard structures containing:

[Interface]
PrivateKey=
Address=

[Peer]
PublicKey=
Endpoint=

→ WireGuard

OpenVPN structures containing directives such as:

client
dev tun
proto
remote

→ OpenVPN

Other protocols should similarly use their structural/content signatures.

---

# PROTOCOL ALIASES

Support aliases when searching.

Examples:

VLESS:
- VLESS
- Xray VLESS
- Xray
- V2Ray VLESS

VMess:
- VMess
- V2Ray
- V2Ray VMess

Reality:
- Reality
- Xray Reality
- VLESS Reality

WireGuard:
- WireGuard
- WG
- Wireguard VPN

OpenVPN:
- OpenVPN
- OVPN

IKEv2:
- IKEv2
- IKE2
- IKEv2/IPsec
- MSCHAPv2

SoftEther:
- SoftEther
- SoftEther VPN

---

# CONFIG EXTRACTION

Use the EXISTING extraction pipeline.

Do not create a completely separate scraper architecture.

The pipeline should become:

SOURCE
→ FETCH
→ PARSE
→ DETECT PROTOCOL
→ EXTRACT CONFIG
→ NORMALIZE
→ VALIDATE
→ DEDUPLICATE
→ SCORE
→ STORE

Reuse existing components wherever possible.

---

# NORMALIZATION

Extend the existing Config model/schema only where necessary.

Common fields may include:

- protocol
- subtype
- host
- port
- username
- password
- uuid
- transport
- security
- tls
- sni
- public_key
- fingerprint
- endpoint
- source
- discovered_at
- expiration
- status
- latency
- quality_score

Do NOT force protocol-specific fields onto protocols that don't use them.

Use optional metadata where appropriate.

---

# DEDUPLICATION

Reuse the existing deduplication mechanism.

The same configuration may appear on:

- multiple websites
- multiple GitHub repositories
- multiple files
- multiple subscription sources

The crawler should recognize duplicates even when formatting differs.

Do not introduce a second independent duplicate system if one already exists.

---

# EXPIRATION

Use the existing expiration/health mechanisms if they already exist.

Where possible detect:

- explicit expiration dates
- expired subscriptions
- expired accounts
- unavailable servers
- dead configs

Possible statuses:

ACTIVE
EXPIRING_SOON
EXPIRED
DEAD
UNKNOWN

Do not assume every free configuration is permanent.

---

# VALIDATION

Extend the existing validator architecture.

Validators should be protocol-aware.

Examples:

VLESS:
- valid URI
- UUID
- host
- port

VMess:
- valid URI/encoding
- UUID
- host
- port

WireGuard:
- PrivateKey format
- PublicKey format
- Endpoint
- Address

OpenVPN:
- valid OpenVPN directives
- remote endpoint
- configuration structure

SSH:
- host
- port
- username
- tunnel structure

Do not implement actual authentication against third-party services merely to validate syntax.

Use the project's existing safe validation/health-check mechanisms.

---

# QUALITY SCORE

Integrate these protocols into the EXISTING quality scoring system.

Where supported, consider:

- syntax validity
- freshness
- source reliability
- availability
- latency
- expiration
- completeness
- duplicate frequency

Do NOT create a separate scoring system if ConfigCrawler already has one.

---

# GUI

If the existing GUI already has protocol filters/categories, extend them.

Suggested grouping:

Xray / V2Ray
- VLESS
- Reality
- VMess
- Trojan

VPN
- WireGuard
- OpenVPN
- IKEv2
- L2TP/IPsec
- SoftEther
- PPTP

SSH / Tunnel
- SSH Tunnel
- SSH Proxy
- SSH Payload
- SSH TLS
- SSH DNSTT

Do not redesign the existing GUI.

Only extend the existing protocol filter/category system.

---

# FUTURE EXTENSIBILITY

The implementation should allow adding another protocol later without modifying the core crawler.

Prefer extending the project's existing registry/configuration/profile mechanism.

For example, conceptually:

Protocol
├── id
├── aliases
├── search_terms
├── signatures
├── extraction rules
└── validation rules

But FIRST inspect the existing architecture and adapt to it.

Do not force this exact structure if the project already has an equivalent mechanism.

---

# SEARCH QUERY GENERATION

The query generator should be capable of combining:

protocol
+
alias
+
config/node/server/subscription
+
transport
+
source

Examples:

free + vless + reality + config

free + wireguard + server

free + openvpn + ovpn

free + ssh + tunnel

free + trojan + tls

The system should generate queries programmatically rather than requiring hundreds of manually hardcoded queries.

---

# SOURCE COVERAGE

Apply the new protocols to the EXISTING supported source types.

Where the current crawler already supports:

- web search
- GitHub
- GitLab
- raw files
- public repositories
- configuration websites
- subscription sources

make the new protocol searches work through those existing mechanisms.

Do NOT add a new external service unless it is already part of the project's architecture.

---

# IMPLEMENTATION RULES

1. Inspect the current implementation first.
2. Identify the existing protocol/search/extraction/validation components.
3. Modify the SMALLEST possible number of files.
4. Reuse existing abstractions.
5. Do not duplicate functionality.
6. Do not rewrite working components.
7. Do not change unrelated features.
8. Do not change the UI design.
9. Do not change database architecture unless required.
10. Preserve backward compatibility.

---

# TESTING

Before finishing:

Run the project's existing tests.

Add focused tests for the new protocol detection/search logic.

At minimum test detection for:

- VLESS
- Reality
- VMess
- Trojan
- WireGuard
- OpenVPN
- IKEv2
- L2TP
- SoftEther
- PPTP
- SSH

Verify that existing protocols still pass all previous tests.

Report:

- files changed
- files added
- tests added
- tests passed
- tests failed
- remaining limitations

---

# EXECUTION MODE

IMPORTANT:

Do NOT start by making large changes.

First perform a SHORT implementation audit of the CURRENT project.

Report:

1. Existing protocol system
2. Existing search/query system
3. Existing extraction system
4. Existing validation system
5. Existing data model
6. Existing GUI protocol filter
7. Exact files that need modification
8. Minimal implementation plan

Then implement the changes in SMALL, SAFE STEPS.

Do not rebuild ConfigCrawler.

The goal is:

CURRENT ConfigCrawler
+
Expanded multi-protocol discovery
+
Protocol-aware detection
+
Protocol-aware extraction/validation

while preserving everything already implemented.
