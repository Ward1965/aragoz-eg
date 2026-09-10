# ConfigCrawler — Comprehensive Android/VPN Config Protocol Coverage

## الهدف

توسيع برنامج **ConfigCrawler** ليكون محركًا عامًا لاكتشاف وجلب واستخراج وتصنيف وفحص ملفات وروابط الكونفيجات المستخدمة في تطبيقات Android الخاصة بالـ tunneling / proxy / VPN.

**مهم:** لا تتعامل مع القائمة التالية على أنها 117 بروتوكولًا مستقلًا. كثير من العناصر هي تركيبات من:
- Protocol
- Transport
- Security
- Proxy
- Payload
- DNS transport
- Obfuscation / CDN / Fronting

يجب أن يكون محرك البرنامج قادرًا على اكتشاف التركيبات المختلفة وتطبيعها إلى نموذج بيانات موحد.

---

# 1. SSH / SSH Tunneling

1. SSH Direct
2. SSH Proxy
3. SSH Payload
4. SSH Proxy + Payload
5. SSH TLS
6. SSH TLS + Proxy
7. SSH TLS + Payload
8. SSH TLS + Proxy + Payload
9. SSH WebSocket
10. SSH WebSocket + TLS
11. SSH over HTTP CONNECT
12. SSH over SOCKS
13. SSH over CDN / Fronting
14. SSH over DNS
15. SSH over DNSTT
16. SSH over SlowDNS
17. SSH over NoizDNS
18. SSH over VayDNS
19. SSH over Slipstream

---

# 2. HTTP / HTTPS / Payload

20. HTTP Proxy
21. HTTPS Proxy
22. HTTP Proxy + Payload
23. HTTP Proxy + SSL/TLS
24. HTTP Proxy + SSL/TLS + Payload
25. HTTP CONNECT
26. HTTP CONNECT + TLS
27. HTTP Proxy + WebSocket
28. HTTP Proxy + CDN / Fronting

---

# 3. SSL / TLS Tunnels

29. SSL Tunnel
30. TLS Tunnel
31. SSH over TLS
32. Proxy over TLS
33. SSL + Payload
34. SSL + Proxy
35. SSL + Proxy + Payload
36. TLS + WebSocket
37. TLS + HTTP/2
38. TLS + gRPC

---

# 4. DNS Tunneling

39. DNS Tunnel
40. SlowDNS
41. FastDNS
42. DNSTT
43. DNSTT + SSH
44. DNSTT + V2Ray
45. NoizDNS
46. NoizDNS + SSH
47. VayDNS
48. VayDNS + SSH
49. Slipstream
50. DNS over HTTPS (DoH)
51. DNS over TLS (DoT)

---

# 5. V2Ray / Xray — VLESS

52. VLESS
53. VLESS + TLS
54. VLESS + Reality
55. VLESS + WebSocket
56. VLESS + WebSocket + TLS
57. VLESS + gRPC
58. VLESS + gRPC + TLS
59. VLESS + XHTTP
60. VLESS + XHTTP + TLS
61. VLESS + HTTPUpgrade
62. VLESS + TCP / RAW
63. VLESS + Vision
64. VLESS + Reality + Vision

---

# 6. V2Ray / Xray — VMess

65. VMess
66. VMess + TLS
67. VMess + WebSocket
68. VMess + WebSocket + TLS
69. VMess + gRPC
70. VMess + HTTPUpgrade
71. VMess + TCP / RAW
72. VMess + mKCP

---

# 7. Trojan

73. Trojan
74. Trojan + TLS
75. Trojan + WebSocket
76. Trojan + WebSocket + TLS
77. Trojan + gRPC
78. Trojan + HTTPUpgrade

---

# 8. Shadowsocks

79. Shadowsocks
80. Shadowsocks + TCP
81. Shadowsocks + UDP
82. Shadowsocks + TLS
83. Shadowsocks + WebSocket
84. Shadowsocks + WebSocket + TLS
85. Shadowsocks + gRPC

---

# 9. Hysteria

