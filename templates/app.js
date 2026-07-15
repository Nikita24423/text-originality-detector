const docsList = document.getElementById("docs-list");
const docsCount = document.getElementById("docs-count");
const refreshBtn = document.getElementById("refresh-docs-btn");
const uploadBtn = document.getElementById("upload-btn");
const analyzeBtn = document.getElementById("analyze-btn");
const docTitle = document.getElementById("doc-title");
const docText = document.getElementById("doc-text");
const docFile = document.getElementById("doc-file");
const emptyState = document.getElementById("empty-state");
const results = document.getElementById("results");
const scoreCards = document.getElementById("score-cards");
const summaryEl = document.getElementById("summary");
const borrowingsList = document.getElementById("borrowings-list");
const aiSection = document.getElementById("ai-section");
const aiCards = document.getElementById("ai-cards");
const queueStatus = document.getElementById("queue-status");

let selectedId = null;
let documentsCache = [];

function formatApiError(payload) {
    const detail = payload?.detail ?? payload?.error;
    if (Array.isArray(detail)) {
        return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
    }
    return detail || "Неизвестная ошибка";
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function setBadge(id, text) {
    const badge = document.getElementById(id);
    if (!badge) return;
    if (text) {
        badge.textContent = text;
        badge.classList.remove("hidden");
    } else {
        badge.textContent = "";
        badge.classList.add("hidden");
    }
}

function setQueueStatus(text) {
    if (!queueStatus) return;
    if (text) {
        queueStatus.textContent = text;
        queueStatus.classList.remove("hidden");
    } else {
        queueStatus.textContent = "";
        queueStatus.classList.add("hidden");
    }
}

function setLoading(loading, label) {
    analyzeBtn.disabled = loading || !selectedId;
    analyzeBtn.querySelector(".btn-text").textContent =
        loading ? (label || "Анализ...") : "Проверить выбранную";
    analyzeBtn.querySelector(".btn-loader").classList.toggle("hidden", !loading);
    uploadBtn.disabled = loading;
    refreshBtn.disabled = loading;
}

function showError(msg) {
    let el = document.getElementById("error-msg");
    if (!el) {
        el = document.createElement("div");
        el.id = "error-msg";
        el.className = "error-msg";
        results.parentElement.insertBefore(el, results);
    }
    el.textContent = msg;
    el.classList.remove("hidden");
    emptyState.classList.add("hidden");
    results.classList.add("hidden");
}

function hideError() {
    const el = document.getElementById("error-msg");
    if (el) el.classList.add("hidden");
}

function statusLabel(status) {
    const map = {
        pending: "ожидает",
        queued: "в очереди",
        processing: "анализ…",
        done: "готово",
        failed: "ошибка",
    };
    return map[status] || status || "—";
}

function formatPct(value) {
    if (value == null || Number.isNaN(Number(value))) return "—";
    return `${Number(value).toFixed(1)}%`;
}

function selectDocument(id) {
    selectedId = id;
    analyzeBtn.disabled = !selectedId;
    docsList.querySelectorAll(".doc-item").forEach((el) => {
        el.classList.toggle("active", Number(el.dataset.id) === id);
    });
}

function renderDocsList(docs) {
    documentsCache = docs || [];
    docsCount.textContent = `Всего работ: ${documentsCache.length}`;

    if (!documentsCache.length) {
        docsList.innerHTML = `<p class="hint">База пуста. Загрузите первую работу ниже.</p>`;
        selectedId = null;
        analyzeBtn.disabled = true;
        return;
    }

    docsList.innerHTML = documentsCache.map((d) => {
        const title = escapeHtml(d.title || d.filename || `Документ #${d.id}`);
        const meta = [
            `#${d.id}`,
            d.word_count != null ? `${d.word_count} слов` : null,
            d.file_format || null,
            statusLabel(d.analytics_status),
        ].filter(Boolean).join(" · ");
        const score = d.originality_percent != null
            ? `<span class="doc-score">${formatPct(d.originality_percent)}</span>`
            : "";
        return `
            <button type="button" class="doc-item ${selectedId === d.id ? "active" : ""}" data-id="${d.id}">
                <span class="doc-title">${title}</span>
                <span class="doc-meta">${escapeHtml(meta)}</span>
                ${score}
            </button>
        `;
    }).join("");

    docsList.querySelectorAll(".doc-item").forEach((btn) => {
        btn.addEventListener("click", () => selectDocument(Number(btn.dataset.id)));
    });

    if (selectedId && !documentsCache.some((d) => d.id === selectedId)) {
        selectedId = null;
        analyzeBtn.disabled = true;
    } else if (selectedId) {
        selectDocument(selectedId);
    }
}

async function loadDocuments() {
    try {
        const resp = await fetch("/api/analytics/documents");
        const data = await resp.json();
        if (!resp.ok) {
            docsCount.textContent = formatApiError(data);
            return;
        }
        renderDocsList(data.documents || []);
    } catch (err) {
        docsCount.textContent = "Не удалось загрузить список. Запущен ли сервер?";
    }
}

document.querySelectorAll(".file-btn[data-target]").forEach((btn) => {
    btn.addEventListener("click", () => {
        const input = document.getElementById(btn.dataset.target);
        if (input) input.click();
    });
});

docFile.addEventListener("change", () => {
    const file = docFile.files[0];
    if (!file) {
        setBadge("doc-file-badge", "");
        return;
    }
    setBadge("doc-file-badge", file.name);
    if (!docTitle.value.trim()) {
        docTitle.value = file.name.replace(/\.[^.]+$/, "");
    }
});

refreshBtn.addEventListener("click", () => loadDocuments());

uploadBtn.addEventListener("click", async () => {
    const text = docText.value.trim();
    const hasFile = docFile.files && docFile.files.length > 0;
    if (!text && !hasFile) {
        showError("Введите текст или прикрепите файл.");
        return;
    }

    hideError();
    uploadBtn.disabled = true;
    uploadBtn.querySelector(".btn-text").textContent = "Сохранение…";

    try {
        const formData = new FormData();
        formData.append("title", docTitle.value.trim());
        formData.append("text", text);
        if (hasFile) formData.append("file", docFile.files[0]);

        const resp = await fetch("/api/analytics/documents", { method: "POST", body: formData });
        const data = await resp.json();
        if (!resp.ok) {
            showError(formatApiError(data));
            return;
        }

        docText.value = "";
        docTitle.value = "";
        docFile.value = "";
        setBadge("doc-file-badge", "");
        selectedId = data.document_id;
        await loadDocuments();
        setQueueStatus(data.message || `Документ #${data.document_id} сохранён`);
    } catch (err) {
        showError("Не удалось сохранить документ.");
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.querySelector(".btn-text").textContent = "Сохранить в БД";
    }
});

analyzeBtn.addEventListener("click", runAnalysis);

async function runAnalysis() {
    if (!selectedId) {
        showError("Сначала выберите работу из списка.");
        return;
    }

    setLoading(true);
    hideError();
    setQueueStatus(`Запуск анализа документа #${selectedId}…`);

    try {
        const createResp = await fetch(`/api/analytics/documents/${selectedId}/analyze`, {
            method: "POST",
        });
        const created = await createResp.json();
        if (!createResp.ok) {
            showError(formatApiError(created));
            return;
        }

        if (created.status === "done" && created.result) {
            await showBorrowings(selectedId);
            return;
        }

        const taskHint = created.task_id ? ` · задача #${created.task_id}` : "";
        setQueueStatus(`Документ #${selectedId}: в очереди${taskHint}`);
        const ok = await pollAnalytics(selectedId);
        if (!ok) return;
        await showBorrowings(selectedId);
        await loadDocuments();
    } catch (err) {
        showError("Не удалось связаться с сервером. Запущен ли API и ML-воркер?");
    } finally {
        setLoading(false);
        setQueueStatus("");
    }
}

async function pollAnalytics(documentId, intervalMs = 3000, maxAttempts = 1800) {
    const labels = {
        pending: "ожидание",
        queued: "в очереди",
        processing: "обработка",
        done: "готово",
        failed: "ошибка",
    };

    for (let i = 0; i < maxAttempts; i++) {
        const resp = await fetch(`/api/analytics/documents/${documentId}/status`);
        const data = await resp.json();
        if (!resp.ok) {
            showError(formatApiError(data));
            return false;
        }

        const st = data.analytics_status || "pending";
        if (st === "failed") {
            showError(data.analytics_error || "Ошибка анализа.");
            return false;
        }
        if (st === "done") {
            return true;
        }

        const mins = Math.floor((i * intervalMs) / 60000);
        setQueueStatus(
            `Документ #${documentId}: ${labels[st] || st}… (${mins} мин)`
        );
        await sleep(intervalMs);
    }

    showError(
        "Превышено время ожидания (~90 мин). " +
        "Проверьте статус документа в списке или запустите анализ снова."
    );
    return false;
}

async function showBorrowings(documentId) {
    const resp = await fetch(`/api/analytics/documents/${documentId}/borrowings`);
    const data = await resp.json();
    if (!resp.ok) {
        showError(formatApiError(data));
        return;
    }
    renderBorrowings(data);
}

function renderBorrowings(data) {
    emptyState.classList.add("hidden");
    results.classList.remove("hidden");
    hideError();

    const title = data.title || `Документ #${data.document_id}`;
    scoreCards.innerHTML = `
        <div class="score-card originality">
            <div class="value">${formatPct(data.originality_percent)}</div>
            <div class="label">Оригинальность</div>
        </div>
        <div class="score-card borrowing">
            <div class="value">${formatPct(data.deep_borrow_percent_ml)}</div>
            <div class="label">Глубокое заимствование</div>
        </div>
        <div class="score-card borrowing">
            <div class="value">${formatPct(data.copy_percent_ml)}</div>
            <div class="label">Копирование</div>
        </div>
        <div class="score-card risk">
            <div class="value">${formatPct(data.plagiarism_percent_ml)}</div>
            <div class="label">Всего заимствований</div>
        </div>
    `;

    summaryEl.textContent =
        `${title}. Найдено совпадений с другими работами: ${data.borrowings_count || 0}. ` +
        (data.analytics_status === "done"
            ? "Анализ завершён."
            : `Статус: ${statusLabel(data.analytics_status)}.`);

    if (data.ai_percent_ml != null) {
        aiSection.classList.remove("hidden");
        aiCards.innerHTML = `
            <div class="score-card borrowing">
                <div class="value">${formatPct(data.ai_percent_ml)}</div>
                <div class="label">Вероятность ИИ</div>
            </div>
        `;
    } else {
        aiSection.classList.add("hidden");
    }

    const borrowings = data.borrowings || [];
    if (!borrowings.length) {
        borrowingsList.innerHTML =
            `<p class="hint">Совпадений с другими работами в БД не найдено — оригинальность 100% или корпус пуст.</p>`;
        return;
    }

    borrowingsList.innerHTML = borrowings.map((b, idx) => {
        const srcTitle = escapeHtml(
            b.target_title || b.target_filename || `Документ #${b.target_document_id}`
        );
        const fragments = (b.matched_fragments || []).filter((f) => f.is_borrowing !== false);
        const fragsHtml = fragments.length
            ? fragments.map((f) => `
                <div class="segment-card risk-${escapeHtml(f.risk_level || "medium")}">
                    <div class="segment-header">
                        <span>Фрагмент ${(f.segment_index ?? 0) + 1}${
                            f.match_type
                                ? ` · ${f.match_type === "copy" ? "копирование" : "глубокое"}`
                                : ""
                        }</span>
                        <span class="segment-badge badge-${escapeHtml(f.risk_level || "medium")}">
                            ${escapeHtml(f.risk_label || "")} · ${formatPct(f.combined_percent)}
                        </span>
                    </div>
                    <div class="segment-text">${escapeHtml(f.segment_text)}</div>
                    ${f.source_text
                        ? `<div class="segment-source"><strong>В источнике:</strong> ${escapeHtml(f.source_text)}</div>`
                        : ""}
                    <div class="score-bar-group">
                        <div class="score-bar-item">
                            <div class="score-bar-label">Глубокое: ${formatPct(f.deep_borrow_percent)}</div>
                            <div class="score-bar">
                                <div class="score-bar-fill fill-bm25" style="width:${Number(f.deep_borrow_percent) || 0}%"></div>
                            </div>
                        </div>
                        <div class="score-bar-item">
                            <div class="score-bar-label">Копирование: ${formatPct(f.copy_percent)}</div>
                            <div class="score-bar">
                                <div class="score-bar-fill fill-tfidf" style="width:${Number(f.copy_percent) || 0}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `).join("")
            : `<p class="hint">Фрагменты не сохранены — сходство ${formatPct(b.similarity_percent)}</p>`;

        return `
            <div class="borrowing-block">
                <div class="borrowing-header">
                    <strong>${idx + 1}. ${srcTitle}</strong>
                    <span class="doc-score">${formatPct(b.similarity_percent)}</span>
                </div>
                <p class="hint">id #${b.target_document_id} · копирование ${formatPct(b.copy_percent)} · глубокое ${formatPct(b.deep_borrow_percent)}</p>
                ${fragsHtml}
            </div>
        `;
    }).join("");
}

loadDocuments();
