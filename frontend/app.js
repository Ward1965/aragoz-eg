(function () {
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    let allConfigs = [];
    let totalConfigs = 0;
    let activeFilters = new Set();
    let activeCountries = new Set();
    let currentDetailRaw = "";
    let sortState = { key: "", dir: 1 };
    let progressTimer = null;
    let currentQrText = "";
    let loadJob = 0;
    let loadedOffset = 0;
    let loadingMore = false;
    let scrollTimer = null;
    let lastKnownCount = null;
    let liveRefreshTimer = null;
    let liveRefreshJob = 0;
    const PAGE_SIZE = 4000;
    const MAX_VISIBLE = 60000;
    let ROW_H = 0;
    let virt = { first: 0, last: 0 };
    let virtPending = null;
    const VIT_BUF = 400;

    function wrapScrollEl() {
        return document.querySelector(".table-wrapper") || document.documentElement;
    }

    function measureRowHeight() {
        const firstRow = document.querySelector("#configBody tr:not(.vit-spacer):not(.more-row)");
        if (!firstRow) return;
        const h = firstRow.offsetHeight;
        if (h > 1 && (ROW_H === 0 || Math.abs(h - ROW_H) > 1)) ROW_H = h;
        if (ROW_H === 0) ROW_H = 38;
    }

    function computeWindow() {
        const wrap = wrapScrollEl();
        const st = wrap.scrollTop || 0;
        const vh = wrap.clientHeight || 600;
        const total = allConfigs.length;
        if (total === 0) return { first: 0, last: 0 };
        let first = Math.max(0, Math.floor((st - VIT_BUF) / ROW_H));
        let last = Math.min(total, Math.ceil((st + vh + VIT_BUF) / ROW_H));
        return { first, last };
    }

    function requestVirtRender() {
        if (virtPending) return;
        virtPending = requestAnimationFrame(() => {
            virtPending = null;
            renderWindow(false);
        });
    }

    function renderWindow(force = true) {
        const tbody = document.querySelector("#configBody");
        if (!tbody) return;
        measureRowHeight();
        const w = computeWindow();
        if (!force && w.first === virt.first && w.last === virt.last) return;
        virt = w;
        const topH = w.first * ROW_H;
        const bottomH = (allConfigs.length - w.last) * ROW_H;
        const spacerTop = topH > 0 ? `<tr class="vit-spacer"><td colspan="8" style="height:${topH}px"></td></tr>` : "";
        const spacerBottom = bottomH > 0 ? `<tr class="vit-spacer"><td colspan="8" style="height:${bottomH}px"></td></tr>` : "";
        const rowsHtml = buildRowsHtml(allConfigs.slice(w.first, w.last), w.first);
        let moreHtml = "";
        if (allConfigs.length < totalConfigs) {
            moreHtml = `<tr class="more-row"><td colspan="8">${
                allConfigs.length >= MAX_VISIBLE
                    ? `Showing first ${allConfigs.length.toLocaleString()} rows — max reached`
                    : `<button class="btn btn-secondary btn-sm" id="loadMoreBtn">Load more (${(totalConfigs - allConfigs.length).toLocaleString()} remaining)</button>`
            }</td></tr>`;
        }
        tbody.innerHTML = spacerTop + rowsHtml + spacerBottom + moreHtml;
    }

    const api = () => window.pywebview.api;

    function waitForApi(cb, retries = 50) {
        if (window.pywebview && window.pywebview.api) {
            cb();
        } else if (retries > 0) {
            setTimeout(() => waitForApi(cb, retries - 1), 100);
        }
    }

    function toast(msg, type = "info") {
        const el = document.createElement("div");
        el.className = "toast toast-" + type;
        el.textContent = msg;
        $("#toast-container").appendChild(el);
        setTimeout(() => el.remove(), 3500);
    }

    async function loadConfigs(reset = true, silent = false, opts = {}) {
        const job = ++loadJob;
        if (reset) {
            allConfigs = [];
            loadedOffset = 0;
            if (!opts.keepScroll) wrapScrollEl().scrollTop = 0;
        }
        try {
            const query = ($("#searchInput").value || "").trim();
            const res = JSON.parse(
                await api().get_configs(
                    query,
                    JSON.stringify({ protocols: [...activeFilters], countries: [...activeCountries] }),
                    sortState.key,
                    sortState.dir,
                    loadedOffset,
                    PAGE_SIZE
                )
            );
            if (job !== loadJob) return allConfigs.length;
            allConfigs = allConfigs.concat(res.configs || []);
            totalConfigs = res.total || 0;
            loadedOffset = allConfigs.length;
            if (!silent) renderTable();
            return allConfigs.length;
        } catch (e) {
            toast("Failed to load configs", "error");
            return allConfigs.length;
        }
    }

    async function ensureLoaded(maxRows) {
        const target = Math.min(totalConfigs, maxRows);
        let guard = 0;
        while (allConfigs.length < target && guard++ < 50) {
            const silent = allConfigs.length + PAGE_SIZE < target;
            await loadConfigs(false, silent);
        }
        renderTable();
    }

    function maybeLoadMore() {
        if (loadingMore) return;
        if (allConfigs.length >= totalConfigs) return;
        if (allConfigs.length >= MAX_VISIBLE) return;
        const wrap = wrapScrollEl();
        if (wrap.scrollTop + wrap.clientHeight >= allConfigs.length * ROW_H - 900) {
            loadingMore = true;
            loadConfigs(false).finally(() => {
                loadingMore = false;
            });
        }
    }

    function formatExpiry(e) {
        if (!e) return { text: "—", cls: "", title: "No expiry info" };
        const d = new Date(e.slice(0, 10) + "T00:00:00");
        if (isNaN(d.getTime())) return { text: "—", cls: "", title: e };
        const now = new Date();
        const days = Math.floor((d.getTime() - now.getTime()) / 86400000);
        if (days < 0) return { text: "Expired", cls: "exp-out", title: e };
        if (days === 0) return { text: "Today", cls: "exp-near", title: e };
        if (days === 1) return { text: "1 day", cls: "exp-near", title: e };
        if (days <= 7) return { text: days + " days", cls: "exp-near", title: e };
        return { text: days + " days", cls: "exp-ok", title: e };
    }

    function buildRowsHtml(configs, baseIndex = 0) {
        return configs
            .map((c, i) => {
                return `
                <tr data-id="${c.id}">
                    <td class="row-number">${baseIndex + i + 1}</td>
                    <td title="${esc(c.name)}">${esc(c.name)}</td>
                    <td><span class="protocol-badge" style="background:${c.color}">${esc(c.protocol)}</span></td>
                    <td title="${esc(c.server)}">${esc(c.server)}</td>
                    <td>${c.port}</td>
                    <td title="${esc(c.country || '')}">${flagMarkup(c.country)}${esc(c.country || '—')}</td>
                    <td>
                        <div class="actions-cell">
                            <button class="btn btn-sm btn-secondary copy-btn" data-id="${c.id}" title="Copy">Copy</button>
                            <button class="btn btn-sm btn-secondary qr-btn" data-id="${c.id}" title="Show QR">QR</button>
                            <button class="btn btn-sm btn-secondary detail-btn" data-id="${c.id}" title="Details">Details</button>
                            <button class="btn btn-sm btn-danger delete-btn" data-id="${c.id}" title="Delete">Delete</button>
                        </div>` + `
                    </td>
                </tr>`
            })
            .join("");
    }

    function renderTable() {
        const tbody = $("#configBody");
        const table = $("#configTable");
        const emptyState = $("#emptyState");

        if (totalConfigs === 0) {
            $("#configCount").textContent = "0 configs";
            table.style.display = "none";
            emptyState.style.display = "block";
            tbody.innerHTML = "";
            return;
        }
        emptyState.style.display = "none";
        table.style.display = "table";

        $("#configCount").textContent =
            allConfigs.length >= totalConfigs
                ? totalConfigs.toLocaleString() + " configs"
                : allConfigs.length.toLocaleString() + " of " + totalConfigs.toLocaleString() + " configs";

        if (allConfigs.length === 0 && totalConfigs > 0) {
            tbody.innerHTML = `
                <tr><td colspan="8">
                    <div class="empty-state">
                        <h3>No matching configs</h3>
                        <p>Try clearing your search or filters</p>
                    </div>
                </td></tr>`;
            return;
        }
        renderWindow(true);
    }

    function copyConfig(id) {
        api()
            .get_raw(id)
            .then((r) => {
                try {
                    const data = JSON.parse(r);
                    if (!data.raw) {
                        toast("Raw content unavailable", "error");
                        return;
                    }
                    return navigator.clipboard.writeText(data.raw).then(() => toast("Copied", "success"));
                } catch (e) {
                    toast("Copy failed", "error");
                }
            })
            .catch(() => toast("Copy failed", "error"));
    }

    async function renderFilters() {
        const container = $("#protocolFilters");
        let counts = [];
        try {
            counts = JSON.parse(await api().get_protocol_counts());
        } catch (e) {
            return;
        }

        if (!counts.length) {
            container.innerHTML = '<div style="font-size:13px;color:var(--text-muted);padding:4px 8px">No configs loaded</div>';
        } else {
            const allActive = activeFilters.size === 0 ? " active" : "";
            container.innerHTML =
                `<div class="filter-item${allActive}" data-type="__all__">
                    <span><span class="filter-dot" style="background:#8b5cf6"></span>All Protocols</span>
                    <span class="filter-count">${totalConfigs}</span>
                </div>` +
                counts
                    .map((t) => {
                        const active = activeFilters.has(t.type) ? " active" : "";
                        return `
                    <div class="filter-item${active}" data-type="${escAttr(t.type)}">
                        <span><span class="filter-dot" style="background:${t.color}"></span>${esc(t.type)}</span>
                        <span class="filter-count">${t.count}</span>
                    </div>`;
                    })
                    .join("");
        }

        const countryBox = $("#countryFilters");
        let countries = [];
        try {
            countries = JSON.parse(await api().get_country_counts());
        } catch (e) {
            return;
        }
        if (!countries.length) {
            countryBox.innerHTML = '<div style="font-size:13px;color:var(--text-muted);padding:4px 8px">No country data</div>';
            return;
        }
        const allCountryActive = activeCountries.size === 0 ? " active" : "";
        countryBox.innerHTML =
            `<div class="filter-item${allCountryActive}" data-country="__all__">
                <span><span class="filter-dot" style="background:#10b981"></span>All Countries</span>
                <span class="filter-count">${totalConfigs}</span>
            </div>` +
            countries
                .map((c) => {
                    const val = c.country === "(unknown)" ? "" : c.country;
                    const active = activeCountries.has(val) ? " active" : "";
                    return `
                <div class="filter-item${active}" data-country="${escAttr(val)}">
                    <span><span class="filter-dot" style="background:#f59e0b"></span>${flagMarkup(c.country)} ${esc(c.country)}</span>
                    <span class="filter-count">${c.count}</span>
                </div>`;
                })
                .join("");
    }

    function renderHeaderState() {
        $$("th.sortable").forEach((th) => {
            const key = th.dataset.key;
            const ind = th.querySelector(".sort-indicator");
            if (sortState.key === key) {
                th.classList.add("active");
                ind.textContent = sortState.dir === 1 ? "▲" : "▼";
            } else {
                th.classList.remove("active");
                ind.textContent = "";
            }
        });
    }

    function toggleSort(key) {
        if (sortState.key === key) {
            sortState.dir = sortState.dir === 1 ? -1 : 1;
        } else {
            sortState.key = key;
            sortState.dir = 1;
        }
        renderHeaderState();
        loadConfigs(true);
    }

    function showProgress(label) {
        $("#progressText").textContent = label;
        $("#progressBar").style.width = "0%";
        $("#progressCount").textContent = "0 configs";
        $("#progressOverlay").style.display = "flex";
        stopProgressPolling();
        progressTimer = setInterval(pollProgress, 600);
    }

    function stopProgressPolling() {
        if (progressTimer) {
            clearInterval(progressTimer);
            progressTimer = null;
        }
    }

    function scheduleLiveRefresh() {
        if (liveRefreshTimer) return;
        liveRefreshTimer = setTimeout(() => {
            liveRefreshTimer = null;
            const job = ++liveRefreshJob;
            loadConfigs(true, false, { keepScroll: true }).then(() => {
                if (job === liveRefreshJob) renderFilters();
            });
        }, 800);
    }

    function hideProgress() {
        stopProgressPolling();
        $("#progressOverlay").style.display = "none";
    }

    async function pollProgress() {
        try {
            const p = JSON.parse(await api().get_progress());
            const phase = p.phase || "idle";
            let label = p.detail || "Working...";
            let pct = 0;
            if (phase === "discovering") {
                label = "Scanning the web... " + (p.detail || "");
                pct = p.total ? Math.round((p.current / p.total) * 100) : 0;
            } else if (phase === "fetching") {
                label = `Fetching sources (${p.current}/${p.total})...`;
                pct = p.total ? Math.round((p.current / p.total) * 100) : 0;
            } else if (phase === "telegram") {
                label = "Scanning Telegram channels... " + (p.detail || "");
                pct = p.total ? Math.round((p.current / p.total) * 100) : 0;
            } else if (phase === "importing") {
                label = p.detail || "Importing...";
                pct = p.total ? Math.round((p.current / p.total) * 100) : 0;
            } else if (phase === "done") {
                label = "Done";
                pct = 100;
            }
            $("#progressText").textContent = label;
            $("#progressBar").style.width = pct + "%";
            const count = typeof p.count === "number" ? p.count : null;
            if (count !== null) {
                $("#progressCount").textContent = count.toLocaleString() + " configs written";
            }
            if (count !== null && phase !== "done" && phase !== "idle") {
                if (lastKnownCount === null) {
                    lastKnownCount = count;
                } else if (count !== lastKnownCount) {
                    lastKnownCount = count;
                    scheduleLiveRefresh();
                }
            }
        } catch (e) { /* ignore transient errors */ }
    }

    async function showQr(id) {
        try {
            const res = JSON.parse(await api().get_qr(id));
            if (res.error) {
                toast(res.error, "error");
                return;
            }
            currentQrText = res.text || "";
            $("#qrContainer").innerHTML = res.svg;
            const short = currentQrText.length > 120
                ? currentQrText.slice(0, 120) + "..."
                : currentQrText;
            $("#qrText").textContent = short;
            $("#qrModal").style.display = "flex";
        } catch (e) {
            toast("QR failed: " + e.message, "error");
        }
    }

    function esc(s) {
        const d = document.createElement("div");
        d.textContent = s || "";
        return d.innerHTML;
    }

    function escAttr(s) {
        return (s || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    const COUNTRY_FLAGS = {
        "United States": "US", "US": "US", "USA": "US", "U.S.A": "US",
        "Iran": "IR", "Iran, Islamic Republic of": "IR",
        "Germany": "DE", "France": "FR", "Netherlands": "NL",
        "United Kingdom": "GB", "Britain": "GB", "UK": "GB",
        "Canada": "CA", "Turkey": "TR", "Türkiye": "TR", "Belarus": "BY",
        "Russia": "RU", "Ukraine": "UA", "Poland": "PL", "Czech": "CZ",
        "Czechia": "CZ", "Slovakia": "SK", "Sweden": "SE", "Finland": "FI",
        "Norway": "NO", "Denmark": "DK", "Iceland": "IS", "Switzerland": "CH",
        "Austria": "AT", "Belgium": "BE", "Luxembourg": "LU", "Ireland": "IE",
        "Spain": "ES", "Portugal": "PT", "Italy": "IT", "Greece": "GR",
        "Bulgaria": "BG", "Romania": "RO", "Hungary": "HU", "Croatia": "HR",
        "Serbia": "RS", "Lithuania": "LT", "Latvia": "LV", "Estonia": "EE",
        "Moldova": "MD", "Georgia": "GE", "Armenia": "AM", "Azerbaijan": "AZ",
        "Kazakhstan": "KZ", "Uzbekistan": "UZ", "Japan": "JP",
        "South Korea": "KR", "Korea": "KR", "Korea, Republic of": "KR",
        "Singapore": "SG", "Hong Kong": "HK", "Hongkong": "HK", "China": "CN",
        "Taiwan": "TW", "Taiwan, Province of China": "TW", "India": "IN",
        "Pakistan": "PK", "Malaysia": "MY", "Indonesia": "ID", "Thailand": "TH",
        "Vietnam": "VN", "Philippines": "PH", "Bangladesh": "BD",
        "Sri Lanka": "LK", "Nepal": "NP", "Australia": "AU", "New Zealand": "NZ",
        "Brazil": "BR", "Argentina": "AR", "Mexico": "MX", "Chile": "CL",
        "Colombia": "CO", "Peru": "PE", "South Africa": "ZA", "Egypt": "EG",
        "Morocco": "MA", "Algeria": "DZ", "Tunisia": "TN", "Saudi Arabia": "SA",
        "UAE": "AE", "United Arab Emirates": "AE", "Qatar": "QA", "Kuwait": "KW",
        "Israel": "IL", "Jordan": "JO", "Lebanon": "LB", "Iraq": "IQ",
        "Slovenia": "SI", "North Macedonia": "MK", "Albania": "AL",
    };

    function flagMarkup(name) {
        if (!name) return "";
        const parts = String(name).split(/[,;-]/)[0].trim();
        const code = COUNTRY_FLAGS[name] || COUNTRY_FLAGS[parts] || COUNTRY_FLAGS[name.replace(/\s+/g, "")];
        if (!code) return "";
        const lower = code.toLowerCase();
        return '<span class="flag-emoji"><img src="https://flagcdn.com/w40/' + lower + '.png" alt="' + escAttr(code.toUpperCase()) + '" loading="lazy" width="20" height="14" onerror="this.style.display=\'none\'"></span>';
    }

    async function handleFetch() {
        const raw = ($("#urlInput").value || "").trim();
        const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
        const isUrl = (l) => /^https?:\/\/\S+/i.test(l);

        if (lines.length === 0) {
            showProgress("Scanning the web for sources...");
            lastKnownCount = null;
            totalConfigs = 0;
            allConfigs = [];
            renderTable();
            renderFilters();
            try {
                const res = JSON.parse(await api().fetch_sources(""));
                applyFetchResult(res);
            } catch (e) {
                hideProgress();
                toast("Scan failed: " + e.message, "error");
            }
            return;
        }

        const invalid = lines.filter((l) => !isUrl(l));
        if (invalid.length > 0) {
            const shown = invalid.slice(0, 3)
                .map((l) => `"${l.length > 40 ? l.slice(0, 40) + "…" : l}"`)
                .join(", ");
            const more = invalid.length > 3 ? ` (+${invalid.length - 3} more)` : "";
            toast(`Skipped ${invalid.length} invalid line(s) — only http/https subscription URLs allowed: ${shown}${more}`, "error");
            $("#urlInput").focus();
        }

        const valid = lines.filter(isUrl);
        if (valid.length === 0) {
            toast("No valid subscription URLs found. Enter http/https links only, one per line.", "error");
            return;
        }

        showProgress("Fetching sources...");
        lastKnownCount = null;
        totalConfigs = 0;
        allConfigs = [];
        renderTable();
        renderFilters();
        try {
            const res = JSON.parse(await api().fetch_sources(valid.join("\n")));
            applyFetchResult(res);
        } catch (e) {
            hideProgress();
            toast("Fetch failed: " + e.message, "error");
        }
    }

    async function handleFetchTelegram() {
        const raw = ($("#urlInput").value || "").trim();
        const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
        const isTg = (l) => /t\.me\//i.test(l) || /^@[A-Za-z0-9_]+$/i.test(l);
        const tg = lines.filter(isTg);

        if (lines.length > 0 && tg.length === 0) {
            toast("Telegram channels not found in Sources. Enter channel links like @name or t.me/s/name — or leave empty to use the 157 built-in channels.", "error");
            return;
        }

        showProgress(tg.length ? `Scanning Telegram: ${tg.length} channel(s)...` : "Scanning 157 Telegram channels...");
        lastKnownCount = null;
        totalConfigs = 0;
        allConfigs = [];
        renderTable();
        renderFilters();
        try {
            const res = JSON.parse(await api().fetch_telegram(tg.join("\n")));
            applyFetchResult(res);
        } catch (e) {
            hideProgress();
            toast("Telegram fetch failed: " + e.message, "error");
        }
    }

    async function handleScanWeb() {
        showProgress("Scanning the web for sources...");
        lastKnownCount = null;
        totalConfigs = 0;
        allConfigs = [];
        renderTable();
        renderFilters();
        try {
            const res = JSON.parse(await api().fetch_sources(""));
            applyFetchResult(res);
        } catch (e) {
            hideProgress();
            toast("Scan failed: " + e.message, "error");
        }
    }

    async function applyFetchResult(res) {
        hideProgress();
        lastKnownCount = res.total || 0;
        if (liveRefreshTimer) {
            clearTimeout(liveRefreshTimer);
            liveRefreshTimer = null;
        }
        if (res.discovered && res.discovered.length > 0) {
            showDiscovered(res.discovered);
        }
        await loadConfigs(true);
        await ensureLoaded(MAX_VISIBLE);
        renderFilters();
        if (res.cancelled) {
            toast(`Scan cancelled — ${res.total} configs loaded so far`, "info");
        } else if ((res.added || 0) > 0) {
            toast(`Added ${res.added} new config — ${res.total} total`, "success");
        } else if (res.total > 0) {
            toast(`No new configs — everything was already saved (${res.total} total)`, "info");
        }
    }

    function showDiscovered(urls) {
        const box = $("#discoveredBox");
        const list = $("#discoveredList");
        box.style.display = "block";
        list.innerHTML = urls
            .map((u) => `<div class="discovered-item" data-url="${escAttr(u)}">${esc(u)}</div>`)
            .join("");
        $("#discoveredBox").dataset.count = urls.length;
    }

    async function handleImportFile() {
        try {
            showProgress("Importing file...");
            const res = JSON.parse(await api().import_from_file(""));
            hideProgress();
            if (res.cancelled) return;
            if (res.error) {
                toast(res.error, "error");
                return;
            }
            if (res.errors && res.errors.length > 0) {
                res.errors.forEach((e) => toast(e, "error"));
            }
            await loadConfigs(true);
            await ensureLoaded(MAX_VISIBLE);
            renderFilters();
            toast(`Loaded ${res.total} configs from file`, "success");
        } catch (e) {
            hideProgress();
            toast("Import failed", "error");
        }
    }

    async function handleRawImport() {
        const text = $("#rawTextInput").value.trim();
        if (!text) {
            toast("Paste some configs first", "error");
            return;
        }
        toast("Parsing...", "info");
        try {
            const res = JSON.parse(await api().import_raw_text(text));
            $("#rawTextInput").value = "";
            $("#rawTextInput").style.display = "none";
            $("#rawSubmitRow").style.display = "none";
            await loadConfigs(true);
            await ensureLoaded(MAX_VISIBLE);
            renderFilters();
            toast(`Loaded ${res.total} configs`, "success");
        } catch (e) {
            toast("Parse failed", "error");
        }
    }

    function currentFilterArgs() {
        const query = ($("#searchInput").value || "").trim();
        const filters = JSON.stringify({ protocols: [...activeFilters], countries: [...activeCountries] });
        return { query, filters, filtered: !!(query || activeFilters.size > 0 || activeCountries.size > 0) };
    }

    async function handleCopyText() {
        try {
            const { query, filters, filtered } = currentFilterArgs();
            const text = await api().export_text(query, filters);
            if (!text) {
                toast("No configs to copy", "error");
                return;
            }
            await navigator.clipboard.writeText(text);
            toast(filtered ? "Copied filtered configs as text" : "Copied all configs as text", "success");
        } catch (e) {
            toast("Copy failed", "error");
        }
    }

    async function handleCopyB64() {
        try {
            const { query, filters, filtered } = currentFilterArgs();
            const b64 = await api().export_base64(query, filters);
            if (!b64) {
                toast("No configs to copy", "error");
                return;
            }
            await navigator.clipboard.writeText(b64);
            toast(filtered ? "Copied filtered Base64 subscription" : "Copied Base64 subscription to clipboard", "success");
        } catch (e) {
            toast("Copy failed", "error");
        }
    }

    async function handleExportFile(filetype) {
        try {
            const { query, filters, filtered } = currentFilterArgs();
            const res = JSON.parse(await api().export_file(filetype, query, filters));
            if (res.cancelled) return;
            if (res.error) {
                toast(res.error, "error");
                return;
            }
            toast((filtered ? "Saved filtered configs to: " : "Saved: ") + res.path, "success");
        } catch (e) {
            toast("Export failed", "error");
        }
    }

    async function handleClearAll() {
        if (!confirm("Clear all saved configs?")) return;
        try {
            await api().clear_all();
            totalConfigs = 0;
            allConfigs = [];
            renderTable();
            renderFilters();
            toast("All configs cleared", "success");
        } catch (e) {
            toast("Clear failed", "error");
        }
    }

    async function showDetail(id) {
        try {
            const res = JSON.parse(await api().get_config_detail(id));
            if (res.error) {
                toast(res.error, "error");
                return;
            }
            currentDetailRaw = res.raw || "";
            $("#modalTitle").textContent = res.name || "Config Details";
            const body = $("#modalBody");
            const LABELS = {
                protocol: "Protocol",
                protocol_type: "Protocol Type",
                name: "Name",
                server: "Server",
                port: "Port",
                uuid: "UUID",
                password: "Password",
                cipher: "Cipher",
                security: "Security",
                sni: "SNI",
                network: "Network",
                flow: "Flow",
                host: "Host",
                path: "Path",
                alpn: "ALPN",
                fingerprint: "Fingerprint",
                public_key: "Public Key",
                short_id: "Short ID",
                alter_id: "Alter ID",
                tls: "TLS",
                expires_at: "Remaining",
                country: "Country",
                created_at: "Created",
            };
            const skip = ["id", "name", "raw", "created_at"];
            body.innerHTML = Object.keys(res)
                .filter((k) => !skip.includes(k))
                .map((k) => {
                    let val = typeof res[k] === "boolean" ? (res[k] ? "Yes" : "No") : (res[k] || "-");
                    if (k === "expires_at" && val !== "-") {
                        const exp = formatExpiry(val);
                        val = `${exp.text} (until ${val})`;
                    }
                    const label = LABELS[k] || (k.charAt(0).toUpperCase() + k.slice(1));
                    return `
                    <div class="detail-row">
                        <div class="detail-label">${esc(label)}</div>
                        <div class="detail-value">${esc(String(val))}</div>
                    </div>`;
                })
                .join("");
            body.innerHTML += `
                <div class="detail-row" style="margin-top:12px">
                    <div class="detail-label">Raw URI</div>
                    <div class="detail-value" style="font-size:11px;color:var(--text-muted)">${esc(currentDetailRaw)}</div>
                </div>`;
            $("#detailModal").style.display = "flex";
        } catch (e) {
            toast("Failed to load details", "error");
        }
    }

    async function handleDelete(id) {
        if (!confirm("Delete this config?")) return;
        try {
            await api().delete_config(id);
            toast("Deleted", "success");
            await loadConfigs(true);
            renderFilters();
        } catch (e) {
            toast("Delete failed", "error");
        }
    }

    function initEvents() {
        const fetchBtn = $("#fetchBtn");
        const urlInput = $("#urlInput");
        function updateFetchBtn() {
            fetchBtn.disabled = !(urlInput.value || "").trim();
        }
        urlInput.addEventListener("input", updateFetchBtn);
        updateFetchBtn();

        $("#fetchBtn").addEventListener("click", handleFetch);
        $("#scanWebBtn").addEventListener("click", handleScanWeb);
        $("#tgFetchBtn").addEventListener("click", handleFetchTelegram);
        $("#importFileBtn").addEventListener("click", handleImportFile);
        $("#importRawBtn").addEventListener("click", () => {
            const ta = $("#rawTextInput");
            const row = $("#rawSubmitRow");
            const vis = ta.style.display === "none";
            ta.style.display = vis ? "block" : "none";
            row.style.display = vis ? "block" : "none";
        });
        $("#rawSubmitBtn").addEventListener("click", handleRawImport);
        $("#exportTextBtn").addEventListener("click", handleCopyText);
        $("#exportB64Btn").addEventListener("click", handleCopyB64);
        $("#exportFileBtn").addEventListener("click", () => handleExportFile($("#exportFormat").value));
        $("#clearAllBtn").addEventListener("click", handleClearAll);
        let searchTimer = null;
        $("#searchInput").addEventListener("input", () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => loadConfigs(true), 250);
        });
        $("#clearSearchBtn").addEventListener("click", () => {
            $("#searchInput").value = "";
            loadConfigs(true);
            $("#searchInput").focus();
        });
        $("#cancelScanBtn").addEventListener("click", handleCancelScan);
        $("#topBtn").addEventListener("click", jumpTop);
        $("#bottomBtn").addEventListener("click", jumpBottom);
        $("#modalClose").addEventListener("click", () => {
            $("#detailModal").style.display = "none";
        });
        $("#detailModal").addEventListener("click", (e) => {
            if (e.target === $("#detailModal")) {
                $("#detailModal").style.display = "none";
            }
        });
        $("#modalCopyRaw").addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(currentDetailRaw);
                toast("Raw URI copied", "success");
            } catch (e) {
                toast("Copy failed", "error");
            }
        });

        $("#configTable").querySelector("thead").addEventListener("click", (e) => {
            const th = e.target.closest("th.sortable");
            if (!th) return;
            toggleSort(th.dataset.key);
        });

        $("#qrClose").addEventListener("click", () => {
            $("#qrModal").style.display = "none";
        });
        $("#qrModal").addEventListener("click", (e) => {
            if (e.target === $("#qrModal")) {
                $("#qrModal").style.display = "none";
            }
        });
        $("#qrCopyBtn").addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(currentQrText);
                toast("Link copied", "success");
            } catch (e) {
                toast("Copy failed", "error");
            }
        });

        $("#configBody").addEventListener("click", (e) => {
            const loadMore = e.target.closest("#loadMoreBtn");
            if (loadMore) {
                loadMore.disabled = true;
                loadConfigs(false);
                return;
            }
            const copyBtn = e.target.closest(".copy-btn");
            if (copyBtn) {
                copyConfig(parseInt(copyBtn.dataset.id));
                return;
            }
            const qrBtn = e.target.closest(".qr-btn");
            if (qrBtn) {
                showQr(parseInt(qrBtn.dataset.id));
                return;
            }
            const detailBtn = e.target.closest(".detail-btn");
            if (detailBtn) {
                showDetail(parseInt(detailBtn.dataset.id));
                return;
            }
            const deleteBtn = e.target.closest(".delete-btn");
            if (deleteBtn) {
                handleDelete(parseInt(deleteBtn.dataset.id));
                return;
            }
        });

        $("#protocolFilters").addEventListener("click", (e) => {
            const item = e.target.closest(".filter-item");
            if (!item) return;
            const type = item.dataset.type;
            if (type === "__all__") {
                activeFilters.clear();
            } else {
                if (activeFilters.has(type)) {
                    activeFilters.delete(type);
                } else {
                    activeFilters.add(type);
                }
            }
            loadConfigs(true);
            renderFilters();
        });

        $("#countryFilters").addEventListener("click", (e) => {
            const item = e.target.closest(".filter-item");
            if (!item) return;
            const country = item.dataset.country;
            if (country === "__all__") {
                activeCountries.clear();
            } else {
                if (activeCountries.has(country)) {
                    activeCountries.delete(country);
                } else {
                    activeCountries.add(country);
                }
            }
            loadConfigs(true);
            renderFilters();
        });

        $("#themeToggle").addEventListener("click", () => {
            document.body.classList.toggle("dark");
            const isDark = document.body.classList.contains("dark");
            $("#themeToggle").textContent = isDark ? "☀" : "☾";
        });

        $("#welcomeClose").addEventListener("click", closeWelcome);

        $("#aboutBtn").addEventListener("click", openWelcome);

        const wrap = document.querySelector(".table-wrapper");
        if (wrap) {
            wrap.addEventListener("scroll", () => {
                requestVirtRender();
                if (!scrollTimer) {
                    scrollTimer = setTimeout(() => {
                        scrollTimer = null;
                        maybeLoadMore();
                    }, 150);
                }
            }, { passive: true });
        }

        window.addEventListener("resize", () => requestVirtRender());

        $("#discoveredList").addEventListener("click", (e) => {
            const item = e.target.closest(".discovered-item");
            if (!item) return;
            const url = item.dataset.url;
            const box = $("#urlInput");
            box.value = box.value ? box.value + "\n" + url : url;
            box.dispatchEvent(new Event("input", { bubbles: true }));
            toast("Source added to URL list", "success");
        });

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && $("#progressOverlay").style.display === "flex") {
                e.preventDefault();
                handleCancelScan();
            }
        });
    }

    function jumpTop() {
        wrapScrollEl().scrollTop = 0;
        requestVirtRender();
    }

    async function jumpBottom() {
        if (allConfigs.length < totalConfigs) {
            await ensureLoaded(MAX_VISIBLE);
            if (allConfigs.length < totalConfigs) {
                toast("Max visible rows reached — showing first " + allConfigs.length.toLocaleString() + " rows", "info");
            }
        }
        wrapScrollEl().scrollTop = allConfigs.length * ROW_H;
        renderWindow(true);
    }

    function handleCancelScan() {
        $("#progressText").textContent = "Cancelling...";
        api()
            .cancel()
            .catch(() => {});
    }

    function openWelcome() {
        const ov = $("#welcomeOverlay");
        ov.style.display = "flex";
        ov.classList.add("visible");
    }

    function closeWelcome() {
        const ov = $("#welcomeOverlay");
        ov.classList.remove("visible");
        setTimeout(() => (ov.style.display = "none"), 260);
    }

    function showWelcome() {
        api()
            .get_app_logo()
            .then((res) => {
                const data = JSON.parse(res);
                if (data && data.data) {
                    $("#welcomeLogo").src = `data:${data.mime || "image/png"};base64,${data.data}`;
                }
                openWelcome();
            })
            .catch(() => openWelcome());
    }

    waitForApi(() => {
        initEvents();
        showWelcome();
        loadConfigs();
        renderFilters();
    });
})();