86. Hysteria
87. Hysteria 2
88. Hysteria 2 + TLS
89. Hysteria + QUIC
90. Hysteria + UDP
91. Hysteria + SlowUDP

---

# 10. TUIC

92. TUIC
93. TUIC v4
94. TUIC v5
95. TUIC + TLS

---

# 11. WireGuard / VPN

96. WireGuard
97. WireGuard over UDP
98. WireGuard over TCP
99. WireGuard + Obfuscation
100. OpenVPN
101. OpenVPN TCP
102. OpenVPN UDP

---

# 12. Generic Proxy Protocols

103. SOCKS4
104. SOCKS4a
105. SOCKS5
106. SOCKS5 + TLS
107. HTTP
108. HTTPS
109. HTTP CONNECT

---

# 13. Modern / Additional Technologies

110. NaiveProxy
111. NaiveProxy + TLS
112. NaiveProxy + HTTP/2
113. NaiveProxy + QUIC
114. Tor
115. Tor + Bridge
116. Tor + Obfs4
117. Tor + Snowflake

---

# 14. Android Config Formats

يجب ألا يبحث البرنامج عن البروتوكولات فقط، بل عن صيغ الكونفيجات الشائعة في تطبيقات Android.

يجب تصميم النظام بحيث يمكن إضافة صيغ جديدة بدون تعديل جوهري في محرك الاستخراج.

أمثلة على ما ينبغي اكتشافه:

- Raw URLs
- URI schemes
- JSON configs
- YAML configs
- TXT config files
- ZIP-based config files
- Encrypted / encoded config files
- Base64 encoded configs
- QR-code encoded configs
- Deep links
- Application-specific config exports
- Subscription URLs
- Plain-text server lists
- Structured API responses

كما يجب دعم اكتشاف الامتدادات والصيغ الخاصة بالتطبيقات عندما تكون معروفة، مع عدم افتراض أن اسم الامتداد وحده كافٍ لتحديد البروتوكول.

---

# 15. URI / Link Schemes يجب اكتشافها

أنشئ نظامًا مرنًا لاكتشاف URI schemes بدل الاعتماد على قائمة ثابتة فقط.

أمثلة مهمة:

- vless://
- vmess://
- trojan://
- ss://
- tuic://
- hysteria://
- hysteria2://
- wg:// أو صيغ WireGuard المناسبة
- socks:// أو صيغ SOCKS عندما تكون مستخدمة
- http://
- https://

يجب أيضًا اكتشاف الروابط التي تحتوي على:

- server
- host
- port
- username
- password
- uuid
- security
- encryption
- network
- type
- path
- host header
- sni
- alpn
- fingerprint
- publicKey
- shortId
- flow
- serviceName
- authority
- obfs
- plugin
- remarks

**لا تفترض أن كل URI scheme موحد بين التطبيقات.**

---

# 16. Payload Detection

يجب أن يكون Payload عنصرًا مستقلاً في نموذج البيانات.

اكتشف على الأقل:

- HTTP GET payload
- HTTP POST payload
- CONNECT payload
- Custom Host
- Host Header
- SNI
- User-Agent
- Custom headers
- HTTP method
- Request path
- Query parameters
- Keep-Alive
- Upgrade
- WebSocket handshake
- SSL payload
- Custom payload templates

يجب حفظ الـPayload الخام، وكذلك نسخة normalized/parsed عند الإمكان.

---

# 17. Transport Layer

أنشئ طبقة Transport مستقلة.

يجب التعرف على:

- TCP
- UDP
- QUIC
- RAW TCP
- WebSocket
- gRPC
- HTTP/2
- HTTPUpgrade
- XHTTP
- mKCP
- DNS
- DoH
- DoT
- CONNECT
- SOCKS transport

---

# 18. Security Layer

أنشئ طبقة Security مستقلة.

القيم المحتملة تشمل:

- None
- TLS
- TLS 1.2
- TLS 1.3
- Reality
- SSH encryption
- Obfuscation
- Custom encryption
- Certificate-based TLS
- Insecure TLS / allowInsecure

لا تعتبر `allowInsecure=true` ميزة جودة؛ يجب أن تكون إشارة تحذير في التقييم.

