(function () {
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    let allConfigs = [];
    let totalConfigs = 0;
    let activeFilters = new Set();
    let activeCountries = new Set();
    let activePingFilters = new Set();
    let pingStats = null;
    let displayConfigs = [];
    let pendingFilterRender = null;
    let filterMsgShown = false;
    let currentDetailRaw = "";
    let sortState = { key: "", dir: 1 };
    let progressTimer = null;
    let currentQrText = "";
    let loadJob = 0;
    let searchGen = 0;
    let loadedOffset = 0;
    let currentPage = 0;
    let loadingMore = false;
    let navLoading = false;
    let navInFlight = false;
    let navPending = null;
    let pageCache = new Map();
    let cacheCtx = null;
    let prefetchJob = 0;
    let fetchInFlight = 0;
    let selectedRowIndex = 0;
    let rowSelectionActive = false;
    let scrollTimer = null;
    let lastKnownCount = null;
    let livePingRefresh = false;
    let liveRefreshTimer = null;
    let liveRefreshJob = 0;
    let progressStartTime = 0;
    const latencyResults = new Map();
    let pingAllRunning = false;
    let pingAllCancelled = false;
    let currentTask = null;
    let pendingTaskWork = null;
    let searchStateActive = false;
    let busyOperation = "";
    function showBusy(msg) {
        busyOperation = msg;
        const ov = document.getElementById("busyOverlay");
        const tx = document.getElementById("busyText");
        if (ov) ov.style.display = "flex";
        if (tx) tx.textContent = msg;
    }
    function hideBusy() {
        busyOperation = "";
        const ov = document.getElementById("busyOverlay");
        if (ov) ov.style.display = "none";
    }
    let searchStartTime = 0;
    let searchTimerId = null;
    let PAGE_SIZE = 20;

    function recalcPageSize() {
        const wrapper = document.querySelector(".table-wrapper");
        const visH = wrapper ? wrapper.clientHeight : window.innerHeight;
        let rowH = 0;
        try { rowH = document.querySelector("#configBody tr").offsetHeight; } catch (e) {}
        if (!rowH || rowH < 10) rowH = 41;
        PAGE_SIZE = Math.max(10, Math.floor(visH / rowH));
    }

    function wrapScrollEl() {
        return document.querySelector(".table-wrapper") || document.documentElement;
    }




    function pageCount() {
        return Math.max(1, Math.ceil(totalConfigs / PAGE_SIZE));
    }

    function updateConfigCounter() {
        const el = $("#configCount");
        if (!el) return;
        if (totalConfigs === 0) {
            el.textContent = "0 configs";
            return;
        }
        const overlay = $("#progressOverlay");
        if (overlay && overlay.style.display === "flex") {
            el.textContent = totalConfigs.toLocaleString() + " configs";
            return;
        }
        const start = Math.min(totalConfigs, currentPage * PAGE_SIZE + 1);
        const end = Math.min(totalConfigs, (currentPage + 1) * PAGE_SIZE);
        el.textContent = start.toLocaleString() + "-" + end.toLocaleString() + " of " + totalConfigs.toLocaleString() + " configs";
    }

    function updatePagination() {
        const first = $("#firstPageBtn");
        const prev = $("#prevPageBtn");
        const next = $("#nextPageBtn");
        const last = $("#lastPageBtn");
        const ind = $("#pageIndicator");
        if (!prev || !next || !ind) return;
        const pc = pageCount();
        currentPage = Math.max(0, Math.min(currentPage, pc - 1));
        if (first) first.disabled = currentPage <= 0;
        prev.disabled = currentPage <= 0;
        if (last) last.disabled = currentPage >= pc - 1;
        next.disabled = currentPage >= pc - 1;
        ind.textContent = "Page " + (currentPage + 1) + " / " + pc;
    }

    function currentCtxKey() {
        const q = ($("#searchInput").value || "").trim();
        return (q + "|" + sortState.key + "|" + sortState.dir +
            "|" + JSON.stringify([...activeFilters]) +
            "|" + JSON.stringify([...activeCountries]) +
            "|" + [...activePingFilters].sort().join(","));
    }

    function trimPageCache() {
        while (pageCache.size > 24) {
            const keys = [...pageCache.keys()];
            const pc = pageCount();
            const guards = new Set([0, 1, Math.max(0, pc - 1), Math.max(0, pc - 2)]);
            let evict = null;
            let bestDist = -1;
            for (const k of keys) {
                if (guards.has(k)) continue;
                const d = Math.abs(k - currentPage);
                if (d > bestDist) {
                    bestDist = d;
                    evict = k;
                }
            }
            if (evict === null) {
                let farDist = -1;
                for (const k of keys) {
                    const d = Math.abs(k - currentPage);
                    if (d > farDist) {
                        farDist = d;
                        evict = k;
                    }
                }
            }
            if (evict === null) break;
            pageCache.delete(evict);
        }
    }

    function buildPrefetchTargets() {
        const pc = pageCount();
        const set = new Set();
        const add = (p) => {
            if (p >= 0 && p < pc) set.add(p);
        };
        for (let d = 1; d <= 6; d++) add(currentPage + d);
        for (let d = 1; d <= 4; d++) add(currentPage - d);
        add(0);
        add(1);
        add(2);
        add(pc - 1);
        add(pc - 2);
        return [...set];
    }

    let prefetchRunning = false;
    let prefetchTimer = null;

    function schedulePrefetch() {
        if (prefetchTimer) return;
        prefetchTimer = setTimeout(() => {
            prefetchTimer = null;
            prefetchPages();
        }, 900);
    }

    async function prefetchPages() {
        if (prefetchRunning) return;
        prefetchRunning = true;
        const me = ++prefetchJob;
        const ctx = currentCtxKey();
        try {
            if (ctx !== cacheCtx) return;
            const targets = buildPrefetchTargets();
            const query = ($("#searchInput").value || "").trim();
            const ping = activePingFilters.size ? [...activePingFilters].join(",") : "";
            for (const p of targets) {
                if (me !== prefetchJob) return;
                if (ctx !== cacheCtx) return;
                if (pageCache.has(p)) continue;
                if (prefetchRunningThrottled()) break;
                try {
                    fetchInFlight++;
                    let res;
                    try {
                        res = JSON.parse(
                            await api().get_configs(
                                query,
                                JSON.stringify({ protocols: [...activeFilters], countries: [...activeCountries] }),
                                sortState.key,
                                sortState.dir,
                                p * PAGE_SIZE,
                                PAGE_SIZE,
                                ping
                            )
                        );
                    } finally {
                        fetchInFlight--;
                    }
                    if (me !== prefetchJob || ctx !== cacheCtx) return;
                    pageCache.set(p, res.configs || []);
                    trimPageCache();
                } catch (e) {}
            }
        } finally {
            prefetchRunning = false;
            if (!prefetchRunningThrottled()) schedulePrefetch();
        }
    }

    function prefetchRunningThrottled() {
        const keys = [...pageCache.keys()];
        if (keys.length >= 24) return true;
        const pc = pageCount();
        if (pc <= 2) return true;
        return false;
    }

    function scrollTableBottom() {
        requestAnimationFrame(() => {
            const el = wrapScrollEl();
            el.scrollTop = el.scrollHeight;
        });
    }

    function flushNavPending() {
        if (navPending !== null) {
            const p = navPending;
            navPending = null;
            navigateTo(p.page, p.scroll);
        } else {
            renderTable();
        }
    }

    function setNavBusy(on) {
        if (on) {
            document.body.classList.add("nav-busy");
        } else {
            document.body.classList.remove("nav-busy");
        }
    }

    function navigateTo(page, scrollBottom = false) {
        hideBusy();
        const pc = pageCount();
        const target = Math.max(0, Math.min(page, pc - 1));
        const ctx = currentCtxKey();
        const cached = (ctx === cacheCtx) ? pageCache.get(target) : undefined;
        if (cached) {
            if (navInFlight) {
                navPending = { page: target, scroll: scrollBottom };
                return;
            }
            setNavBusy(false);
            currentPage = target;
            allConfigs = cached.slice();
            loadedOffset = target * PAGE_SIZE;
            if (scrollBottom) scrollTableBottom();
            renderTable();
            schedulePrefetch();
            return;
        }
        if (navInFlight) {
            navPending = { page: target, scroll: scrollBottom };
            return;
        }
        navInFlight = true;
        navPending = null;
        currentPage = target;
        navLoading = true;
        if (!document.querySelectorAll("#configBody tr").length) {
            renderLoadingState();
        } else {
            setNavBusy(true);
        }
        loadConfigs(true)
            .then(() => {
                navInFlight = false;
                navLoading = false;
                setNavBusy(false);
                if (scrollBottom) scrollTableBottom();
                flushNavPending();
            })
            .catch(() => {
                navInFlight = false;
                navLoading = false;
                setNavBusy(false);
                flushNavPending();
            });
    }

    function goToPage(page) {
        navigateTo(page, false);
    }

    function goToFirstRow() {
        goToPage(0);
    }

    function goToLastRow() {
        navigateTo(Number.MAX_SAFE_INTEGER, true);
    }

    function renderWindow(force = true) {
        const tbody = document.querySelector("#configBody");
        if (!tbody) return;
        tbody.innerHTML = buildRowsHtml(displayConfigs || [], currentPage * PAGE_SIZE);
    }

    const api = () => window.pywebview.api;

    function waitForApi(cb, retries = 50) {
        if (window.pywebview && window.pywebview.api) {
            recalcPageSize();
            cb();
        } else if (retries > 0) {
            setTimeout(() => waitForApi(cb, retries - 1), 100);
        }
    }

    const TOAST_ICONS = {
        success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="m9 11 3 3L22 4"/></svg>',
        error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/></svg>',
        info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
        warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
    };

    let _toastAudio = null;
    function playToastSound() {
        try {
            const AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return;
            if (!_toastAudio) _toastAudio = new AC();
            if (_toastAudio.state === "suspended") _toastAudio.resume();
            const freq = 880;
            const osc = _toastAudio.createOscillator();
            const gain = _toastAudio.createGain();
            osc.type = "sine";
            osc.frequency.value = freq;
            gain.gain.setValueAtTime(0.001, _toastAudio.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.25, _toastAudio.currentTime + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.001, _toastAudio.currentTime + 0.35);
            osc.connect(gain);
            gain.connect(_toastAudio.destination);
            osc.start(_toastAudio.currentTime);
            osc.stop(_toastAudio.currentTime + 0.4);
        } catch (e) {}
    }

    let _toastTimer = null;
    function toast(msg, type = "info") {
        playToastSound();
        const container = $("#toast-container");
        let el = container.firstElementChild;
        container.querySelectorAll(".toast").forEach((t) => t.remove());
        el = document.createElement("div");
        el.className = "toast toast-" + type;
        el.innerHTML = `<span class="toast-icon">${TOAST_ICONS[type] || TOAST_ICONS.info}</span><span class="toast-msg">${esc(msg)}</span>`;
        if (type === "error") {
            el.style.cursor = "pointer";
            el.title = "Click to copy error";
            el.addEventListener("click", () => {
                navigator.clipboard.writeText(msg).then(() => {
                    el.querySelector(".toast-msg").textContent = "Copied!";
                    _toastTimer && clearTimeout(_toastTimer);
                    _toastTimer = setTimeout(() => el.remove(), 700);
                });
            });
        }
        container.appendChild(el);
        container.style.display = "flex";
        if (_toastTimer) clearTimeout(_toastTimer);
        _toastTimer = setTimeout(() => {
            el.style.transition = "opacity 0.3s, transform 0.3s";
            el.style.opacity = "0";
            el.style.transform = "scale(0.94)";
            setTimeout(() => {
                el.remove();
                if (!container.hasChildNodes()) container.style.display = "none";
            }, 300);
        }, 3500);
    }

    async function loadConfigs(reset = true, silent = false, opts = {}) {
        const job = ++loadJob;
        if (reset) {
            allConfigs = [];
            loadedOffset = currentPage * PAGE_SIZE;
            searchGen++;
            if (!opts.keepScroll) wrapScrollEl().scrollTop = 0;
        }
        try {
            const query = ($("#searchInput").value || "").trim();
            const ping = activePingFilters.size ? [...activePingFilters].join(",") : "";
            fetchInFlight++;
            let res;
            try {
                res = JSON.parse(
                    await api().get_configs(
                        query,
                        JSON.stringify({ protocols: [...activeFilters], countries: [...activeCountries] }),
                        sortState.key,
                        sortState.dir,
                        loadedOffset,
                        PAGE_SIZE,
                        ping
                    )
                );
            } finally {
                fetchInFlight--;
            }
            if (job !== loadJob) return allConfigs.length;
            const rows = res.configs || [];
            const total = res.total || 0;
            if (rows.length === 0 && total > 0 && currentPage * PAGE_SIZE >= total && !opts._retried) {
                currentPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);
                allConfigs = [];
                return loadConfigs(reset, silent, Object.assign({}, opts, { _retried: true }));
            }
            allConfigs = allConfigs.concat(rows);
            totalConfigs = total;
            loadedOffset = allConfigs.length;
            navLoading = false;
            const ctx = currentCtxKey();
            if (ctx !== cacheCtx) {
                pageCache.clear();
                cacheCtx = ctx;
            }
            pageCache.set(currentPage, rows.slice());
            trimPageCache();
            if (!silent) {
                renderTable();
                schedulePrefetch();
            }
            return allConfigs.length;
        } catch (e) {
            navLoading = false;
            toast("Failed to load configs", "error");
            return allConfigs.length;
        }
    }


    function formatExpiry(e) {
        if (!e) return { text: "?", cls: "", title: "No expiry info" };
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
                const key = (c.server || "") + ":" + (c.port || 0);
                const saved = latencyResults.get(key);
                const badgeHtml = saved
                    ? `<span class="latency-badge ${latencyClass(saved.ms)}" data-server="${escAttr(c.server)}" data-port="${c.port}" data-id="${c.id}">${latencyLabel(saved.ms, saved.error)}</span>`
                    : `<span class="latency-badge" data-server="${escAttr(c.server)}" data-port="${c.port}" data-id="${c.id}"></span>`;
                return `
                <tr data-id="${c.id}">
                    <td class="row-number">${baseIndex + i + 1}</td>
                    <td title="${esc(c.name)}">${esc(c.name)}</td>
                    <td><span class="protocol-badge" style="background:${c.color}">${esc(c.protocol)}</span></td>
                    <td title="${esc(c.server)}">${esc(c.server)}</td>
                    <td>${c.port}</td>
                    <td title="${esc(c.country || '')}">${flagMarkup(c.country)}${esc(c.country || '?')}</td>
                    <td>${badgeHtml}</td>
                    <td>
                        <div class="actions-cell">
                            <button class="btn btn-sm btn-secondary ping-btn" data-id="${c.id}" title="Test latency">Ping</button>
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

    function renderEmptyGrid() {
        const tbody = $("#configBody");
        const cols = document.querySelectorAll("#configTable thead th").length || 1;
        const rows = Math.max(1, Math.min(PAGE_SIZE || 20, 30));
        const cell = "<td>&nbsp;</td>";
        tbody.innerHTML = `<tr>${cell.repeat(cols)}</tr>`.repeat(rows);
    }

    function renderLoadingState() {
        const tbody = $("#configBody");
        if (!tbody) return;
        const cols = document.querySelectorAll("#configTable thead th").length || 1;
        tbody.innerHTML = `<tr><td colspan="${cols}" style="height:120px;text-align:center;color:var(--text-muted,#94a3b8)">
            <div style="display:inline-flex;align-items:center;gap:10px;font-size:13px">
                <span style="width:16px;height:16px;border:2px solid rgba(99,102,241,.3);border-top-color:#6366f1;border-radius:50%;display:inline-block;animation:spin .7s linear infinite"></span>
                <span>Loading...</span>
            </div>
            <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
        </td></tr>`;
    }

    function tableRowsList() {
        return Array.from(document.querySelectorAll("#configBody tr"));
    }

    function applyRowSelection() {
        const rows = tableRowsList();
        rows.forEach((r) => r.classList.remove("row-selected"));
        if (!rowSelectionActive || rows.length === 0) return;
        if (selectedRowIndex >= rows.length) selectedRowIndex = rows.length - 1;
        if (selectedRowIndex < 0) selectedRowIndex = 0;
        const row = rows[selectedRowIndex];
        row.classList.add("row-selected");
        try {
            row.scrollIntoView({ block: "nearest" });
        } catch (e) {}
    }

    function moveRowSelection(delta) {
        const rows = tableRowsList();
        if (rows.length === 0) return;
        rowSelectionActive = true;
        selectedRowIndex = Math.max(0, Math.min(rows.length - 1, selectedRowIndex + delta));
        applyRowSelection();
    }

    function handleTableKeys(e) {
        if (e.ctrlKey || e.altKey || e.metaKey) return;
        const t = e.target;
        if (t) {
            const tag = t.tagName || "";
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable) return;
        }
        const overlay = $("#progressOverlay");
        if (overlay && overlay.style.display === "flex") return;
        const about = document.getElementById("aboutModal");
        if (about && about.style.display === "flex") return;
        const table = $("#configTable");
        if (!table || table.style.display === "none") return;
        const total = totalConfigs || 0;
        switch (e.key) {
            case "ArrowDown":
                e.preventDefault();
                moveRowSelection(1);
                break;
            case "ArrowUp":
                e.preventDefault();
                moveRowSelection(-1);
                break;
            case "PageDown":
                e.preventDefault();
                if (total) goToPage(currentPage + 1);
                break;
            case "PageUp":
                e.preventDefault();
                if (total) goToPage(currentPage - 1);
                break;
            case "Home":
                if (!total) break;
                e.preventDefault();
                if (e.shiftKey) {
                    moveRowSelection(-9999);
                } else {
                    goToPage(0);
                }
                break;
            case "End":
                if (!total) break;
                e.preventDefault();
                if (e.shiftKey) {
                    moveRowSelection(9999);
                } else {
                    goToLastRow();
                }
                break;
            case "Enter": {
                e.preventDefault();
                const rows = tableRowsList();
                if (rows.length === 0) break;
                rowSelectionActive = true;
                if (selectedRowIndex >= rows.length) selectedRowIndex = rows.length - 1;
                const row = rows[Math.max(0, selectedRowIndex)];
                const btn = row && row.querySelector(".detail-btn");
                if (btn) btn.click();
                break;
            }
        }
    }

    function renderTable() {
        const tbody = $("#configBody");
        const table = $("#configTable");
        const emptyState = $("#emptyState");
        updatePingAllBtnState();

        if (pendingFilterRender === null) {
            displayConfigs = allConfigs;
        } else {
            displayConfigs = pendingFilterRender;
        }
        pendingFilterRender = null;

        if (totalConfigs === 0) {
            $("#configCount").textContent = "0 configs";
            updatePagination();
            emptyState.style.display = "none";
            table.style.display = "table";
            renderEmptyGrid();
            document.getElementById("toolbarStats")?.remove();
            return;
        }
        emptyState.style.display = "none";
        table.style.display = "table";
        if (searchStateActive) {
            searchStateActive = false;
            const def = $("#emptyDefault");
            const searching = $("#emptySearching");
            if (def) def.style.display = "block";
            if (searching) searching.style.display = "none";
        }

        updateConfigCounter();
        updatePagination();

        if (displayConfigs.length === 0 && totalConfigs > 0) {
            if (busyOperation) {
                showBusy(busyOperation);
                return;
            }
            if (navLoading || fetchInFlight > 0) {
                renderLoadingState();
                return;
            }
            tbody.innerHTML = `
                <tr><td colspan="8">
                    <div class="empty-state">
                        <h3>No matching configs</h3>
                        <p>Try clearing your search, ping or filters</p>
                    </div>
                </td></tr>`;
            return;
        }
        renderWindow(true);
    }

    function updatePingAllBtnState() {
        const btn = $("#pingAllBtn");
        if (!btn) return;
        const empty = totalConfigs === 0 || displayConfigs.length === 0;
        if (empty || pingAllRunning) {
            btn.disabled = true;
        } else {
            btn.disabled = false;
            btn.innerHTML = "Ping All";
        }
    }

    let filterJobSeq = 0;

    function latencyOf(c) {
        const r = latencyResults.get((c.server || "") + ":" + (c.port || 0));
        return r ? r.ms : Number.NaN;
    }
    function pingCategoryOf(c) {
        const ms = latencyOf(c);
        if (Number.isNaN(ms)) return "untested";
        if (ms < 0) return "dead";
        if (ms < 150) return "fast";
        if (ms < 300) return "mid";
        return "slow";
    }

    function fastLocalFilter() {
        const q = ($("#searchInput").value || "").trim().toLowerCase();
        let list = allConfigs;
        if (activeFilters.size) {
            list = list.filter((c) => activeFilters.has(c.protocol_type || c.protocol));
        }
        if (activeCountries.size) {
            list = list.filter((c) => activeCountries.has(c.country || ""));
        }
        if (activePingFilters.size) {
            list = list.filter((c) => activePingFilters.has(pingCategoryOf(c)));
        }
        if (q) {
            list = list.filter((c) => {
                const hay = ((c.name || "") + " " + (c.server || "") + " " + (c.protocol || "")).toLowerCase();
                return hay.includes(q);
            });
        }
        return list;
    }

    function refreshFilteredTable(itemEl) {
        const myJob = ++filterJobSeq;
        const flashKey = itemEl ? itemEl.dataset.ping || itemEl.dataset.type || itemEl.dataset.country || null : null;
        syncFilterHighlights();
        flashFilterItem(itemEl, flashKey);
        showBusy("Filtering configs...");
        const local = fastLocalFilter();
        pendingFilterRender = local;
        renderTable();
        currentPage = 0;
        loadConfigs(true)
            .then(() => {
                if (myJob !== filterJobSeq) { hideBusy(); return; }
                hideBusy();
                pendingFilterRender = allConfigs;
                renderTable();
                try { renderFilters().catch(() => {}); } catch (e) {}
                const el = findFilterItem(flashKey);
                syncFilterHighlights();
                flashFilterItem(el, flashKey);
                setTimeout(() => {
                    if (myJob === filterJobSeq) unflashFilterItem(findFilterItem(flashKey));
                }, 350);
            })
            .catch(() => {
                if (myJob !== filterJobSeq) { hideBusy(); return; }
                hideBusy();
                unflashFilterItem(findFilterItem(flashKey));
            });
    }

    function syncFilterHighlights() {
        document.querySelectorAll("#protocolFilters .filter-item").forEach((el) => {
            const k = el.dataset.type;
            el.classList.toggle("active", k === "__all__" ? activeFilters.size === 0 : activeFilters.has(k));
        });
        document.querySelectorAll("#pingFilters .filter-item").forEach((el) => {
            const k = el.dataset.ping;
            el.classList.toggle("active", k === "__all__" ? activePingFilters.size === 0 : activePingFilters.has(k));
        });
        document.querySelectorAll("#countryFilters .filter-item").forEach((el) => {
            const k = el.dataset.country;
            el.classList.toggle("active", k === "__all__" ? activeCountries.size === 0 : activeCountries.has(k));
        });
    }

    function flashFilterItem(itemEl, key) {
        if (!itemEl) return;
        itemEl.classList.add("filtering");
        const cnt = itemEl.querySelector(".filter-count");
        if (cnt && !itemEl.dataset.flashing) {
            itemEl.dataset.flashing = "1";
            cnt.dataset.prev = cnt.textContent;
        }
    }

    function unflashFilterItem(itemEl) {
        if (!itemEl) return;
        itemEl.classList.remove("filtering");
        if (itemEl.dataset.flashing) {
            const cnt = itemEl.querySelector(".filter-count");
            if (cnt) cnt.textContent = cnt.dataset.prev || cnt.textContent;
            delete itemEl.dataset.flashing;
        }
    }

    function findFilterItem(key) {
        if (!key) return null;
        return document.querySelector(
            `#pingFilters .filter-item[data-ping="${key}"], ` +
            `#protocolFilters .filter-item[data-type="${key}"], ` +
            `#countryFilters .filter-item[data-country="${escAttr(key)}"]`
        );
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

    function latencyClass(ms) {
        if (ms < 0) return "lat-bad";
        if (ms < 150) return "lat-good";
        if (ms < 300) return "lat-mid";
        return "lat-bad";
    }

    function latencyLabel(ms, err) {
        if (ms < 0) return err ? "?" : "?";
        return ms + "ms";
    }

    async function handlePing(btn) {
        const badge = btn.closest("tr").querySelector(".latency-badge");
        const server = badge.dataset.server || "";
        const port = badge.dataset.port || 0;
        btn.disabled = true;
        btn.textContent = "?";
        try {
            const res = JSON.parse(await api().test_latency(server, port));
            saveLatency(server, port, res);
        } catch (e) {
            saveLatency(server, port, { ok: false, ms: -1, error: e.message });
        } finally {
            btn.disabled = false;
            btn.textContent = "Ping";
        }
    }

    function applyLatencyBadge(badge, res) {
        if (!badge) return;
        const ms = typeof res.ms === "number" ? res.ms : -1;
        badge.className = "latency-badge " + latencyClass(ms);
        badge.textContent = latencyLabel(ms, res.error);
        badge.title = res.error || (ms >= 0 ? `Latency: ${ms}ms` : "Unreachable");
    }

    function saveLatency(server, port, res) {
        const key = (server || "") + ":" + (port || 0);
        latencyResults.set(key, res);
        const sel = `.latency-badge[data-server="${CSS.escape(server || "")}"][data-port="${port || 0}"]`;
        document.querySelectorAll(sel).forEach((b) => applyLatencyBadge(b, res));
        schedulePingFilterRefresh();
    }

    let pingFilterRefreshTimer = null;
    function schedulePingFilterRefresh() {
        if (pingFilterRefreshTimer) return;
        pingFilterRefreshTimer = setTimeout(() => {
            pingFilterRefreshTimer = null;
            renderPingFilters();
        }, 400);
    }

    const TASK_LABELS = {
        fetch: "Fetching sources",
        scan: "Scanning the web",
        telegram: "Fetching from Telegram",
        ping: "Pinging all configs",
        import_file: "Importing file",
        raw_import: "Importing raw text",
    };

    function openConfirmModal(task) {
        $("#confirmTitle").textContent = TASK_LABELS[task] || task;
        $("#confirmMsg").textContent =
            "There is a task already running: " + (TASK_LABELS[currentTask] || currentTask) +
            ".\nStop it and start " + (TASK_LABELS[task] || task) + "?";
        $("#confirmModal").style.display = "flex";
    }

    function showConfirm({ title, message, icon, yesLabel, noLabel }) {
        return new Promise((resolve) => {
            if (icon) $("#confirmIcon").textContent = icon;
            $("#confirmTitle").textContent = title || "Confirm";
            $("#confirmMsg").textContent = message || "";
            const yesBtn = $("#confirmYesBtn");
            const noBtn = $("#confirmNoBtn");
            yesBtn.textContent = yesLabel || "Yes";
            noBtn.textContent = noLabel || "No";
            $("#confirmModal").style.display = "flex";
            const cleanup = (result) => {
                $("#confirmModal").removeEventListener("mousedown", outsideHandler, true);
                yesBtn.onclick = null;
                noBtn.onclick = null;
                $("#confirmModal").style.display = "none";
                $("#confirmIcon").textContent = "✓";
                resolve(result);
            };
            const outsideHandler = (e) => {
                if (e.target === $("#confirmModal")) cleanup(false);
            };
            $("#confirmModal").addEventListener("mousedown", outsideHandler, true);
            yesBtn.onclick = () => cleanup(true);
            noBtn.onclick = () => cleanup(false);
        });
    }

    async function stopCurrentTask() {
        try { await api().cancel(); } catch (e) {}
        if (pingAllRunning) {
            stopPingPoller();
            finishPingAll(null, true);
        }
        stopProgressPolling();
        hideProgress();
        if (pingAllRunning || currentTask === "ping") {
            resetPingUiState();
        } else {
            clearPingResults();
        }
        await waitForBgIdle();
        const bg = await api().get_bg_result().catch(() => "{}");
        try {
            const r = JSON.parse(bg);
            if (r && r.error) toast("Task stopped", "info");
        } catch (e) {}
        currentTask = null;
    }

    async function waitForBgIdle(timeoutMs = 2500) {
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            try {
                const p = JSON.parse(await api().get_progress());
                if (!p || p.phase === "idle" || !String(p.phase || "").startsWith("ping")) {
                    return;
                }
            } catch (e) {}
            await new Promise((r) => setTimeout(r, 100));
        }
    }

    function resetPingUiState() {
        latencyResults.clear();
        activePingFilters.clear();
        pingStats = null;
        pingAppliedSince = 0;
        pingLastRender = 0;
        document.querySelectorAll(".latency-badge").forEach((b) => {
            b.textContent = "";
            b.removeAttribute("class");
            b.className = "latency-badge";
        });
        const ptr = $("#pingFilters");
        if (ptr) ptr.innerHTML = "";
        renderTable();
        loadPingResults();
    }

    function clearPingResults() {
        latencyResults.clear();
        activePingFilters.clear();
        pingStats = null;
        pingAppliedSince = 0;
        pingLastRender = 0;
        document.querySelectorAll(".latency-badge").forEach((b) => {
            b.textContent = "";
            b.removeAttribute("class");
            b.className = "latency-badge";
        });
        const ptr = $("#pingFilters");
        if (ptr) ptr.innerHTML = "";
        renderTable();
        renderPingFilters();
    }

    async function requestTask(task, doWork) {
        if (currentTask) {
            pendingTaskWork = () => { currentTask = task; doWork(); };
            openConfirmModal(task);
            return;
        }
        currentTask = task;
        doWork();
    }

    async function handlePingAll() {
        const btn = $("#pingAllBtn");
        if (pingAllRunning) {
            showProgress("⚡", "Pinging filtered configs", "Pinging...");
            return;
        }
        requestTask("ping", () => handlePingAllStart());
    }

    async function handlePingAllStart() {
        const btn = $("#pingAllBtn");
        pingAllRunning = true;
        pingAllCancelled = false;
        pingAppliedSince = 0;
        pingLastRender = 0;
        showProgress("⚡", "Pinging filtered configs", "Preparing...");
        try {
            const query = ($("#searchInput").value || "").trim();
            const scope = JSON.stringify({
                query,
                protocols: [...activeFilters],
                countries: [...activeCountries],
            });
            await api().start_bg("ping_all", scope);
        } catch (e) {
            pingAllRunning = false;
            updatePingAllBtnState();
            hideProgress();
            toast("Failed to start ping: " + e.message, "error");
            return;
        }
        renderPingFilters();
        document.querySelectorAll(".latency-badge:not(:empty)").forEach((b) => {
            if (!latencyResults.has(b.dataset.server + ":" + b.dataset.port)) b.textContent = "?";
        });
        startPingPoller(btn);
    }

    let pingPollTimer = null;
    let pingAppliedSince = 0;
    let pingLastRender = 0;
    let pingStartTime = 0;
    function fmtElapsed(sec) {
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return m > 0 ? `${m}m ${s}s` : `${s}s`;
    }
    function startPingPoller(btn) {
        pingStartTime = Date.now();
        stopProgressPolling();
        const poll = async () => {
            if (pingAllCancelled) { stopPingPoller(); return; }
            try {
                const prog = JSON.parse(await api().get_ping_progress());
                const done = prog.done || 0;
                const total = prog.total || 0;
                const elapsedSecs = (Date.now() - pingStartTime) / 1000;
                const pText = $("#progressText");
                const pBar = $("#progressBar");
                const pCount = $("#progressCount");
                const pTime = $("#progressTime");
                if (pText) pText.textContent = total > 0 ? `Testing ${done} of ${total} configs...` : "Pinging...";
                if (pBar) pBar.style.width = total > 0 ? Math.round((done / total) * 100) + "%" : "0%";
                if (pCount) pCount.textContent = total > 0 ? `${done}/${total} tested` : "0 configs";
                if (pTime) pTime.textContent = "⏱ " + fmtElapsed(elapsedSecs);
                try {
                    const batch = JSON.parse(await api().get_ping_batch(pingAppliedSince));
                    if (batch.batch && batch.batch.length) {
                        batch.batch.forEach((item) => {
                            latencyResults.set(item.key, { ms: item.ms, ok: item.ok, error: item.error });
                        });
                        pingAppliedSince = batch.since;
                    }
                } catch (e) {}
                const now = Date.now();
                if (now - pingLastRender > 500) {
                    pingLastRender = now;
                    renderTable();
                    schedulePingFilterRefresh();
                }
                if (done >= total && total > 0) {
                    renderTable();
                    finishPingAll(btn, false);
                    return;
                }
                const progress = JSON.parse(await api().get_progress());
                if ((progress.phase === "idle" || progress.phase === "ping_done") && total > 0) {
                    renderTable();
                    finishPingAll(btn, false);
                    return;
                }
            } catch (e) {}
            if (!pingAllCancelled) pingPollTimer = setTimeout(poll, 350);
        };
        pingPollTimer = setTimeout(poll, 150);
    }

    function stopPingPoller() {
        if (pingPollTimer) { clearTimeout(pingPollTimer); pingPollTimer = null; }
    }

    function finishPingAll(btn, stopped) {
        stopPingPoller();
        pingAllRunning = false;
        pingAllCancelled = false;
        if (currentTask === "ping") currentTask = null;
        renderTable();
        updatePingAllBtnState();
        renderPingFilters();
        hideProgress();
        playFinishChime();
    }

    async function renderFilters() {
        const container = $("#protocolFilters");
        let counts = [];
        let allTotal = totalConfigs;
        try {
            const parsed = JSON.parse(await api().get_protocol_counts());
            counts = parsed.items || [];
            if (typeof parsed.total === "number") allTotal = parsed.total;
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
                    <span class="filter-count">${allTotal.toLocaleString()}</span>
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
        let countryTotal = totalConfigs;
        try {
            const parsed = JSON.parse(await api().get_country_counts());
            countries = parsed.items || [];
            if (typeof parsed.total === "number") countryTotal = parsed.total;
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
                <span class="filter-count">${countryTotal.toLocaleString()}</span>
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
        renderPingFilters();
    }

    function renderPingFilters() {
        const container = $("#pingFilters");
        if (!container) return;
        const cats = [
            { key: "fast", label: "Fast (<150ms)", color: "#22c55e" },
            { key: "mid", label: "Medium (150-300ms)", color: "#eab308" },
            { key: "slow", label: "Slow (>300ms)", color: "#f97316" },
            { key: "dead", label: "Unreachable / Error", color: "#ef4444" },
            { key: "untested", label: "Not tested", color: "#64748b" },
        ];
        api()
            .get_ping_stats()
            .then((r) => {
                let counts = null;
                try {
                    counts = JSON.parse(r);
                } catch (e) {}
                const stats = counts && typeof counts.total === "number" ? counts : null;
                if (stats) {
                    pingStats = stats;
                    renderPingFilterBox(container, cats, stats);
                } else {
                    renderPingFilterBox(container, cats, null);
                }
                renderTable();
            })
            .catch(() => {
                renderPingFilterBox(container, cats, null);
                renderTable();
            });
    }

    function renderPingFilterBox(container, cats, counts) {
        const totalAll = counts ? counts.total : totalConfigs;
        const allActive = activePingFilters.size === 0 ? " active" : "";
        container.innerHTML =
            `<div class="filter-item${allActive}" data-ping="__all__">
                <span><span class="filter-dot" style="background:#8b5cf6"></span>All Pings</span>
                <span class="filter-count">${totalAll.toLocaleString()}</span>
            </div>` +
            cats
                .map((cat) => {
                    const active = activePingFilters.has(cat.key) ? " active" : "";
                    const n = counts ? (counts[cat.key] || 0) : "?";
                    const num = typeof n === "number" ? n.toLocaleString() : n;
                    return `
                <div class="filter-item${active}" data-ping="${cat.key}">
                    <span><span class="filter-dot" style="background:${cat.color}"></span>${cat.label}</span>
                    <span class="filter-count">${num}</span>
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
                ind.textContent = sortState.dir === 1 ? "?" : "?";
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
        if (key === "ping") {
            sortByPing();
        } else {
            currentPage = 0;
            showBusy("Sorting...");
            loadConfigs(true).then(() => hideBusy());
        }
    }

    function sortByPing() {
        const dir = sortState.dir;
        allConfigs.sort((a, b) => {
            const ma = latencyKey(a);
            const mb = latencyKey(b);
            if (ma === -1 && mb === -1) return 0;
            if (ma === -1) return 1;
            if (mb === -1) return -1;
            return (ma - mb) * dir;
        });
        renderTable();
    }

    function latencyKey(c) {
        const r = latencyResults.get((c.server || "") + ":" + (c.port || 0));
        return r && typeof r.ms === "number" ? r.ms : -1;
    }

    function showProgress(icon, title, label) {
        progressStartTime = Date.now();
        const tIcon = $("#progressIcon");
        const tText = $("#progressTitleText");
        const tTime = $("#progressTime");
        if (tIcon) tIcon.textContent = icon || "🔥";
        if (tText) tText.textContent = title || "Working...";
        if (tTime) tTime.textContent = "";
        $("#progressText").textContent = label || "";
        $("#progressBar").style.width = "0%";
        $("#progressCount").textContent = "0 configs";
        $("#progressOverlay").style.display = "flex";
        stopProgressPolling();
        progressTimer = setInterval(pollProgress, 600);
    }

    function stopProgressPolling() {
        if (progressTimer) {
            clearInterval(progressTimer);
            clearTimeout(progressTimer);
            progressTimer = null;
        }
    }

    async function refreshLivePage() {
        const job = ++loadJob;
        const gen = searchGen;
        const page = currentPage;
        const query = ($("#searchInput").value || "").trim();
        const ping = activePingFilters.size ? [...activePingFilters].join(",") : "";
        let res;
        try {
            fetchInFlight++;
            try {
                res = JSON.parse(
                    await api().get_configs(
                        query,
                        JSON.stringify({ protocols: [...activeFilters], countries: [...activeCountries] }),
                        sortState.key,
                        sortState.dir,
                        currentPage * PAGE_SIZE,
                        PAGE_SIZE,
                        ping
                    )
                );
            } finally {
                fetchInFlight--;
            }
        } catch (e) {
            return;
        }
        if (job !== loadJob || gen !== searchGen || page !== currentPage) return;
        totalConfigs = res.total || 0;
        updateConfigCounter();
        updatePagination();
        const rows = res.configs || [];
        const total = res.total || 0;
        if (rows.length === 0 && total > 0) {
            return;
        }
        const shown = allConfigs.length;
        if (shown === 0 && rows.length > 0) {
            allConfigs = rows;
            renderTable();
            return;
        }
        if (rows.length > shown) {
            const tail = rows.slice(shown);
            allConfigs = rows;
            const tbody = document.querySelector("#configBody");
            if (tbody && tbody.rows.length > 0) {
                tbody.insertAdjacentHTML("beforeend", buildRowsHtml(tail, currentPage * PAGE_SIZE + shown));
            } else {
                renderTable();
            }
        } else {
            allConfigs = rows;
        }
    }

    function scheduleLiveRefresh() {
        if (liveRefreshTimer) return;
        liveRefreshTimer = setTimeout(() => {
            liveRefreshTimer = null;
            const job = ++liveRefreshJob;
            const pingActive = livePingRefresh;
            refreshLivePage().then(() => {
                if (job === liveRefreshJob) renderFilters();
                if (job === liveRefreshJob && pingActive) applySessionPings();
            });
        }, 800);
    }

    function showSearchingState(label, hint) {
        searchStateActive = true;
        searchStartTime = Date.now();
        stopSearchTimer();
        searchTimerId = setInterval(updateSearchTimer, 1000);
        const def = $("#emptyDefault");
        const searching = $("#emptySearching");
        const txt = $("#emptySearchingText");
        const hintEl = document.querySelector(".searching-hint");
        if (def) def.style.display = "none";
        if (searching) searching.style.display = "none";
        if (txt) txt.textContent = label || "Searching...";
        if (hintEl) hintEl.textContent = hint || "";
        updateSearchTimer();
    }

    function updateSearchTimer() {
        const el = $("#searchingTime");
        if (!el) return;
        const elapsed = Math.max(0, Math.floor((Date.now() - searchStartTime) / 1000));
        const m = Math.floor(elapsed / 60);
        const s = elapsed % 60;
        el.textContent = "⏱ " + (m > 0 ? m + "m " : "") + s + "s";
    }

    function stopSearchTimer() {
        if (searchTimerId) {
            clearInterval(searchTimerId);
            searchTimerId = null;
        }
    }

    function hideSearchingState() {
        searchStateActive = false;
        stopSearchTimer();
        const def = $("#emptyDefault");
        const searching = $("#emptySearching");
        if (def) def.style.display = "none";
        if (searching) searching.style.display = "none";
    }

    function hideProgress() {
        stopProgressPolling();
        hideSearchingState();
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
            const tTime = $("#progressTime");
            if (tTime && progressStartTime) {
                const elapsed = Math.max(0, Math.round((Date.now() - progressStartTime) / 1000));
                const h = Math.floor(elapsed / 3600);
                const m = Math.floor((elapsed % 3600) / 60);
                const s = elapsed % 60;
                const pad = (n) => String(n).padStart(2, "0");
                tTime.textContent = (h > 0 ? h + ":" : "") + pad(m) + ":" + pad(s);
            }
            const count = typeof p.count === "number" ? p.count : null;
            if (count !== null) {
                $("#progressCount").textContent = count.toLocaleString() + " configs written";
            }
            if (count !== null && phase !== "done" && phase !== "idle") {
                if (count !== lastKnownCount || (count > 0 && allConfigs.length === 0)) {
                    lastKnownCount = count;
                    scheduleLiveRefresh();
                }
            }
            if (phase === "done" || phase === "error") {
                await finishBgWhenDone();
            }
        } catch (e) { /* ignore transient errors */ }
    }

    let bgDoneHandled = false;
    async function finishBgWhenDone() {
        const overlay = document.getElementById("progressOverlay");
        if (!overlay || overlay.style.display !== "flex") return true;
        if (bgDoneHandled) return true;
        try {
            const result = JSON.parse(await api().get_bg_result());
            if (result.status === "running") {
                return false;
            }
            bgDoneHandled = true;
            if (result.error) {
                hideProgress();
                toast("Scan failed: " + result.error, "error");
                return true;
            }
            applyFetchResult(result);
            return true;
        } catch (e) {
            return false;
        }
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
        requestTask("fetch", () => handleFetchInner());
    }

    async function handleFetchInner() {
        const raw = ($("#urlInput").value || "").trim();
        const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
        const isUrl = (l) => /^https?:\/\/\S+/i.test(l);

        if (lines.length === 0) {
            showProgress("🔍", "Scanning the web", "Searching the web for new config sources...");
            lastKnownCount = null;
            livePingRefresh = $("#scanWebPingCb").checked;
            totalConfigs = 0;
            allConfigs = [];
            searchGen++;
            clearPingResults();
            showSearchingState("Scanning the web...", "Searching the web for new sources ? found configs will appear here as they are discovered.");
            renderTable();
            renderFilters();
            try {
await api().start_bg("auto_fetch", "", $("#scanWebPingCb").checked ? 1 : 0);
                startBgPoller();
            } catch (e) {
                hideProgress();
                toast("Scan failed: " + e.message, "error");
            }
            return;
        }

        const invalid = lines.filter((l) => !isUrl(l));
        if (invalid.length > 0) {
            const shown = invalid.slice(0, 3)
                .map((l) => `"${l.length > 40 ? l.slice(0, 40) + "?" : l}"`)
                .join(", ");
            const more = invalid.length > 3 ? ` (+${invalid.length - 3} more)` : "";
            toast(`Skipped ${invalid.length} invalid line(s) ? only http/https subscription URLs allowed: ${shown}${more}`, "error");
            $("#urlInput").focus();
        }

        const valid = lines.filter(isUrl);
        if (valid.length === 0) {
            toast("No valid subscription URLs found. Enter http/https links only, one per line.", "error");
            return;
        }

        showProgress("📡", "Fetching sources", "Fetching configs from subscription URLs...");
        lastKnownCount = null;
        livePingRefresh = $("#scanWebPingCb").checked;
        totalConfigs = 0;
        allConfigs = [];
        searchGen++;
        clearPingResults();
        renderTable();
        renderFilters();
        try {
            await api().start_bg("fetch_urls", valid.join("\n"), $("#scanWebPingCb").checked ? 1 : 0);
            startBgPoller();
        } catch (e) {
            hideProgress();
            toast("Fetch failed: " + e.message, "error");
        }
    }

    async function handleFetchTelegram() {
        requestTask("telegram", () => handleFetchTelegramInner());
    }

    async function handleFetchTelegramInner() {
        const raw = ($("#urlInput").value || "").trim();
        const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
        const isTg = (l) => /t\.me\//i.test(l) || /^@[A-Za-z0-9_]+$/i.test(l);
        const tg = lines.filter(isTg);

        if (lines.length > 0 && tg.length === 0) {
            toast("Telegram channels not found in Sources. Enter channel links like @name or t.me/s/name ? or leave empty to use the 157 built-in channels.", "error");
            return;
        }

        showProgress("✈️", "Scanning Telegram", tg.length ? `Scanning ${tg.length} Telegram channel(s)...` : "Scanning 157 Telegram channels...");
        lastKnownCount = null;
        livePingRefresh = $("#tgPingCb").checked;
        totalConfigs = 0;
        allConfigs = [];
        searchGen++;
        clearPingResults();
        showSearchingState("Scanning Telegram...", "Searching Telegram channels ? found configs will appear here as they are discovered.");
        renderTable();
        renderFilters();
        try {
            await api().start_bg("fetch_telegram", tg.join("\n"), $("#tgPingCb").checked ? 1 : 0);
            startBgPoller();
        } catch (e) {
            hideProgress();
            toast("Telegram fetch failed: " + e.message, "error");
        }
    }

    async function handleScanWeb() {
        requestTask("scan", () => handleScanWebInner());
    }

    async function handleScanWebInner() {
        showProgress("🔍", "Scanning the web", "Searching the web for new config sources...");
        lastKnownCount = null;
        livePingRefresh = $("#scanWebPingCb").checked;
        totalConfigs = 0;
        allConfigs = [];
        clearPingResults();
        showSearchingState("Scanning the web...", "Searching the web for new sources ? found configs will appear here as they are discovered.");
        renderTable();
        renderFilters();
        try {
            await api().start_bg("auto_fetch", "", $("#scanWebPingCb").checked ? 1 : 0);
            startBgPoller();
        } catch (e) {
            hideProgress();
            toast("Scan failed: " + e.message, "error");
        }
    }

    function startBgPoller() {
        bgDoneHandled = false;
        stopProgressPolling();
        const poll = async () => {
            try {
                const overlay = document.getElementById("progressOverlay");
                if (overlay.style.display !== "flex") return;
                const p = JSON.parse(await api().get_progress());
                const phase = p.phase || "idle";
                let label = p.detail || "Working...";
                let pct = 0;
                if (phase === "discovering") {
                    label = "Scanning the web... " + (p.detail || "");
                    pct = p.total ? Math.round((p.current / p.total) * 100) : 0;
                } else if (phase === "fetching") {
                    label = "Fetching sources (" + p.current + "/" + p.total + ")...";
                    pct = p.total ? Math.round((p.current / p.total) * 100) : 0;
                } else if (phase === "starting") {
                    label = "Starting scan...";
                    pct = 0;
                }
                $("#progressText").textContent = label;
                $("#progressBar").style.width = pct + "%";
                const tTime = $("#progressTime");
                if (tTime && progressStartTime) {
                    tTime.textContent = "⏱ " + fmtElapsed(Math.max(0, Math.round((Date.now() - progressStartTime) / 1000)));
                }
                const count = typeof p.count === "number" ? p.count : null;
                if (count !== null) {
                    $("#progressCount").textContent = count.toLocaleString() + " configs written";
                }
                if (count !== null && phase !== "done" && phase !== "idle") {
                    if (count !== lastKnownCount || (count > 0 && allConfigs.length === 0)) {
                        lastKnownCount = count;
                        scheduleLiveRefresh();
                    }
                }
                if (phase === "done" || phase === "error") {
                    if (await finishBgWhenDone()) return;
                    setTimeout(poll, 300);
                    return;
                }
                setTimeout(poll, 500);
            } catch (e) {
                hideProgress();
                toast("Scan failed: " + e.message, "error");
            }
        };
        progressTimer = setTimeout(poll, 300);
    }

    async function applyFetchResult(res) {
        currentTask = null;
        hideProgress();
        hideSearchingState();
        lastKnownCount = res.total || 0;
        if (liveRefreshTimer) {
            clearTimeout(liveRefreshTimer);
            liveRefreshTimer = null;
        }
        if (res.discovered && res.discovered.length > 0) {
            showDiscovered(res.discovered);
        }
        currentPage = 0;
        totalConfigs = res.total || 0;
        const target = Math.min(PAGE_SIZE, totalConfigs);
        if (target === 0) {
            await loadConfigs(true);
        } else if (allConfigs.length < target) {
            await refreshLivePage();
        }
        updateConfigCounter();
        updatePagination();
        renderFilters();
        if (livePingRefresh) {
            await applySessionPings();
        }
        livePingRefresh = false;
        playFinishChime();
        if (res.cancelled) {
            toast(`Scan cancelled ? ${res.total} configs loaded so far`, "info");
        } else if ((res.added || 0) > 0) {
            toast(`Added ${res.added} new config ? ${res.total} total`, "success");
        } else if (res.total > 0) {
            toast(`No new configs ? everything was already saved (${res.total} total)`, "info");
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
        requestTask("import_file", () => handleImportFileInner());
    }

    async function handleImportFileInner() {
        try {
            showProgress("📂", "Importing file", "Importing configs from file...");
            const res = JSON.parse(await api().import_from_file(""));
            hideProgress();
            currentTask = null;
            if (res.cancelled) return;
            if (res.error) {
                toast(res.error, "error");
                return;
            }
            if (res.errors && res.errors.length > 0) {
                res.errors.forEach((e) => toast(e, "error"));
            }
            currentPage = 0;
            await loadConfigs(true);
            renderFilters();
            toast(`Loaded ${res.total} configs from file`, "success");
        } catch (e) {
            hideProgress();
            toast("Import failed", "error");
        }
    }

    async function handleRawImport() {
        requestTask("raw_import", () => handleRawImportInner());
    }

    async function handleRawImportInner() {
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
            currentPage = 0;
            await loadConfigs(true);
            renderFilters();
            currentTask = null;
            toast(`Loaded ${res.total} configs`, "success");
        } catch (e) {
            currentTask = null;
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
        const ok = await showConfirm({ title: "Clear All Configs", message: "This will permanently delete ALL saved configs. This cannot be undone.", icon: "🗑️", yesLabel: "Clear All", noLabel: "Cancel" });
        if (!ok) return;
        try {
            await api().clear_all();
            totalConfigs = 0;
            allConfigs = [];
            searchGen++;
            renderTable();
            renderFilters();
            toast("All configs cleared", "success");
        } catch (e) {
            toast("Clear failed", "error");
        }
    }

    let clickCtx = null;
    function playClickSound() {
        try {
            clickCtx = clickCtx || new (window.AudioContext || window.webkitAudioContext)();
            const t = clickCtx.currentTime;
            const osc = clickCtx.createOscillator();
            const gain = clickCtx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(1400, t);
            osc.frequency.exponentialRampToValueAtTime(600, t + 0.03);
            gain.gain.setValueAtTime(0.04, t);
            gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.05);
            osc.connect(gain);
            gain.connect(clickCtx.destination);
            osc.start(t);
            osc.stop(t + 0.06);
        } catch (e) {}
    }

    function playFinishChime() {
        try {
            clickCtx = clickCtx || new (window.AudioContext || window.webkitAudioContext)();
            const beep = (at, freq, dur) => {
                const osc = clickCtx.createOscillator();
                const gain = clickCtx.createGain();
                osc.type = "sine";
                osc.frequency.setValueAtTime(freq, at);
                gain.gain.setValueAtTime(0, at);
                gain.gain.linearRampToValueAtTime(0.06, at + 0.015);
                gain.gain.exponentialRampToValueAtTime(0.0001, at + dur);
                osc.connect(gain);
                gain.connect(clickCtx.destination);
                osc.start(at);
                osc.stop(at + dur + 0.02);
            };
            const t0 = clickCtx.currentTime;
            beep(t0, 880, 0.22);
            beep(t0 + 0.3, 880, 0.22);
            beep(t0 + 0.6, 1175, 0.45);
        } catch (e) {}
    }

    async function handleDeleteFiltered() {
        const query = ($("#searchInput").value || "").trim();
        const hasFilter = query || activeFilters.size || activePingFilters.size || activeCountries.size;
        if (!hasFilter) {
            toast("No active filter or search to delete", "info");
            return;
        }
        const parts = [];
        if (query) parts.push("search");
        if (activeFilters.size) parts.push(activeFilters.size + " protocol filter(s)");
        if (activeCountries.size) parts.push(activeCountries.size + " country filter(s)");
        if (activePingFilters.size) parts.push(activePingFilters.size + " ping filter(s)");
        const detail = parts.length > 0 ? "Active: " + parts.join(", ") : "current filter";
        const ok = await showConfirm({ title: "Delete Filtered Configs", message: "Delete only the rows matching the " + detail + ". All other configs stay.", icon: "🗑️", yesLabel: "Delete", noLabel: "Cancel" });
        if (!ok) return;
        try {
            const res = JSON.parse(
                await api().delete_filtered(
                    query,
                    JSON.stringify({ protocols: [...activeFilters], countries: [...activeCountries] }),
                    activePingFilters.size ? [...activePingFilters].join(",") : ""
                )
            );
            if (!res.success) throw new Error("bad");
            $("#searchInput").value = "";
            activeFilters.clear();
            activeCountries.clear();
            activePingFilters.clear();
            await loadConfigs(true);
            renderFilters();
            toast("Deleted " + (res.deleted || 0).toLocaleString() + " filtered configs", "success");
        } catch (e) {
            toast("Delete filtered failed", "error");
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
        let label = "this config";
        try {
            const row = allConfigs.find((c) => c.id === id);
            if (row && (row.name || row.server)) {
                label = (row.name || "").trim() || row.server;
            }
        } catch (e) {}
        const ok = await showConfirm({ title: "Delete Config", message: "Delete \"" + label + "\" permanently?", icon: "🗑️", yesLabel: "Delete", noLabel: "Cancel" });
        if (!ok) return;
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
        $("#fetchToggleBtn").addEventListener("click", () => {
            const wrap = $("#fetchWrap");
            const vis = wrap.style.display === "none";
            wrap.style.display = vis ? "block" : "none";
            if (vis) $("#urlInput")?.focus();
        });
        $("#importRawBtn").addEventListener("click", () => {
            const ta = $("#rawTextInput");
            const row = $("#rawSubmitRow");
            const vis = ta.style.display === "none";
            ta.style.display = vis ? "block" : "none";
            row.style.display = vis ? "block" : "none";
            if (vis) ta.focus();
        });
        $("#rawSubmitBtn").addEventListener("click", handleRawImport);
        $("#exportTextBtn").addEventListener("click", handleCopyText);
        $("#exportB64Btn").addEventListener("click", handleCopyB64);
        $("#exportFileBtn").addEventListener("click", () => handleExportFile($("#exportFormat").value));
        $("#clearAllBtn").addEventListener("click", handleClearAll);
        $("#deleteFilteredBtn").addEventListener("click", handleDeleteFiltered);
        document.addEventListener("click", () => playClickSound(), true);
        let searchTimer = null;
        $("#searchInput").addEventListener("input", () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => refreshFilteredTable(), 250);
        });
        $("#clearSearchBtn").addEventListener("click", () => {
            $("#searchInput").value = "";
            refreshFilteredTable();
            $("#searchInput").focus();
        });
        $("#cancelScanBtn").addEventListener("click", handleCancelScan);
        $("#pingAllBtn").addEventListener("click", handlePingAll);
        $("#confirmNoBtn").addEventListener("click", () => {
            $("#confirmModal").style.display = "none";
            pendingTaskWork = null;
        });
        $("#confirmYesBtn").addEventListener("click", async () => {
            $("#confirmModal").style.display = "none";
            const work = pendingTaskWork;
            pendingTaskWork = null;
            if (!work) return;
            await stopCurrentTask();
            work();
        });
        $("#confirmModal").addEventListener("click", (e) => {
            if (e.target === $("#confirmModal")) {
                $("#confirmModal").style.display = "none";
                pendingTaskWork = null;
            }
        });
        $("#prevPageBtn").addEventListener("click", () => goToPage(currentPage - 1));
        $("#nextPageBtn").addEventListener("click", () => goToPage(currentPage + 1));
        const firstBtn = $("#firstPageBtn");
        if (firstBtn) firstBtn.addEventListener("click", goToFirstRow);
        const lastBtn = $("#lastPageBtn");
        if (lastBtn) lastBtn.addEventListener("click", goToLastRow);
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
            const pingBtn = e.target.closest(".ping-btn");
            if (pingBtn) {
                handlePing(pingBtn);
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
            refreshFilteredTable(item);
        });

        $("#pingFilters").addEventListener("click", (e) => {
            const item = e.target.closest(".filter-item");
            if (!item) return;
            const ping = item.dataset.ping;
            if (ping === "__all__") {
                activePingFilters.clear();
            } else {
                if (activePingFilters.has(ping)) {
                    activePingFilters.delete(ping);
                } else {
                    activePingFilters.add(ping);
                }
            }
            refreshFilteredTable(item);
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
            refreshFilteredTable(item);
        });

        $("#themeToggle").addEventListener("click", () => {
            document.body.classList.toggle("dark");
            const isDark = document.body.classList.contains("dark");
            $("#themeToggle").textContent = isDark ? "🌙" : "☀️";
        });

        $("#welcomeClose").addEventListener("click", closeWelcome);

        $("#aboutBtn").addEventListener("click", () => {
            showWelcome();
        });

        window.addEventListener("resize", () => { recalcPageSize(); });

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
            if (e.key === "Escape") {
                if ($("#progressOverlay").style.display === "flex") {
                    e.preventDefault();
                    handleCancelScan();
                }
                if (document.getElementById("aboutModal").style.display === "flex") {
                    document.getElementById("aboutModal").style.display = "none";
                }
            }
            if (e.ctrlKey && e.key === "f") {
                e.preventDefault();
                const searchInput = document.getElementById("searchInput");
                searchInput.focus();
                searchInput.select();
            }
            if (e.ctrlKey && e.key === "r") {
                e.preventDefault();
                handleScanWeb();
            }
            if (e.ctrlKey && e.key === "l") {
                e.preventDefault();
                document.getElementById("urlInput").focus();
            }
            if (e.ctrlKey && e.key === "e") {
                e.preventDefault();
                handleExportConfigs();
            }
            if (e.ctrlKey && e.key === "i") {
                e.preventDefault();
                handleImportFile();
            }
            if (e.ctrlKey && e.key === "d") {
                e.preventDefault();
                handleDetails();
            }
        });

        document.addEventListener("keydown", handleTableKeys);

        document.getElementById("aboutClose").addEventListener("click", () => {
            document.getElementById("aboutModal").style.display = "none";
        });
        document.getElementById("aboutCloseBtn").addEventListener("click", () => {
            document.getElementById("aboutModal").style.display = "none";
        });
    }

    function handleCancelScan() {
        currentTask = null;
        const wasPing = pingAllRunning;
        if (wasPing) {
            pingAllCancelled = true;
            stopPingPoller();
        }
        api()
            .cancel()
            .then(() => {
                if (wasPing) {
                    pingAllRunning = false;
                    pingAllCancelled = false;
                    updatePingAllBtnState();
                }
                hideProgress();
                if (wasPing) {
                    resetPingUiState();
                } else {
                    clearPingResults();
                }
            })
            .catch(() => {
                hideProgress();
            });
    }

    function openWelcome() {
        const ov = $("#welcomeOverlay");
        ov.style.display = "flex";
        ov.classList.add("visible");
    }

    function closeWelcome() {
        const ov = $("#welcomeOverlay");
        ov.classList.remove("visible");
        setTimeout(() => {
            ov.style.display = "none";
            api().maximize_window();
        }, 260);
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

    async function loadPingResults() {
        try {
            const res = JSON.parse(await api().get_ping_map());
            const map = res && res.map;
            if (map) {
                const keys = Object.keys(map);
                for (const k of keys) latencyResults.set(k, { ms: map[k], ok: map[k] >= 0 });
            }
        } catch (e) {}
        renderTable();
        renderPingFilters();
    }

    async function applySessionPings() {
        try {
            const res = JSON.parse(await api().get_ping_session());
            const map = res && res.map;
            if (map) {
                const keys = Object.keys(map);
                for (const k of keys) latencyResults.set(k, { ms: map[k], ok: map[k] >= 0 });
            }
        } catch (e) {}
        renderTable();
        renderPingFilters();
    }

    waitForApi(() => {
        initEvents();
        loadConfigs();
        renderFilters();
        loadPingResults();
    });
})();