---

# 19. Proxy Layer

يجب فصل Proxy عن Protocol.

القيم:

- None
- HTTP
- HTTPS
- HTTP CONNECT
- SOCKS4
- SOCKS4a
- SOCKS5
- SOCKS5 TLS
- Custom proxy

---

# 20. DNS Layer

اكتشف:

- Normal DNS
- DNS Tunnel
- SlowDNS
- FastDNS
- DNSTT
- NoizDNS
- VayDNS
- Slipstream
- DoH
- DoT

وسجل:

- DNS server
- domain
- resolver
- transport
- tunnel mode
- server address
- port

---

# 21. CDN / Fronting / Domain Fronting Indicators

اكتشف عند وجودها:

- CDN
- Cloudflare
- Reverse proxy
- Domain fronting indicators
- SNI
- Host header mismatch
- CDN hostname
- Origin hostname
- WebSocket path
- gRPC service name

يجب ألا يصنف البرنامج هذه العناصر تلقائيًا كـ "Domain Fronting" إلا إذا كانت الأدلة الموجودة في الكونفيج تدعم ذلك.

---

# 22. استخراج المعلومات

لكل Config مكتشف، حاول استخراج:

```text
id
source_url
source_name
source_type
raw_config
normalized_config

protocol
transport
security
proxy
payload
dns_mode

server
port
username
password
uuid

host
sni
path
service_name
alpn
fingerprint

public_key
short_id
flow

encryption
method
plugin
obfs

country
region
asn
isp

created_at
updated_at
expires_at
last_seen

latency
jitter
packet_loss
download_speed
upload_speed

connection_success
handshake_success
protocol_valid
tls_valid

quality_score
reliability_score
freshness_score
```

---

# 23. Validation Engine

لا تعتبر الكونفيج صالحًا لمجرد أن صيغة النص صحيحة.

يجب إنشاء مراحل تحقق:

1. Syntax validation
2. URI parsing
3. Server/port validation
4. DNS resolution
5. TCP connectivity
6. UDP connectivity عند الحاجة
7. TLS handshake
8. Protocol handshake
9. Proxy connectivity
10. Tunnel connectivity
11. Latency test
12. Stability test
13. Optional throughput test

يجب تسجيل سبب الفشل، وليس فقط `invalid`.

أمثلة:

```text
INVALID_URI
INVALID_HOST
INVALID_PORT
DNS_FAILED
TCP_TIMEOUT
TCP_REFUSED
TLS_FAILED
TLS_CERT_ERROR
REALITY_HANDSHAKE_FAILED
PROTOCOL_HANDSHAKE_FAILED
AUTH_FAILED
PROXY_FAILED
TIMEOUT
EXPIRED
RATE_LIMITED
```

---

# 24. Expiration / Freshness

يجب أن يفرق البرنامج بين:

- Newly discovered
- Recently verified
- Active
- Stale
- Expired
- Unknown expiry

ويحسب:

```text
age
last_seen
last_verified
expires_at
remaining_time
freshness_score
```

إذا لم توجد معلومات صريحة عن تاريخ الانتهاء، لا تخترع تاريخًا.

يمكن تقدير freshness اعتمادًا على آخر ظهور وآخر نجاح، لكن يجب تسمية ذلك **estimated**.

---

# 25. Quality Scoring

أنشئ Quality Score من 0 إلى 100.

مثال مبدئي:

```text
Protocol capability       20
Connection success        20
Latency                   15
Stability / uptime        15
Freshness                 10
TLS / security            5
Throughput                10
Configuration validity    5
----------------------------
Total                    100
```

يجب أن تكون الأوزان قابلة للتعديل من إعدادات البرنامج.

لا تجعل البروتوكول وحده يحدد الدرجة.

مثلاً:

```text
VLESS Reality
```

ليس بالضرورة أفضل من:

```text
SSH TLS
```

إذا كان خادم VLESS بطيئًا أو غير مستقر.

---

# 26. Duplicate Detection

يجب إزالة التكرار على عدة مستويات:

### Exact duplicate

نفس النص تمامًا.

### Normalized duplicate

نفس الكونفيج بعد إزالة:

- whitespace
- formatting
- remarks غير المؤثرة
- ترتيب JSON fields

### Endpoint duplicate

نفس:

```text
server + port + protocol + relevant identity
```

لكن لا تعتبر endpoint متطابقًا دائمًا نفس الكونفيج إذا اختلفت بيانات المصادقة أو transport.

---

# 27. Source Crawling

يجب أن يستطيع ConfigCrawler جمع البيانات من مصادر متعددة:

- GitHub repositories
- GitHub raw files
- GitHub releases
- GitHub Gists
- Public websites
- Public config pages
- Public APIs
- Subscription URLs
- Public text files
- Public JSON/YAML endpoints
- RSS/feeds عندما تحتوي على configs
- صفحات HTML
- ملفات ZIP/TXT/JSON/YAML

يجب أن يكون لكل Source:

```text
source_id
source_url
source_type
last_scan
scan_status
configs_found
valid_configs
invalid_configs
new_configs
updated_configs
```

---

# 28. Search Engine

لا تعتمد على بحث واحد.

أنشئ Search Targets قابلة للتعديل.

أمثلة:

```text
"vless://"
"vmess://"
"trojan://"
"ss://"
"tuic://"
"hysteria"
"hysteria2"
"dnstt"
"slowdns"
"ssh payload"
"ssh tls"
"ssh websocket"
"wireguard config"
".json"
".yaml"
".yml"
".conf"
".txt"
```

ويجب أن يستطيع المستخدم إضافة Search Patterns جديدة من الواجهة.

---

# 29. Intelligent Extraction

يجب ألا يعتمد البرنامج على Regex واحد.

أنشئ Pipeline:

```text
SOURCE
  ↓
DOWNLOAD
  ↓
CONTENT TYPE DETECTION
  ↓
DECOMPRESSION
  ↓
DECODING
  ↓
URI DETECTION
  ↓
JSON/YAML PARSING
  ↓
PAYLOAD DETECTION
  ↓
PROTOCOL CLASSIFICATION
  ↓
NORMALIZATION
  ↓
DEDUPLICATION
  ↓
VALIDATION
  ↓
QUALITY SCORING
  ↓
DATABASE
```

---

# 30. Encoding Detection

يجب اكتشاف وفك الترميز الشائع عندما يكون آمنًا ومشروعًا:

- Base64
- URL encoding
- JSON escaping
- HTML entities
- gzip
- ZIP
- plain text

يجب وضع حدود للحجم والعمق لمنع recursive decoding غير المنضبط.

---

# 31. Database Model

يفضل تصميم قاعدة البيانات بحيث يكون:

```text
configs
sources
endpoints
protocols
transports
security_profiles
payloads
validation_results
speed_tests
countries
asns
scan_jobs
scan_results
subscriptions
tags
```

مع إمكانية إضافة protocol جديد دون migration معقدة قدر الإمكان.

---

# 32. GUI Requirements

واجهة ConfigCrawler يجب أن تعرض Live Dashboard.

المطلوب:

```text
Total Sources
Active Sources
Configs Found
New Configs
Valid Configs
Dead Configs
Expired Configs
Active Configs
Average Latency
Average Speed
Top Protocols
Top Countries
Top ISPs
```

ويجب وجود صفحات:

- Dashboard
- Sources
- Configs
- Live Scanner
- Validation
- Protocols
- Subscriptions
- Statistics
- Logs
- Settings

---

# 33. Config Table

جدول الكونفيجات يجب أن يعرض على الأقل:

```text
Status
Protocol
Transport
Security
Server
Port
Country
Latency
Speed
Uptime
Expiry
Last Verified
Quality
Source
```

مع Filters:

- Protocol
- Country
- Status
- Security
- Transport
- Latency
- Speed
- Expiry
- Quality
- Source
- Last Seen

---

# 34. Export

يجب دعم التصدير حسب البروتوكول أو التطبيق أو الصيغة.

أمثلة:

```text
VLESS URLs
VMess URLs
Trojan URLs
Shadowsocks URLs
Hysteria configs
TUIC configs
WireGuard configs
OpenVPN configs
SOCKS lists
HTTP proxy lists
SSH configs
Raw configs
JSON
YAML
TXT
CSV
```

ويجب إمكانية:

- Copy URL
- Copy selected
- Export selected
- Export by protocol
- Export by country
- Export by quality
- Export active only
- Export recently verified only

---

# 35. Application-oriented Classification

يجب أن يستطيع النظام تصنيف الكونفيج حسب التطبيقات/العائلات التي قد تستخدم الصيغة، بدون الادعاء بالتوافق إذا لم يتم التحقق منه.

أمثلة لفئات التطبيقات:

- HTTP Injector-style configs
- HA Tunnel-style configs
- HTTP Custom-style configs
- NapsternetV-style configs
- NetMod-style configs
- TLS Tunnel-style configs
- SSH Tunnel apps
- V2Ray/Xray clients
- Hysteria clients
- TUIC clients
- WireGuard clients
- OpenVPN clients

يجب أن تكون Application Compatibility نتيجة تحليل الصيغة، وليست مجرد تخمين مبني على اسم الملف.

---

# 36. Important Architecture Rule

لا تبنِ النظام هكذا:

```text
if extension == ".ehi":
    protocol = "SSH"
```

بل:

```text
File
 ↓
Format Detector
 ↓
Decoder
 ↓
Parser
 ↓
Protocol Detector
 ↓
Transport Detector
 ↓
Security Detector
 ↓
Payload Detector
 ↓
Normalizer
 ↓
Validator
```

لأن ملفًا واحدًا قد يحتوي على أكثر من طبقة.

---

# 37. Plugin Architecture

اجعل إضافة بروتوكول أو صيغة جديدة سهلة.

مثال منطقي:

```text
plugins/
  protocols/
    vless/
    vmess/
    trojan/
    shadowsocks/
    hysteria/
    tuic/
    ssh/
    wireguard/
    openvpn/

  formats/
    json/
    yaml/
    uri/
    base64/
    zip/
    txt/

  sources/
    github/
    websites/
    subscriptions/
    apis/
```

كل Plugin يحدد:

```text
name
aliases
detector
parser
normalizer
validator
exporters
```

---

# 38. أهم قاعدة

**لا تحصر البرنامج في القائمة الحالية.**

القائمة الحالية هي Seed Catalog فقط.

يجب أن يكون النظام قادرًا على:

1. اكتشاف بروتوكولات جديدة.
2. اكتشاف صيغ ملفات جديدة.
3. اكتشاف URI schemes جديدة.
4. اكتشاف transports جديدة.
5. اكتشاف طرق encoding جديدة.
6. إضافة parser جديد كـ plugin.
7. إضافة exporter جديد كـ plugin.
8. تحديث protocol metadata من دون إعادة بناء النظام بالكامل.

---

# 39. المطلوب من Big Pickle

قبل تعديل الكود:

1. اقرأ المشروع بالكامل.
2. افهم المعمارية الحالية.
3. حدد ما هو موجود بالفعل.
4. حدد ما هو ناقص.
5. لا تعيد كتابة أجزاء تعمل بالفعل.
6. لا تحذف features موجودة.
7. لا تغير الواجهة الحالية إلا لتحسينها.
8. أنشئ خطة تنفيذ مرحلية.
9. نفذ على مراحل صغيرة.
10. بعد كل مرحلة شغّل الاختبارات والتحقق.
11. لا تعتبر المهمة منتهية إلا بعد نجاح build/tests.
12. حافظ على backward compatibility مع configs الحالية.

## المطلوب النهائي

تحويل ConfigCrawler من:

```text
Simple Config Scraper
```

إلى:

```text
Multi-Protocol Config Discovery Engine
        +
Multi-Format Parser
        +
Decoder
        +
Normalizer
        +
Validator
        +
Deduplicator
        +
Quality Ranking Engine
        +
Live Dashboard
        +
Multi-Format Exporter
```

ويجب أن تكون كل المكونات قابلة للتوسعة مستقبلًا.
