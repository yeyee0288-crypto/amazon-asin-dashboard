(function() {
  var LS_KEY = "amazon_asin_dashboard_rows_v2";
  var LOG_LS_KEY = "amazon_asin_dashboard_operation_logs_v1";
  var LAST_RESULTS_LS_KEY = "amazon_asin_dashboard_last_results_v1";

  var inputRows = document.getElementById("input-rows");
  var intakeListBody = document.getElementById("intake-list-body");
  var intakeToggle = document.getElementById("intake-toggle");
  var inputPageSummary = document.getElementById("input-page-summary");
  var inputPageSizeSelect = document.getElementById("input-page-size");
  var inputPrevPage = document.getElementById("input-prev-page");
  var inputNextPage = document.getElementById("input-next-page");
  var pageSizePresetButtons = document.querySelectorAll("[data-page-size-preset]");
  var inputCategoryFilter = document.getElementById("input-category-filter");
  var inputNoteFilter = document.getElementById("input-note-filter");
  var inputAsinHeaderFilter = document.getElementById("input-asin-header-filter");
  var inputCategoryHeaderFilter = document.getElementById("input-category-header-filter");
  var inputNoteHeaderFilter = document.getElementById("input-note-header-filter");
  var inputPriceHeaderFilter = document.getElementById("input-price-header-filter");
  var inputHeaderFilters = [
    inputAsinHeaderFilter,
    inputCategoryHeaderFilter,
    inputNoteHeaderFilter,
    inputPriceHeaderFilter
  ].filter(Boolean);
  var inputFilterClear = document.getElementById("input-filter-clear");
  var inputFilterSummary = document.getElementById("input-filter-summary");
  var addRowBtn = document.getElementById("add-row-btn");
  var pasteBtn = document.getElementById("paste-btn");
  var importBtn = document.getElementById("import-btn");
  var importFile = document.getElementById("import-file");
  var inventoryImportBtn = document.getElementById("inventory-import-btn");
  var skuMapImportBtn = document.getElementById("sku-map-import-btn");
  var erpAutoUpdateBtn = document.getElementById("erp-auto-update-btn");
  var erpConfigSaveBtn = document.getElementById("erp-config-save-btn");
  var erpUsernameInput = document.getElementById("erp-username");
  var erpPasswordInput = document.getElementById("erp-password");
  var erpTargetUrlInput = document.getElementById("erp-target-url");
  var erpDownloadTargetInput = document.getElementById("erp-download-target");
  var erpAutoStatus = document.getElementById("erp-auto-status");
  var inventoryFile = document.getElementById("inventory-file");
  var skuMapFile = document.getElementById("sku-map-file");
  var inventoryStatusCard = document.getElementById("inventory-status-card");
  var skuMapStatusCard = document.getElementById("sku-map-status-card");
  var inventoryPersonFilter = document.getElementById("inventory-person-filter");
  var inventoryPersonFilterNote = document.getElementById("inventory-person-filter-note");
  var startBtn = document.getElementById("start-btn");
  var stopBtn = document.getElementById("stop-btn");
  var saveStatus = document.getElementById("save-status");
  var msgBox = document.getElementById("msg-box");
  var resultsArea = document.getElementById("results-area");
  var resultsGroups = document.getElementById("results-groups");
  var groupFilters = document.getElementById("group-filters");
  var summaryBar = document.getElementById("summary-bar");
  var exportBtn = document.getElementById("export-btn");
  var retryFailedBtn = document.getElementById("retry-failed-btn");
  var progressArea = document.getElementById("progress-area");
  var progressBar = document.getElementById("progress-bar");
  var progressText = document.getElementById("progress-text");
  var groupPreview = document.getElementById("group-preview");
  var logToggle = document.getElementById("log-toggle");
  var logBody = document.getElementById("log-body");
  var logEntries = document.getElementById("log-entries");
  var logCount = document.getElementById("log-count");
  var dashboardBaseline = document.getElementById("dashboard-baseline");
  var dashboardPanel = document.getElementById("dashboard-panel");
  var dashTotal = document.getElementById("dash-total");
  var dashChanged = document.getElementById("dash-changed");
  var dashNew = document.getElementById("dash-new");
  var dashRemoved = document.getElementById("dash-removed");
  var dashOversell = document.getElementById("dash-oversell");
  var dashNearOversell = document.getElementById("dash-near-oversell");
  var dashReplenish = document.getElementById("dash-replenish");
  var dashQuoteRisk = document.getElementById("dash-quote-risk");
  var comparisonCount = document.getElementById("comparison-count");
  var comparisonMiniSummary = document.getElementById("comparison-mini-summary");
  var comparisonList = document.getElementById("comparison-list");

  var statTotal = document.getElementById("stat-total");
  var statSuccess = document.getElementById("stat-success");
  var statWarning = document.getElementById("stat-warning");
  var statFail = document.getElementById("stat-fail");

  var isScraping = false;
  var currentSessionId = null;
  var evtSource = null;
  var saveTimer = null;
  var currentGroupFilter = "全部";
  var currentStatusFilter = "全部状态";
  var currentErpRiskFilter = "全部ERP库存";
  var currentBusinessRiskFilter = "全部业务风险";
  var currentPriceCompareFilter = "all";
  var collapsedGroups = {};
  var sessionResults = [];
  var logGroups = [];
  var currentLogGroup = null;
  var logVisible = false;
  var logSaveTimer = null;
  var inputCurrentPage = 1;
  var inputPageSize = 20;
  var intakeCollapsed = false;
  var previousResults = [];
  var previousResultsTime = "";
  var previousResultsReady = null;
  var comparisonFinalized = false;
  var dashboardFilter = "all";
  var collapsedComparisons = {};

  function esc(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function createRow(data) {
    data = data || { asin: "", category: "", name: "", price: "" };
    var row = document.createElement("tr");
    row.innerHTML =
      '<td class="idx-cell"></td>' +
      '<td><input type="text" class="asin-input" placeholder="B0XXXXXXXX 或 https://www.amazon.com/dp/..." value="' + esc(data.asin) + '"></td>' +
      '<td><input type="text" class="category-input" placeholder="店铺链接名，留空则按链接自动归组" value="' + esc(data.category) + '"></td>' +
      '<td><input type="text" class="name-input" placeholder="ERP SKU" value="' + esc(data.name) + '"></td>' +
      '<td><input type="text" class="price-input" placeholder="19.99" value="' + esc(data.price) + '"></td>' +
      '<td><button type="button" class="btn-del" title="删除">×</button></td>';

    row.querySelector(".btn-del").addEventListener("click", function() {
      row.remove();
      renumberRows();
      scheduleSave();
      updateGroupPreview();
    });

    row.querySelectorAll("input").forEach(function(input) {
      input.addEventListener("input", function() {
        scheduleSave();
        updateInputPagination();
        updateGroupPreview();
      });
    });

    row.querySelector(".asin-input").addEventListener("keydown", function(event) {
      if (event.key === "Enter" && !event.ctrlKey && !event.metaKey) {
        event.preventDefault();
        addRow();
        var rows = inputRows.querySelectorAll("tr");
        var nextRow = rows[rows.length - 1];
        if (nextRow) {
          nextRow.querySelector(".asin-input").focus();
        }
      }
    });

    inputRows.appendChild(row);
    renumberRows();
  }

  function addRow(data) {
    createRow(data);
    inputCurrentPage = Math.max(1, Math.ceil(inputRows.children.length / inputPageSize));
    updateInputPagination();
    scheduleSave();
    updateGroupPreview();
  }

  function renumberRows() {
    inputRows.querySelectorAll("tr").forEach(function(row, index) {
      row.querySelector(".idx-cell").textContent = index + 1;
    });
    updateInputPagination();
  }

  function updateInputPagination() {
    var rows = Array.prototype.slice.call(inputRows.querySelectorAll("tr"));
    var filteredRows = rows.filter(rowMatchesInputFilters);
    var totalRows = filteredRows.length;
    var totalPages = Math.max(1, Math.ceil(totalRows / inputPageSize));
    inputCurrentPage = Math.min(Math.max(1, inputCurrentPage), totalPages);
    var startIndex = (inputCurrentPage - 1) * inputPageSize;
    var endIndex = Math.min(startIndex + inputPageSize, totalRows);

    rows.forEach(function(row) {
      row.hidden = true;
    });
    filteredRows.forEach(function(row, index) {
      row.hidden = index < startIndex || index >= endIndex;
    });

    inputPageSummary.textContent = totalRows
      ? "第 " + inputCurrentPage + " / " + totalPages + " 页 · 显示 " + (startIndex + 1) + "-" + endIndex + " · 共 " + totalRows + " 行"
      : (rows.length ? "当前筛选无匹配行" : "暂无录入行");
    updateInputFilterSummary(rows.length, totalRows);
    inputPrevPage.disabled = inputCurrentPage <= 1;
    inputNextPage.disabled = inputCurrentPage >= totalPages;
  }

  function normalizedFilterValue(value) {
    return String(value || "").trim().toLowerCase();
  }

  function getInputFilters() {
    return {
      asin: normalizedFilterValue(inputAsinHeaderFilter ? inputAsinHeaderFilter.value : ""),
      category: normalizedFilterValue(inputCategoryFilter ? inputCategoryFilter.value : ""),
      categoryHeader: normalizedFilterValue(inputCategoryHeaderFilter ? inputCategoryHeaderFilter.value : ""),
      note: normalizedFilterValue(inputNoteFilter ? inputNoteFilter.value : ""),
      noteHeader: normalizedFilterValue(inputNoteHeaderFilter ? inputNoteHeaderFilter.value : ""),
      price: normalizedFilterValue(inputPriceHeaderFilter ? inputPriceHeaderFilter.value : "")
    };
  }

  function rowMatchesInputFilters(row) {
    var filters = getInputFilters();
    var asin = normalizedFilterValue(row.querySelector(".asin-input").value);
    var category = normalizedFilterValue(row.querySelector(".category-input").value);
    var note = normalizedFilterValue(row.querySelector(".name-input").value);
    var price = normalizedFilterValue(row.querySelector(".price-input").value);
    if (filters.asin && asin.indexOf(filters.asin) === -1) {
      return false;
    }
    if (filters.category && category.indexOf(filters.category) === -1) {
      return false;
    }
    if (filters.categoryHeader && category.indexOf(filters.categoryHeader) === -1) {
      return false;
    }
    if (filters.note && note.indexOf(filters.note) === -1) {
      return false;
    }
    if (filters.noteHeader && note.indexOf(filters.noteHeader) === -1) {
      return false;
    }
    if (filters.price && price.indexOf(filters.price) === -1) {
      return false;
    }
    return true;
  }

  function updateInputFilterSummary(totalRows, filteredRows) {
    if (!inputFilterSummary) {
      return;
    }
    var filters = getInputFilters();
    var active = !!(filters.asin || filters.category || filters.categoryHeader || filters.note || filters.noteHeader || filters.price);
    inputFilterSummary.textContent = active
      ? "已筛选 " + filteredRows + " / " + totalRows + " 行，可直接修改匹配行"
      : "显示全部 " + totalRows + " 行";
    if (inputFilterClear) {
      inputFilterClear.hidden = !active;
    }
  }

  function updateInputFilters() {
    inputCurrentPage = 1;
    updateInputPagination();
  }

  function applyInputPageSize(value) {
    var nextSize = value === undefined ? inputPageSizeSelect.value : value;
    inputPageSize = Math.min(500, Math.max(1, Math.floor(Number(nextSize) || 20)));
    inputPageSizeSelect.value = String(inputPageSize);
    inputCurrentPage = 1;
    updateInputPagination();
  }

  function setIntakeCollapsed(collapsed) {
    intakeCollapsed = collapsed;
    intakeListBody.hidden = collapsed;
    intakeToggle.textContent = collapsed ? "展开清单" : "收起清单";
    intakeToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  }

  function isValidAsin(value) {
    var text = String(value || "").trim().toUpperCase();
    return /^[A-Z0-9]{10}$/.test(text) && /\d/.test(text);
  }

  function extractAsin(text) {
    text = String(text || "").trim();
    if (isValidAsin(text)) {
      return text.toUpperCase();
    }
    var markdownMatch = text.match(/\[([A-Z0-9]{10})\]\((https?:\/\/[^)\s]+)\)/i);
    if (markdownMatch && isValidAsin(markdownMatch[1])) {
      return markdownMatch[1].toUpperCase();
    }
    if (!/^https?:\/\//i.test(text)) {
      var standaloneMatch = text.match(/(^|[^A-Z0-9])([A-Z0-9]{10})(?![A-Z0-9])/i);
      if (standaloneMatch && isValidAsin(standaloneMatch[2])) {
        return standaloneMatch[2].toUpperCase();
      }
    }
    var match = text.match(/\/(?:dp|gp\/product|product|ASIN)\/([A-Z0-9]{10})/i);
    return match && isValidAsin(match[1]) ? match[1].toUpperCase() : null;
  }

  function extractUrl(raw) {
    var text = String(raw || "").trim();
    var markdownMatch = text.match(/\[[^\]]+\]\((https?:\/\/[^)\s]+)\)/i);
    if (markdownMatch) {
      return markdownMatch[1];
    }
    var urlMatch = text.match(/https?:\/\/[^\s)\]]+/i);
    return urlMatch ? urlMatch[0] : "";
  }

  function normalizeUrl(raw) {
    try {
      var url = new URL((extractUrl(raw) || raw).trim());
      var pathname = url.pathname.replace(/\/+$/, "") || "/";
      return url.origin.toLowerCase() + pathname;
    } catch (error) {
      return raw.trim();
    }
  }

  function getSourceType(raw) {
    return extractUrl(raw) ? "url" : "asin";
  }

  function autoCategory(raw) {
    var sourceType = getSourceType(raw);
    if (sourceType !== "url") {
      return "手动 ASIN";
    }
    try {
      var url = new URL(extractUrl(raw) || raw.trim());
      var pieces = url.pathname.split("/").filter(Boolean);
      return pieces.length ? (url.hostname + " / " + pieces[pieces.length - 1]) : url.hostname;
    } catch (error) {
      return "链接归组";
    }
  }

  function parsePrice(raw) {
    if (!raw) {
      return null;
    }
    var value = parseFloat(String(raw).replace(/[^0-9.]/g, ""));
    return isNaN(value) ? null : value;
  }

  function applyPreviousResultsPayload(saved) {
    if (saved && Array.isArray(saved.results)) {
      previousResults = saved.results;
      previousResultsTime = saved.time || "";
      try {
        localStorage.setItem(LAST_RESULTS_LS_KEY, JSON.stringify({
          time: previousResultsTime,
          results: previousResults
        }));
      } catch (error) {}
      return true;
    }
    return false;
  }

  function loadPreviousResults() {
    try {
      var saved = JSON.parse(localStorage.getItem(LAST_RESULTS_LS_KEY) || "null");
      applyPreviousResultsPayload(saved);
    } catch (error) {}
  }

  function loadPreviousResultsFromServer() {
    previousResultsReady = fetch("/api/previous-results")
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data && Array.isArray(data.results) && data.results.length) {
          applyPreviousResultsPayload(data);
          renderDashboard();
          renderResults();
        } else if (previousResults.length) {
          savePreviousResultsToServer({
            time: previousResultsTime || new Date().toLocaleString("zh-CN"),
            results: previousResults
          });
        }
      })
      .catch(function() {})
      .finally(function() {
        previousResultsReady = null;
      });
    return previousResultsReady;
  }

  function savePreviousResultsToServer(payload) {
    return fetch("/api/previous-results", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).catch(function() {});
  }

  function saveCurrentResultsAsPrevious() {
    if (!sessionResults.length) {
      return;
    }
    var payload = {
      time: new Date().toLocaleString("zh-CN"),
      results: sessionResults
    };
    try {
      localStorage.setItem(LAST_RESULTS_LS_KEY, JSON.stringify(payload));
    } catch (error) {}
    savePreviousResultsToServer(payload);
  }

  function resultComparison(result) {
    var previous = previousResults.find(function(item) { return item.asin === result.asin; });
    if (!previous) {
      return { type: "new", label: "新增", detail: "上次未出现" };
    }

    var changes = [];
    var previousErpRisk = normalizedErpRiskLabel(previous);
    var currentErpRisk = normalizedErpRiskLabel(result);
    var previousBusinessRisk = businessRiskInfo(previous);
    var currentBusinessRisk = businessRiskInfo(result);
    var erpRecoveredToNormal = previousErpRisk !== currentErpRisk && currentErpRisk === "ERP库存正常";
    var oldPrice = parsePrice(previous.price);
    var newPrice = parsePrice(result.price);
    if (oldPrice !== newPrice) {
      var oldLabel = previous.price || "无价格";
      var newLabel = result.price || "无价格";
      changes.push("价格 " + oldLabel + " → " + newLabel);
    }
    if (previous.status !== result.status && !erpRecoveredToNormal) {
      changes.push("状态 " + statusLabel(previous) + " → " + statusLabel(result));
    }
    if ((previous.brand || "") !== (result.brand || "")) {
      changes.push("品牌 " + (previous.brand || "-") + " → " + (result.brand || "-"));
    }
    if ((previous.seller || "") !== (result.seller || "")) {
      changes.push("店铺 " + (previous.seller || "-") + " → " + (result.seller || "-"));
    }
    if ((previous.stock_left || "") !== (result.stock_left || "")) {
      changes.push("库存 " + stockText(previous) + " → " + stockText(result));
    }
    if ((previous.erp_sku_stock || "") !== (result.erp_sku_stock || "") && currentErpRisk !== "ERP库存正常") {
      changes.push("ERP库存 " + erpStockText(previous) + " → " + erpStockText(result));
    }
    if (previousErpRisk !== currentErpRisk && currentErpRisk !== "ERP库存正常") {
      changes.push("ERP风险 " + previousErpRisk + " → " + currentErpRisk);
    }
    return changes.length
      ? { type: "changed", label: "有变化", detail: changes.join("；") }
      : { type: "same", label: "无变化", detail: "与上次一致" };
  }

  function isWarningStatus(status) {
    return status === "out_of_stock" || status === "needs_review" || status === "variant" || status === "price_warn" || status === "price_compare" || status === "low_stock" || status === "erp_out_of_stock" || status === "erp_low_stock" || status === "erp_substitute_available";
  }

  function stockText(result) {
    if (!result) return "-";
    if (result.stock_left) return "仅剩 " + result.stock_left + " 件";
    if (result.stock_message) return result.stock_message;
    return "-";
  }

  function erpStockText(result) {
    if (!result || result.erp_sku_stock === "" || result.erp_sku_stock === null || result.erp_sku_stock === undefined) {
      return "-";
    }
    var own = Number(result.erp_sku_stock || 0);
    var substitute = Number(result.erp_substitute_stock || 0);
    var total = result.erp_total_stock === "" || result.erp_total_stock === null || result.erp_total_stock === undefined
      ? own + substitute
      : Number(result.erp_total_stock || 0);
    return own + " + " + substitute + " = " + total;
  }

  function substituteText(result) {
    if (!result || result.erp_substitute_stock === "" || result.erp_substitute_stock === null || result.erp_substitute_stock === undefined) {
      return "-";
    }
    return "可替代 " + result.erp_substitute_stock;
  }

  function comparisonMeta(result) {
    var note = result.note ? '<span class="comparison-note" title="ERP SKU">' + esc(result.note) + "</span>" : "";
    var name = esc(result.brand || result.title || "商品");
    return note + "<span>" + name + "</span>";
  }

  function renderDashboard() {
    var success = sessionResults.filter(function(result) { return result.status === "success"; }).length;
    var warning = sessionResults.filter(function(result) {
      return isWarningStatus(result.status);
    }).length;
    var failed = Math.max(0, sessionResults.length - success - warning);
    var scrapedSuccessfully = sessionResults.length - failed;
    var businessRiskMap = buildBusinessRiskCounts(sessionResults);
    var comparisons = sessionResults.map(function(result) {
      return { result: result, comparison: safeResultComparison(result) };
    });
    var changed = comparisons.filter(function(item) { return item.comparison.type === "changed"; });
    var added = comparisons.filter(function(item) { return item.comparison.type === "new"; });
    var currentAsins = {};
    sessionResults.forEach(function(result) { currentAsins[result.asin] = true; });
    var removed = comparisonFinalized ? previousResults.filter(function(result) { return !currentAsins[result.asin]; }) : [];
    var changeItems = changed.concat(added);

    dashTotal.textContent = String(sessionResults.length);
    dashChanged.textContent = String(changed.length);
    dashNew.textContent = String(added.length);
    dashRemoved.textContent = String(removed.length);
    if (dashOversell) dashOversell.textContent = String((businessRiskMap.oversell || {}).count || 0);
    if (dashNearOversell) dashNearOversell.textContent = String((businessRiskMap.near_oversell || {}).count || 0);
    if (dashReplenish) dashReplenish.textContent = String((businessRiskMap.replenish_opportunity || {}).count || 0);
    if (dashQuoteRisk) dashQuoteRisk.textContent = String((businessRiskMap.quote_abnormal || {}).count || 0);
    dashboardBaseline.textContent = previousResults.length
      ? "对比基准：" + (previousResultsTime || "上一次完整抓取") + " · " + previousResults.length + " 个 ASIN"
      : "暂无上次抓取数据，本次将建立对比基准";

    var rate = sessionResults.length ? Math.round((scrapedSuccessfully / sessionResults.length) * 100) : 0;
    donutRate.textContent = rate + "%";
    var successDeg = sessionResults.length ? (scrapedSuccessfully / sessionResults.length) * 360 : 0;
    statusDonut.style.background = sessionResults.length
      ? "conic-gradient(var(--success) 0deg " + successDeg + "deg, var(--danger) " + successDeg + "deg 360deg)"
      : "conic-gradient(rgba(92,73,45,.12) 0deg 360deg)";
    statusBreakdown.innerHTML =
      '<div><span class="status-dot dot-success"></span><span>抓取成功</span><strong>' + scrapedSuccessfully + "</strong></div>" +
      '<div><span class="status-dot dot-warning"></span><span>其中异常状态</span><strong>' + warning + "</strong></div>" +
      '<div><span class="status-dot dot-danger"></span><span>失败</span><strong>' + failed + "</strong></div>";

    var totalChanges = changeItems.length + removed.length;
    var filteredChangeItems = dashboardFilter === "changed"
      ? changed
      : dashboardFilter === "new" ? added : dashboardFilter === "removed" ? [] : changeItems;
    var filteredRemoved = dashboardFilter === "removed" || dashboardFilter === "all" ? removed : [];
    var filterLabels = { all: "全部变化", changed: "发生变化", new: "新增商品", removed: "本次未出现" };
    comparisonCount.textContent = (filteredChangeItems.length + filteredRemoved.length) + " 个 · " + filterLabels[dashboardFilter];
    dashboardPanel.querySelectorAll("[data-dashboard-filter]").forEach(function(tile) {
      tile.classList.toggle("active", tile.getAttribute("data-dashboard-filter") === dashboardFilter);
    });
    dashboardPanel.querySelectorAll("[data-business-risk]").forEach(function(tile) {
      tile.classList.toggle("active", tile.getAttribute("data-business-risk") === currentBusinessRiskFilter);
    });
    var html = filteredChangeItems.map(function(item) {
      var result = item.result;
      return '<div class="comparison-item comparison-' + item.comparison.type + '">' +
        '<div><a href="' + esc(result.resolved_url || result.url) + '" target="_blank">' + esc(result.asin) + "</a>" + comparisonMeta(result) + "</div>" +
        '<p>' + esc(item.comparison.detail) + "</p>" +
        '<strong>' + esc(item.comparison.label) + "</strong></div>";
    });
    filteredRemoved.forEach(function(result) {
      html.push('<div class="comparison-item comparison-removed"><div><span class="mono">' + esc(result.asin) + '</span>' + comparisonMeta(result) + '</div><p>本次抓取清单中未出现</p><strong>已移除</strong></div>');
    });
    comparisonList.innerHTML = html.length
      ? html.join("")
      : '<div class="comparison-empty">' + (sessionResults.length ? "当前筛选类型暂无对应商品。" : "完成一次抓取后，这里会显示变化。") + "</div>";
  }

  function resultComparison(result) {
    var previous = previousResults.find(function(item) { return item.asin === result.asin; });
    if (!previous) {
      return {
        type: "new",
        label: "新增",
        detail: "上次未出现",
        changes: []
      };
    }

    var changes = [];
    var previousErpRisk = normalizedErpRiskLabel(previous);
    var currentErpRisk = normalizedErpRiskLabel(result);
    var previousBusinessRisk = businessRiskInfo(previous);
    var currentBusinessRisk = businessRiskInfo(result);
    var erpRecoveredToNormal = previousErpRisk !== currentErpRisk && currentErpRisk === "ERP库存正常";
    var oldPrice = parsePrice(previous.price);
    var newPrice = parsePrice(result.price);
    if (oldPrice !== newPrice) {
      changes.push({
        field: "price",
        label: "价格",
        before: previous.price || "无价格",
        after: result.price || "无价格"
      });
    }
    if (previous.status !== result.status && !erpRecoveredToNormal) {
      changes.push({
        field: "status",
        label: "状态",
        before: statusLabel(previous),
        after: statusLabel(result)
      });
    }
    if ((previous.brand || "") !== (result.brand || "")) {
      changes.push({
        field: "brand",
        label: "品牌",
        before: previous.brand || "-",
        after: result.brand || "-"
      });
    }
    if ((previous.seller || "") !== (result.seller || "")) {
      changes.push({
        field: "seller",
        label: "店铺",
        before: previous.seller || "-",
        after: result.seller || "-"
      });
    }
    if ((previous.stock_left || "") !== (result.stock_left || "")) {
      changes.push({
        field: "stock",
        label: "库存",
        before: stockText(previous),
        after: stockText(result)
      });
    }
    if ((previous.erp_sku_stock || "") !== (result.erp_sku_stock || "") && currentErpRisk !== "ERP库存正常") {
      changes.push({
        field: "erp_stock",
        label: "ERP库存",
        before: erpStockText(previous),
        after: erpStockText(result)
      });
    }
    if (previousErpRisk !== currentErpRisk && currentErpRisk !== "ERP库存正常") {
      changes.push({
        field: "erp_risk",
        label: "ERP风险",
        before: previousErpRisk,
        after: currentErpRisk
      });
    }
    if (
      previousBusinessRisk.key !== currentBusinessRisk.key &&
      ["normal", "not_judged"].indexOf(currentBusinessRisk.key) === -1
    ) {
      changes.push({
        field: "business_risk",
        label: "业务风险",
        before: previousBusinessRisk.label,
        after: currentBusinessRisk.label
      });
    }

    return changes.length
      ? {
          type: "changed",
          label: "有变化",
          detail: changes.map(function(item) {
            return item.label + " " + item.before + " -> " + item.after;
          }).join("；"),
          changes: changes
        }
      : {
          type: "same",
          label: "无变化",
          detail: "与上次一致",
          changes: []
        };
  }

  function safeResultComparison(result) {
    try {
      var comparison = resultComparison(result);
      if (!comparison || !comparison.type) {
        return { type: "same", label: "未比对", detail: "对比数据为空，已跳过", changes: [] };
      }
      comparison.changes = Array.isArray(comparison.changes) ? comparison.changes : [];
      comparison.detail = comparison.detail || comparison.label || "未发现变化";
      return comparison;
    } catch (error) {
      console.error("Result comparison failed", error, result);
      return { type: "same", label: "未比对", detail: "旧数据字段异常，已跳过本行对比", changes: [] };
    }
  }

  function comparisonSnapshotRows(rows) {
    return rows.map(function(row) {
      return (
        '<div class="comparison-field-row">' +
          '<span class="comparison-field-name">' + esc(row.label) + "</span>" +
          '<span class="comparison-field-before">' + esc(row.before) + "</span>" +
          '<span class="comparison-field-arrow">-></span>' +
          '<span class="comparison-field-after">' + esc(row.after) + "</span>" +
        "</div>"
      );
    }).join("");
  }

  function newOrRemovedSnapshot(result, mode) {
    var rows = [
      { label: "状态", before: mode === "removed" ? statusLabel(result) : "上次未出现", after: mode === "removed" ? "本次未出现" : statusLabel(result) },
      { label: "价格", before: mode === "removed" ? (result.price || "无价格") : "-", after: mode === "removed" ? "-" : (result.price || "无价格") },
      { label: "品牌", before: mode === "removed" ? (result.brand || "-") : "-", after: mode === "removed" ? "-" : (result.brand || "-") },
      { label: "店铺", before: mode === "removed" ? (result.seller || "-") : "-", after: mode === "removed" ? "-" : (result.seller || "-") },
      { label: "库存", before: mode === "removed" ? stockText(result) : "-", after: mode === "removed" ? "-" : stockText(result) },
      { label: "ERP库存", before: mode === "removed" ? erpStockText(result) : "-", after: mode === "removed" ? "-" : erpStockText(result) },
      { label: "ERP风险", before: mode === "removed" ? (result.erp_inventory_risk || "-") : "-", after: mode === "removed" ? "-" : (result.erp_inventory_risk || "-") },
      { label: "业务风险", before: mode === "removed" ? businessRiskInfo(result).label : "-", after: mode === "removed" ? "-" : businessRiskInfo(result).label }
    ];
    return comparisonSnapshotRows(rows);
  }

  function renderDashboard() {
    var success = sessionResults.filter(function(result) { return result.status === "success"; }).length;
    var warning = sessionResults.filter(function(result) {
      return isWarningStatus(result.status);
    }).length;
    var failed = Math.max(0, sessionResults.length - success - warning);
    var scrapedSuccessfully = sessionResults.length - failed;
    var comparisons = sessionResults.map(function(result) {
      return { result: result, comparison: safeResultComparison(result) };
    });
    var changed = comparisons.filter(function(item) { return item.comparison.type === "changed"; });
    var added = comparisons.filter(function(item) { return item.comparison.type === "new"; });
    var currentAsins = {};
    sessionResults.forEach(function(result) { currentAsins[result.asin] = true; });
    var removed = comparisonFinalized ? previousResults.filter(function(result) { return !currentAsins[result.asin]; }) : [];
    var changeItems = changed.concat(added);

    dashTotal.textContent = String(sessionResults.length);
    dashChanged.textContent = String(changed.length);
    dashNew.textContent = String(added.length);
    dashRemoved.textContent = String(removed.length);
    dashboardBaseline.textContent = previousResults.length
      ? "对比基准：" + (previousResultsTime || "上一次完整抓取") + " · " + previousResults.length + " 个 ASIN"
      : "暂无上次抓取数据，本次将建立对比基准";

    var totalChanges = changeItems.length + removed.length;
    var filteredChangeItems = dashboardFilter === "changed"
      ? changed
      : dashboardFilter === "new" ? added : dashboardFilter === "removed" ? [] : changeItems;
    var filteredRemoved = dashboardFilter === "removed" || dashboardFilter === "all" ? removed : [];
    var filterLabels = { all: "全部变化", changed: "发生变化", new: "新增商品", removed: "本次未出现" };
    comparisonCount.textContent = (filteredChangeItems.length + filteredRemoved.length) + " 个 · " + filterLabels[dashboardFilter];
    if (comparisonMiniSummary) {
      comparisonMiniSummary.innerHTML =
        '<span class="comparison-mini-pill">成功 ' + scrapedSuccessfully + "</span>" +
        '<span class="comparison-mini-pill warn">异常 ' + warning + "</span>" +
        '<span class="comparison-mini-pill danger">失败 ' + failed + "</span>" +
        '<span class="comparison-mini-pill accent">总变化 ' + totalChanges + "</span>";
    }
    dashboardPanel.querySelectorAll("[data-dashboard-filter]").forEach(function(tile) {
      tile.classList.toggle("active", tile.getAttribute("data-dashboard-filter") === dashboardFilter);
    });

    var html = filteredChangeItems.map(function(item) {
      var result = item.result;
      var fields = item.comparison.type === "changed"
        ? comparisonSnapshotRows(item.comparison.changes)
        : newOrRemovedSnapshot(result, "new");
      var comparisonKey = item.comparison.type + ":" + result.asin;
      var collapsedClass = collapsedComparisons[comparisonKey] ? " comparison-item-collapsed" : "";
      var expanded = collapsedComparisons[comparisonKey] ? "false" : "true";
      return (
        '<div class="comparison-item comparison-' + item.comparison.type + collapsedClass + '" data-comparison-item="' + esc(comparisonKey) + '">' +
          '<div class="comparison-toggle" data-toggle-comparison="' + esc(comparisonKey) + '" aria-expanded="' + expanded + '">' +
            '<div class="comparison-item-head">' +
              '<div><a href="' + esc(result.resolved_url || result.url) + '" target="_blank">' + esc(result.asin) + "</a>" + comparisonMeta(result) + '</div>' +
              '<div class="comparison-item-side"><strong>' + esc(item.comparison.label) + '</strong><span class="comparison-caret" aria-hidden="true"></span></div>' +
            "</div>" +
            '<p class="comparison-item-summary">' + esc(item.comparison.detail) + "</p>" +
          "</div>" +
          '<div class="comparison-field-list">' + fields + "</div>" +
        "</div>"
      );
    });

    filteredRemoved.forEach(function(result) {
      html.push(
        '<div class="comparison-item comparison-removed" data-comparison-item="removed:' + esc(result.asin) + '">' +
          '<div class="comparison-item-head">' +
            '<div><span class="mono">' + esc(result.asin) + "</span>" + comparisonMeta(result) + '</div>' +
            "<strong>已移除</strong>" +
          "</div>" +
          '<p class="comparison-item-summary">本次抓取清单中未出现，因此归类为已移除。</p>' +
          '<div class="comparison-field-list">' + newOrRemovedSnapshot(result, "removed") + "</div>" +
        "</div>"
      );
    });

    comparisonList.innerHTML = html.length
      ? html.join("")
      : '<div class="comparison-empty">' + (sessionResults.length ? "当前筛选类型暂无对应商品。" : "完成一次抓取后，这里会显示变化。") + "</div>";
  }

  function gatherInput() {
    var items = [];
    inputRows.querySelectorAll("tr").forEach(function(row) {
      var raw = (row.querySelector(".asin-input").value || "").trim();
      var category = (row.querySelector(".category-input").value || "").trim();
      var name = (row.querySelector(".name-input").value || "").trim();
      var price = (row.querySelector(".price-input").value || "").trim();
      if (!raw) {
        return;
      }

      var asin = extractAsin(raw);
      if (!asin) {
        return;
      }

      var sourceType = getSourceType(raw);
      var sourceUrl = sourceType === "url" ? normalizeUrl(raw) : "";
      var sourceUrlAsin = sourceUrl ? extractAsin(sourceUrl) : "";
      if (sourceUrlAsin && sourceUrlAsin !== asin) {
        sourceType = "asin";
        sourceUrl = "";
      }
      var sourceLabel = sourceType === "url" ? autoCategory(raw) : "手动 ASIN";
      items.push({
        asin: asin,
        raw: raw,
        category: category || sourceLabel,
        name: name,
        price: price,
        source_type: sourceType,
        source_key: sourceType === "url" ? sourceUrl : asin,
        source_url: sourceUrl,
        source_label: sourceLabel
      });
    });
    return items;
  }

  function saveToLS() {
    var data = [];
    inputRows.querySelectorAll("tr").forEach(function(row) {
      data.push({
        asin: row.querySelector(".asin-input").value || "",
        category: row.querySelector(".category-input").value || "",
        name: row.querySelector(".name-input").value || "",
        price: row.querySelector(".price-input").value || ""
      });
    });
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(data));
      saveStatus.textContent = "已自动保存";
      setTimeout(function() {
        saveStatus.textContent = "";
      }, 1200);
    } catch (error) {}
  }

  function scheduleSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveToLS, 250);
  }

  function loadFromLS() {
    try {
      var raw = localStorage.getItem(LS_KEY);
      if (raw) {
        JSON.parse(raw).forEach(function(item) {
          createRow(item);
        });
      }
    } catch (error) {}

    if (!inputRows.children.length) {
      for (var i = 0; i < 6; i++) {
        createRow();
      }
    }
    updateGroupPreview();
  }

  function updateGroupPreview() {
    var groups = {};
    var validCount = 0;
    gatherInput().forEach(function(item) {
      validCount += 1;
      groups[item.category] = (groups[item.category] || 0) + 1;
    });

    statTotal.textContent = validCount;

    var labels = Object.keys(groups);
    if (!labels.length) {
      groupPreview.textContent = "还没有录入数据";
      return;
    }

    labels.sort(function(a, b) {
      return groups[b] - groups[a];
    });
    groupPreview.innerHTML = labels.slice(0, 6).map(function(label) {
      return '<div>' + esc(label) + " · " + groups[label] + " 个 ASIN</div>";
    }).join("");
  }

  function showMsg(text, type) {
    msgBox.hidden = false;
    msgBox.className = "msg-box msg-" + (type || "info");
    msgBox.textContent = text;
  }

  function hideMsg() {
    msgBox.hidden = true;
    msgBox.textContent = "";
  }

  function renderInventoryStatus(data) {
    data = data || {};
    var inventory = data.inventory || null;
    var skuMap = data.sku_map || null;
    var people = Array.isArray(data.inventory_people) ? data.inventory_people : [];
    var selectedPerson = data.inventory_person_filter || "";
    if (inventoryStatusCard) {
      inventoryStatusCard.innerHTML = inventory
        ? "ERP库存：已导入 " + esc(inventory.sku_count || 0) + " 个 SKU / " + esc(inventory.rows || 0) + " 行<br><span>" + esc(inventory.filename || "") + " · " + esc(inventory.imported_at || "") + " · " + esc(data.inventory_person_department || "指定部门") + "负责人 " + esc(inventory.person_count || people.length || 0) + " 人</span>"
        : "ERP库存：未导入";
      inventoryStatusCard.classList.toggle("loaded", !!inventory);
    }
    if (skuMapStatusCard) {
      skuMapStatusCard.innerHTML = skuMap
        ? "SKU映射：已导入 " + esc(skuMap.common_sku_count || 0) + " 个通用 SKU / " + esc(skuMap.actual_sku_count || 0) + " 个实际 SKU<br><span>" + esc(skuMap.filename || "") + " · " + esc(skuMap.imported_at || "") + "</span>"
        : "SKU映射：未导入";
      skuMapStatusCard.classList.toggle("loaded", !!skuMap);
    }
    if (inventoryPersonFilter) {
      var currentValue = selectedPerson || inventoryPersonFilter.value || "";
      inventoryPersonFilter.innerHTML = '<option value="">全部库存</option>' + people.map(function(person) {
        return '<option value="' + esc(person) + '">' + esc(person) + "</option>";
      }).join("");
      inventoryPersonFilter.value = people.indexOf(currentValue) !== -1 ? currentValue : "";
      inventoryPersonFilter.disabled = isScraping || !people.length;
    }
    if (inventoryPersonFilterNote) {
      inventoryPersonFilterNote.textContent = people.length
        ? "当前库存口径：" + (selectedPerson || "全部库存") + "；筛选对象仅来自“" + (data.inventory_person_department || "指定部门") + "”。"
        : "未读取到指定部门负责人；请先导入或自动更新 ERP 库存。";
    }
  }

  function loadInventoryStatus() {
    fetch("/api/inventory/status")
      .then(function(resp) { return resp.json(); })
      .then(renderInventoryStatus)
      .catch(function() {});
  }

  function saveInventoryPersonFilter() {
    var person = inventoryPersonFilter ? inventoryPersonFilter.value : "";
    if (inventoryPersonFilter) {
      inventoryPersonFilter.disabled = true;
    }
    return fetch("/api/inventory/person-filter", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ person: person })
    })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data.error) {
          throw new Error(data.error);
        }
        renderInventoryStatus(data);
        if (sessionResults.length && !isScraping) {
          return reapplyInventoryRisk(person).then(function() {
            showMsg(person ? "已切换为 " + person + " 名下库存，并同步刷新当前结果。" : "已切换为全部库存，并同步刷新当前结果。", "success");
          });
        }
        showMsg(person ? "已切换为 " + person + " 名下库存。" : "已切换为全部库存。", "success");
      })
      .catch(function(error) {
        showMsg(error.message || "库存负责人筛选保存失败。", "error");
        loadInventoryStatus();
      })
      .finally(function() {
        if (inventoryPersonFilter) {
          inventoryPersonFilter.disabled = isScraping || inventoryPersonFilter.options.length <= 1;
        }
      });
  }

  function reapplyInventoryRisk(person) {
    return fetch("/api/inventory/reapply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        person: person || "",
        session_id: currentSessionId || "",
        results: sessionResults
      })
    })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data.error) {
          throw new Error(data.error);
        }
        sessionResults = Array.isArray(data.results) ? data.results : sessionResults;
        currentErpRiskFilter = "全部ERP库存";
        renderResults();
        updateStats();
        return data;
      });
  }

  function renderErpConfigStatus(data) {
    data = data || {};
    if (erpUsernameInput && data.username) {
      erpUsernameInput.value = data.username;
    }
    if (erpPasswordInput) {
      erpPasswordInput.value = "";
      erpPasswordInput.placeholder = data.password_saved ? "已保存密码，留空则不修改" : "输入 ERP 密码";
    }
    if (erpTargetUrlInput) {
      erpTargetUrlInput.value = data.target_url || "";
    }
    if (erpDownloadTargetInput) {
      erpDownloadTargetInput.value = data.download_target || "导出,下载,Excel,库存";
    }
    if (erpAutoStatus) {
      erpAutoStatus.textContent = data.username
        ? "ERP自动更新：已配置账号 " + data.username + (data.password_saved ? "，密码已保存" : "，未保存密码")
        : "ERP自动更新：未配置";
    }
  }

  function loadErpConfig() {
    fetch("/api/erp/config")
      .then(function(resp) { return resp.json(); })
      .then(renderErpConfigStatus)
      .catch(function() {});
  }

  function saveErpConfig() {
    var username = erpUsernameInput ? erpUsernameInput.value.trim() : "";
    var password = erpPasswordInput ? erpPasswordInput.value : "";
    var targetUrl = erpTargetUrlInput ? erpTargetUrlInput.value.trim() : "";
    var downloadTarget = erpDownloadTargetInput ? erpDownloadTargetInput.value.trim() : "";
    if (!username) {
      showMsg("请先填写 ERP 账号。", "error");
      return Promise.reject(new Error("missing username"));
    }
    if (erpConfigSaveBtn) erpConfigSaveBtn.disabled = true;
    if (erpAutoStatus) erpAutoStatus.textContent = "ERP自动更新：正在保存配置...";
    return fetch("/api/erp/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username,
        password: password,
        target_url: targetUrl,
        download_target: downloadTarget,
        keep_password: !password
      })
    })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data.error) {
          throw new Error(data.error);
        }
        renderErpConfigStatus(data);
        showMsg("ERP配置已保存。", "success");
        return data;
      })
      .catch(function(error) {
        showMsg(error.message || "ERP配置保存失败。", "error");
        throw error;
      })
      .finally(function() {
        if (erpConfigSaveBtn) erpConfigSaveBtn.disabled = false;
      });
  }

  function autoUpdateErpInventory() {
    if (isScraping) {
      showMsg("抓取任务进行中，先完成或停止后再更新 ERP 库存。", "error");
      return;
    }
    if (erpAutoUpdateBtn) erpAutoUpdateBtn.disabled = true;
    if (erpConfigSaveBtn) erpConfigSaveBtn.disabled = true;
    if (erpAutoStatus) erpAutoStatus.textContent = "ERP自动更新：正在登录并下载库存，请稍等...";
    showMsg("正在自动登录 ERP 并下载库存表...", "info");

    fetch("/api/inventory/auto-update", { method: "POST" })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data.error) {
          throw new Error(data.error);
        }
        renderInventoryStatus(data);
        if (erpAutoStatus) {
          erpAutoStatus.textContent = "ERP自动更新：已完成，文件 " + (data.downloaded_file || "最新库存表");
        }
        showMsg("ERP库存已自动更新。", "success");
      })
      .catch(function(error) {
        if (erpAutoStatus) {
          erpAutoStatus.textContent = "ERP自动更新失败：" + (error.message || "请检查登录或下载入口");
        }
        showMsg(error.message || "ERP库存自动更新失败。", "error");
      })
      .finally(function() {
        if (erpAutoUpdateBtn) erpAutoUpdateBtn.disabled = false;
        if (erpConfigSaveBtn) erpConfigSaveBtn.disabled = false;
      });
  }

  function importInventoryContext(fileInput, endpoint, label) {
    var file = fileInput && fileInput.files ? fileInput.files[0] : null;
    if (!file) {
      return;
    }
    var formData = new FormData();
    formData.append("file", file);
    showMsg("正在导入" + label + "...", "info");
    fetch(endpoint, { method: "POST", body: formData })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data.error) {
          throw new Error(data.error);
        }
        renderInventoryStatus(data);
        showMsg(label + "导入成功。", "success");
      })
      .catch(function(error) {
        showMsg(error.message || (label + "导入失败"), "error");
      })
      .finally(function() {
        fileInput.value = "";
      });
  }

  function setScrapingState(active) {
    isScraping = active;
    startBtn.disabled = active;
    stopBtn.hidden = !active;
    addRowBtn.disabled = active;
    pasteBtn.disabled = active;
    importBtn.disabled = active;
    if (inventoryImportBtn) inventoryImportBtn.disabled = active;
    if (skuMapImportBtn) skuMapImportBtn.disabled = active;
    if (erpAutoUpdateBtn) erpAutoUpdateBtn.disabled = active;
    if (erpConfigSaveBtn) erpConfigSaveBtn.disabled = active;
    retryFailedBtn.disabled = active;
    if (inventoryPersonFilter) inventoryPersonFilter.disabled = active || inventoryPersonFilter.options.length <= 1;
    if (inputCategoryFilter) inputCategoryFilter.disabled = active;
    if (inputNoteFilter) inputNoteFilter.disabled = active;
    inputHeaderFilters.forEach(function(input) {
      input.disabled = active;
    });
    if (inputFilterClear) inputFilterClear.disabled = active;
    if (inputPageSizeSelect) inputPageSizeSelect.disabled = active;
    pageSizePresetButtons.forEach(function(button) {
      button.disabled = active;
    });
    inputRows.querySelectorAll("input, button.btn-del").forEach(function(el) {
      el.disabled = active;
    });
    startBtn.textContent = active ? "抓取中..." : "开始抓取";
  }

  function resetResults() {
    sessionResults = [];
    comparisonFinalized = false;
    dashboardFilter = "all";
    currentGroupFilter = "全部";
    currentStatusFilter = "全部状态";
    currentErpRiskFilter = "全部ERP库存";
    currentBusinessRiskFilter = "全部业务风险";
    currentPriceCompareFilter = "all";
    collapsedGroups = {};
    resultsGroups.innerHTML = "";
    groupFilters.innerHTML = "";
    summaryBar.hidden = true;
    exportBtn.hidden = true;
    retryFailedBtn.hidden = true;
    resultsArea.hidden = true;
    progressArea.hidden = true;
    progressBar.style.width = "0%";
    progressText.textContent = "0 / 0";
    statSuccess.textContent = "0";
    statWarning.textContent = "0";
    statFail.textContent = "0";
    renderDashboard();
  }

  function startLogGroup(items) {
    var now = new Date();
    currentLogGroup = {
      timeStr: now.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit"
      }),
      total: items.length,
      categories: Array.from(new Set(items.map(function(item) { return item.category; }))),
      results: []
    };
    logGroups.push(currentLogGroup);
    renderLog();
    scheduleLogSave();
    if (!logVisible) {
      logVisible = true;
      logBody.hidden = false;
    }
  }

  function addResultLog(result) {
    if (!currentLogGroup) {
      return;
    }
    currentLogGroup.results.push(result);
    renderLog();
    scheduleLogSave();
  }

  function finishLogGroup(statusText) {
    if (!currentLogGroup) {
      return;
    }
    currentLogGroup.summary = statusText;
    currentLogGroup = null;
    renderLog();
    scheduleLogSave();
  }

  function scheduleLogSave() {
    clearTimeout(logSaveTimer);
    logSaveTimer = setTimeout(saveOperationLogs, 180);
  }

  function saveOperationLogs() {
    try {
      localStorage.setItem(LOG_LS_KEY, JSON.stringify(logGroups));
    } catch (error) {}
  }

  function loadOperationLogs() {
    try {
      var raw = localStorage.getItem(LOG_LS_KEY);
      var savedLogs = raw ? JSON.parse(raw) : [];
      if (Array.isArray(savedLogs)) {
        logGroups = savedLogs;
      }
    } catch (error) {}
    renderLog();
  }

  function logStatusClass(status) {
    if (status === "success") return "log-success";
    if (isWarningStatus(status)) return "log-warn";
    return "log-error";
  }

  function renderLog() {
    if (!logGroups.length) {
      logEntries.innerHTML = '<div class="log-entry muted">暂无日志</div>';
      logCount.textContent = "0";
      return;
    }

    var html = logGroups.slice().reverse().map(function(group, index) {
      var realIndex = logGroups.length - 1 - index;
      var resultHtml = group.results.map(function(item) {
        var line = item.asin + " · " + item.status_label;
        if (item.category) {
          line += " · " + item.category;
        }
        if (item.price) {
          line += " · " + item.price;
        }
        if (item.stock_left || item.stock_message) {
          line += " · " + stockText(item);
        }
        return '<div class="log-entry ' + logStatusClass(item.status) + '">' + esc(line) + "</div>";
      }).join("");

      return (
        '<div class="log-group" id="log-group-' + realIndex + '">' +
          '<div class="log-group-header" data-log-index="' + realIndex + '">' +
            '<span class="log-group-time">' + group.timeStr + '</span>' +
            '<span class="log-group-title">抓取 ' + group.total + ' 个 ASIN</span>' +
            '<span class="log-group-summary">' + esc(group.summary || "进行中") + '</span>' +
          "</div>" +
          '<div class="log-group-body">' + resultHtml + "</div>" +
        "</div>"
      );
    }).join("");

    logEntries.innerHTML = html;
    logCount.textContent = String(logGroups.length);
  }

  function statusBadge(status, label, result) {
    var isErpStatus = ["erp_out_of_stock", "erp_low_stock", "erp_substitute_available"].indexOf(status) !== -1;
    var cls = "badge-error";
    if (status === "success") cls = "badge-success";
    if (isWarningStatus(status)) cls = "badge-warn";
    if (status === "low_stock") {
      label = label + " · " + stockText(result);
    }
    if (isErpStatus) {
      label = normalizedErpRiskLabel(result);
      cls = label === "ERP库存正常" ? "badge-success" : (label === "ERP缺货" ? "badge-error" : "badge-warn");
      return '<span class="badge erp-risk-filter ' + cls + '" data-erp-risk="' + esc(label) + '" title="点击筛选此ERP库存状态">' + esc(label) + "</span>";
    }
    return '<span class="badge status-filter-badge ' + cls + '" data-status="' + esc(status || "") + '" title="点击筛选此状态">' + esc(label) + "</span>";
  }

  function statusLabel(result) {
    return result.status_label || result.status || "未知";
  }

  function amazonStatusKey(result) {
    if (result.amazon_status) {
      return result.amazon_status;
    }
    if (["erp_out_of_stock", "erp_low_stock", "erp_substitute_available"].indexOf(result.status) !== -1) {
      return "success";
    }
    return result.status || "unknown";
  }

  function amazonStatusLabel(result) {
    if (result.amazon_status_label) {
      return result.amazon_status_label;
    }
    if (["erp_out_of_stock", "erp_low_stock", "erp_substitute_available"].indexOf(result.status) !== -1) {
      return "成功";
    }
    return statusLabel(result);
  }

  function buildStatusCounts(results) {
    var map = {};
    results.forEach(function(result) {
      var status = amazonStatusKey(result);
      if (!map[status]) {
        map[status] = {
          count: 0,
          label: amazonStatusLabel(result)
        };
      }
      map[status].count += 1;
    });
    return map;
  }

  function filterByStatus(results) {
    if (currentStatusFilter === "全部状态") {
      return results;
    }
    return results.filter(function(result) {
      return amazonStatusKey(result) === currentStatusFilter;
    });
  }

  function normalizedErpRiskLabel(result) {
    if (!result) {
      return "未判断ERP库存";
    }
    var raw = result.erp_inventory_risk || "";
    if (raw && raw !== "可替代库存") {
      return raw;
    }
    if (raw === "可替代库存" || result.status === "erp_substitute_available") {
      var own = Number(result.erp_sku_stock || 0);
      var substitute = Number(result.erp_substitute_stock || 0);
      var total = result.erp_total_stock === "" || result.erp_total_stock === null || result.erp_total_stock === undefined
        ? own + substitute
        : Number(result.erp_total_stock || 0);
      if (total <= 0) {
        return "ERP缺货";
      }
      if (total <= 10) {
        return "ERP即将缺货";
      }
      return "ERP库存正常";
    }
    return "未判断ERP库存";
  }

  function erpRiskKey(result) {
    return normalizedErpRiskLabel(result);
  }

  function buildErpRiskCounts(results) {
    var map = {};
    results.forEach(function(result) {
      var key = erpRiskKey(result);
      if (!map[key]) {
        map[key] = {
          count: 0,
          label: key
        };
      }
      map[key].count += 1;
    });
    return map;
  }

  function filterByErpRisk(results) {
    if (currentErpRiskFilter === "全部ERP库存") {
      return results;
    }
    return results.filter(function(result) {
      return erpRiskKey(result) === currentErpRiskFilter;
    });
  }

  function erpTotalStock(result) {
    if (!result) {
      return null;
    }
    if (result.erp_total_stock !== "" && result.erp_total_stock !== null && result.erp_total_stock !== undefined) {
      var total = Number(result.erp_total_stock);
      return isNaN(total) ? null : total;
    }
    if (result.erp_sku_stock !== "" && result.erp_sku_stock !== null && result.erp_sku_stock !== undefined) {
      var own = Number(result.erp_sku_stock || 0);
      var substitute = Number(result.erp_substitute_stock || 0);
      return (isNaN(own) ? 0 : own) + (isNaN(substitute) ? 0 : substitute);
    }
    return null;
  }

  function businessRiskInfo(result) {
    if (!result) {
      return { key: "not_judged", label: "未判断业务风险", note: "没有结果数据", level: 0 };
    }
    if (result.business_risk && result.business_risk_label) {
      return {
        key: result.business_risk,
        label: result.business_risk_label,
        note: result.business_risk_note || result.business_risk_label,
        level: Number(result.business_risk_level || 0)
      };
    }

    var amazonStatus = amazonStatusKey(result);
    var erpRisk = normalizedErpRiskLabel(result);
    var total = erpTotalStock(result);
    if (erpRisk === "未导入ERP库存" || erpRisk === "未填写ERP SKU" || erpRisk === "ERP未匹配" || total === null) {
      return { key: "not_judged", label: "未判断业务风险", note: erpRisk || "需要导入 ERP 库存", level: 0 };
    }
    if ((amazonStatus === "success" || amazonStatus === "price_warn") && total <= 0) {
      return { key: "oversell", label: "超卖风险", note: "Amazon 可售，但 ERP 总库存为 0", level: 5 };
    }
    if ((amazonStatus === "success" || amazonStatus === "price_warn") && total > 0 && total <= 10) {
      return { key: "near_oversell", label: "即将超卖", note: "Amazon 可售，但 ERP 总库存仅 " + total, level: 4 };
    }
    if ((amazonStatus === "out_of_stock" || amazonStatus === "low_stock") && total > 10) {
      return { key: "replenish_opportunity", label: "可补货机会", note: "Amazon 缺货或即将缺货，但 ERP 总库存还有 " + total, level: 4 };
    }
    if ((amazonStatus === "out_of_stock" || amazonStatus === "low_stock") && total > 0 && total <= 10) {
      return { key: "low_stock_unavailable", label: "低库存缺货", note: "Amazon 缺货或即将缺货，ERP 总库存也仅 " + total, level: 3 };
    }
    if (amazonStatus === "price_compare" && total > 0) {
      return { key: "quote_abnormal", label: "报价异常", note: "Amazon 为比价/无购物车状态，但 ERP 有库存", level: 3 };
    }
    if ((amazonStatus === "success" || amazonStatus === "price_warn") && total > 10) {
      return { key: "normal", label: "库存一致", note: "Amazon 可售且 ERP 库存正常", level: 1 };
    }
    return { key: "observe", label: "观察", note: "需要结合 Amazon 状态和 ERP 库存复核", level: 1 };
  }

  function businessRiskKey(result) {
    return businessRiskInfo(result).key;
  }

  function buildBusinessRiskCounts(results) {
    var map = {};
    results.forEach(function(result) {
      var info = businessRiskInfo(result);
      if (!map[info.key]) {
        map[info.key] = { count: 0, label: info.label, level: info.level };
      }
      map[info.key].count += 1;
      map[info.key].level = Math.max(map[info.key].level || 0, info.level || 0);
    });
    return map;
  }

  function filterByBusinessRisk(results) {
    if (currentBusinessRiskFilter === "全部业务风险") {
      return results;
    }
    return results.filter(function(result) {
      return businessRiskKey(result) === currentBusinessRiskFilter;
    });
  }

  function businessRiskBadge(result) {
    var info = businessRiskInfo(result);
    if (info.key === "not_judged" || info.key === "normal") {
      return "";
    }
    var cls = info.key === "oversell" ? "badge-error" : (info.key === "replenish_opportunity" || info.key === "quote_abnormal" ? "badge-accent" : "badge-warn");
    return '<span class="badge business-risk-filter ' + cls + '" data-business-risk="' + esc(info.key) + '" title="' + esc(info.note) + '；点击筛选此业务风险">' + esc(info.label) + "</span>";
  }

  function priceCompareState(result) {
    var expected = parsePrice(result.expected_price);
    var current = parsePrice(result.price);
    if (expected === null || current === null) {
      return { key: "unset", label: "未比对", detail: "未设置预期价或未抓到价格" };
    }
    var delta = +(current - expected).toFixed(2);
    if (Math.abs(delta) <= 0.01) {
      return { key: "same", label: "价格一致", detail: "实际价格与预期价一致", delta: delta };
    }
    var symbol = delta > 0 ? "+" : "";
    return { key: "changed", label: "价格不同", detail: "差价 " + symbol + delta.toFixed(2), delta: delta };
  }

  function buildPriceCompareCounts(results) {
    var map = {
      changed: { count: 0, label: "价格不同" },
      same: { count: 0, label: "价格一致" },
      unset: { count: 0, label: "未比对" }
    };
    results.forEach(function(result) {
      map[priceCompareState(result).key].count += 1;
    });
    return map;
  }

  function filterByPriceCompare(results) {
    if (currentPriceCompareFilter === "all") {
      return results;
    }
    return results.filter(function(result) {
      return priceCompareState(result).key === currentPriceCompareFilter;
    });
  }

  function compareState(result) {
    var state = priceCompareState(result);
    if (state.key === "unset") {
      return '<span class="price-compare-filter muted" data-price-compare="unset" title="点击筛选未比对">-</span>';
    }
    if (state.key === "same") {
      return '<span class="badge badge-success price-compare-filter" data-price-compare="same" title="点击筛选价格一致">一致</span>';
    }
    var symbol = state.delta > 0 ? "+" : "";
    return '<span class="badge badge-warn price-compare-filter" data-price-compare="changed" title="点击筛选价格不同">' + symbol + state.delta.toFixed(2) + "</span>";
  }

  function erpRiskCell(result) {
    var label = normalizedErpRiskLabel(result);
    if (!result.erp_inventory_risk && label === "未判断ERP库存") {
      return '<span class="muted">-</span>';
    }
    if (["erp_out_of_stock", "erp_low_stock", "erp_substitute_available"].indexOf(result.status) !== -1) {
      return "";
    }
    var title = result.erp_inventory_note || label;
    var cls = label === "ERP库存正常" ? "badge-success" : (label === "ERP缺货" ? "badge-error" : "badge-warn");
    return '<span class="badge erp-risk-filter ' + cls + '" data-erp-risk="' + esc(label) + '" title="' + esc(title) + '；点击筛选此ERP库存状态">' + esc(label) + "</span>";
  }

  function erpSubstituteCell(result) {
    var skus = result.erp_substitute_skus || [];
    var stock = substituteText(result);
    if (stock === "-") {
      return '<span class="muted">-</span>';
    }
    return '<span class="substitute-pill" title="' + esc(skus.join(" / ") || "无可替代 SKU 明细") + '">' + esc(stock) + "</span>";
  }

  function buildGroups(results) {
    var map = {};
    results.forEach(function(result) {
      var key = result.category || "未填写店铺链接名";
      if (!map[key]) {
        map[key] = [];
      }
      map[key].push(result);
    });
    return map;
  }

  function updateStats() {
    var success = 0;
    var warning = 0;
    var fail = 0;
    sessionResults.forEach(function(result) {
      if (result.status === "success") {
        success += 1;
      } else if (isWarningStatus(result.status)) {
        warning += 1;
      } else {
        fail += 1;
      }
    });
    statSuccess.textContent = String(success);
    statWarning.textContent = String(warning);
    statFail.textContent = String(fail);
  }

  function renderGroupFilters(groupMap, statusMap) {
    var groups = Object.keys(groupMap);
    var buttons = [
      '<button type="button" class="chip filter-chip ' + (currentGroupFilter === "全部" ? "active" : "") + '" data-group="全部">全部店铺链接名</button>'
    ];
    groups.sort().forEach(function(group) {
      var active = currentGroupFilter === group ? "active" : "";
      buttons.push('<button type="button" class="chip filter-chip ' + active + '" data-group="' + esc(group) + '">' + esc(group) + " · " + groupMap[group].length + "</button>");
    });

    var statusButtons = [
      '<button type="button" class="chip status-chip ' + (currentStatusFilter === "全部状态" ? "active" : "") + '" data-status="全部状态">全部状态</button>'
    ];
    Object.keys(statusMap).sort(function(a, b) {
      return statusMap[b].count - statusMap[a].count;
    }).forEach(function(status) {
      var active = currentStatusFilter === status ? "active" : "";
      statusButtons.push(
        '<button type="button" class="chip status-chip ' + active + '" data-status="' + esc(status) + '">' +
        esc(statusMap[status].label) + " · " + statusMap[status].count +
        "</button>"
      );
    });

    var priceCompareMap = buildPriceCompareCounts(sessionResults);
    var compareButtons = [
      '<button type="button" class="chip compare-chip ' + (currentPriceCompareFilter === "all" ? "active" : "") + '" data-price-compare="all">全部比对</button>'
    ];
    ["changed", "same", "unset"].forEach(function(key) {
      var active = currentPriceCompareFilter === key ? "active" : "";
      compareButtons.push(
        '<button type="button" class="chip compare-chip ' + active + '" data-price-compare="' + key + '">' +
        priceCompareMap[key].label + " · " + priceCompareMap[key].count +
        "</button>"
      );
    });

    var erpRiskMap = buildErpRiskCounts(sessionResults);
    var erpButtons = [
      '<button type="button" class="chip erp-chip ' + (currentErpRiskFilter === "全部ERP库存" ? "active" : "") + '" data-erp-risk="全部ERP库存">全部ERP库存</button>'
    ];
    Object.keys(erpRiskMap).sort(function(a, b) {
      return erpRiskMap[b].count - erpRiskMap[a].count;
    }).forEach(function(key) {
      var active = currentErpRiskFilter === key ? "active" : "";
      erpButtons.push(
        '<button type="button" class="chip erp-chip ' + active + '" data-erp-risk="' + esc(key) + '">' +
        esc(erpRiskMap[key].label) + " · " + erpRiskMap[key].count +
        "</button>"
      );
    });

    var businessRiskMap = buildBusinessRiskCounts(sessionResults);
    var businessOrder = ["oversell", "near_oversell", "replenish_opportunity", "quote_abnormal", "low_stock_unavailable", "observe", "normal", "not_judged"];
    var businessButtons = [
      '<button type="button" class="chip business-chip ' + (currentBusinessRiskFilter === "全部业务风险" ? "active" : "") + '" data-business-risk="全部业务风险">全部业务风险</button>'
    ];
    Object.keys(businessRiskMap).sort(function(a, b) {
      var indexA = businessOrder.indexOf(a);
      var indexB = businessOrder.indexOf(b);
      if (indexA === -1) indexA = 99;
      if (indexB === -1) indexB = 99;
      if (indexA !== indexB) return indexA - indexB;
      return businessRiskMap[b].count - businessRiskMap[a].count;
    }).forEach(function(key) {
      var active = currentBusinessRiskFilter === key ? "active" : "";
      businessButtons.push(
        '<button type="button" class="chip business-chip ' + active + '" data-business-risk="' + esc(key) + '">' +
        esc(businessRiskMap[key].label) + " · " + businessRiskMap[key].count +
        "</button>"
      );
    });

    groupFilters.innerHTML =
      '<div class="filter-row"><span class="filter-label">店铺链接名</span>' + buttons.join("") + "</div>" +
      '<div class="filter-row"><span class="filter-label">业务风险</span>' + businessButtons.join("") + "</div>" +
      '<div class="filter-row"><span class="filter-label">Amazon状态</span>' + statusButtons.join("") + "</div>" +
      '<div class="filter-row"><span class="filter-label">ERP库存</span>' + erpButtons.join("") + "</div>" +
      '<div class="filter-row"><span class="filter-label">比对</span>' + compareButtons.join("") + "</div>";
  }

  function renderResults() {
    resultsArea.hidden = false;
    exportBtn.hidden = !sessionResults.length;
    retryFailedBtn.hidden = !sessionResults.some(function(result) { return result.status === "error"; });

    var statusMap = buildStatusCounts(sessionResults);
    var statusFilteredResults = filterByStatus(sessionResults);
    statusFilteredResults = filterByErpRisk(statusFilteredResults);
    statusFilteredResults = filterByBusinessRisk(statusFilteredResults);
    statusFilteredResults = filterByPriceCompare(statusFilteredResults);
    var groupMap = buildGroups(statusFilteredResults);
    renderGroupFilters(groupMap, statusMap);
    updateStats();
    try {
      renderDashboard();
    } catch (error) {
      console.error("Dashboard render failed", error);
    }

    var groups = Object.keys(groupMap).sort();
    if (currentGroupFilter !== "全部") {
      groups = groups.filter(function(group) { return group === currentGroupFilter; });
    }

    if (!groups.length) {
      resultsGroups.innerHTML = '<div class="empty-state">当前筛选条件下没有结果。</div>';
      return;
    }

    resultsGroups.innerHTML = groups.map(function(group) {
      var collapsed = !!collapsedGroups[group];
      var rows = groupMap[group].map(function(result, index) {
        try {
          var duplicateTag = result.duplicate_count > 1 ? '<span class="duplicate-tag">重复 ' + result.duplicate_count + ' 次</span>' : "";
          var brand = result.brand || (result.title ? String(result.title).trim().split(/\s+/)[0] : "");
          var productUrl = result.input_url || result.url || result.resolved_url || "#";
          var resolvedUrl = result.resolved_url || "";
          var sellerText = result.seller || "-";
          var asinMeta = [brand, sellerText].filter(function(item) { return item && item !== "-"; }).join(" · ");
          var detailTitle = [
            result.title ? "标题：" + result.title : "",
            result.note ? "ERP SKU：" + result.note : "",
            result.erp_common_sku ? "通用SKU：" + result.erp_common_sku : "",
            result.diagnostic_evidence ? "诊断证据：" + result.diagnostic_evidence : "",
            result.source_label ? "来源：" + result.source_label : ""
          ].filter(Boolean).join("\n");
          var comparison = safeResultComparison(result);
          var comparisonBadge = '<span class="comparison-badge comparison-' + comparison.type + '" title="' + esc(comparison.detail) + '">' + esc(comparison.label) + "</span>";
          var priceCell = '<div class="price-stack"><span>' + esc(result.price || "-") + "</span>" + comparisonBadge + "</div>";
          var titleLine = result.title ? '<div class="compact-product-title">' + esc(result.title) + "</div>" : "";
          var commonSkuLine = result.erp_common_sku ? '<div class="compact-common-sku" title="通用SKU：' + esc(result.erp_common_sku) + '">' + esc(result.erp_common_sku) + "</div>" : "";
          var erpStockMain = erpStockText(result) === "-"
            ? '<span class="muted">-</span>'
            : '<span class="erp-stock-pill erp-risk-filter" data-erp-risk="' + esc(erpRiskKey(result)) + '" title="' + esc(result.erp_inventory_note || "") + '；点击筛选此ERP库存状态">' + esc(erpStockText(result)) + "</span>";
          var erpStockCell = '<div class="erp-stock-stack">' + commonSkuLine + erpStockMain + "</div>";
          return (
            "<tr>" +
              '<td class="compact-asin-cell" title="' + esc(detailTitle) + '">' +
                '<a class="compact-asin-link" href="' + esc(productUrl) + '" target="_blank">' + esc(result.asin) + "</a>" + duplicateTag +
                '<div class="compact-asin-meta">' + esc(asinMeta || "点击打开商品") + "</div>" +
                titleLine +
                (result.resolved_asin && result.resolved_asin !== result.asin ? '<div class="muted">页面 ASIN: ' + esc(result.resolved_asin) + (resolvedUrl ? ' · <a href="' + esc(resolvedUrl) + '" target="_blank">实际页面</a>' : "") + "</div>" : "") +
                (result.diagnostic_evidence && result.status !== "success" ? '<div class="muted compact-diagnostic" title="' + esc(result.diagnostic_evidence) + '">诊断：' + esc(result.diagnostic_evidence) + "</div>" : "") +
              "</td>" +
              '<td class="price-cell">' + priceCell + "</td>" +
              "<td>" + erpStockCell + "</td>" +
              '<td><div class="compact-status-stack">' + businessRiskBadge(result) + statusBadge(result.status, result.status_label || result.status, result) + erpRiskCell(result) + compareState(result) + "</div></td>" +
            "</tr>"
          );
        } catch (error) {
          console.error("Result row render failed", error, result);
          var message = error && error.message ? error.message : String(error || "未知错误");
          return '<tr><td colspan="4" class="render-error-row">结果行渲染异常：' + esc(result && result.asin ? result.asin : "未知 ASIN") + "；" + esc(message) + '。数据仍在，可导出 Excel 或刷新后重试。</td></tr>';
        }
      }).join("");

      return (
        '<section class="result-group ' + (collapsed ? "collapsed" : "") + '" data-group="' + esc(group) + '">' +
          '<div class="group-head" data-toggle-group="' + esc(group) + '" title="点击折叠 / 展开">' +
            '<div class="group-title-wrap">' +
              "<h3>" + esc(group) + "</h3>" +
              '<div class="group-subtitle">' + (collapsed ? "已折叠，点击展开结果" : "同一店铺链接名或来源链接的 ASIN 会集中展示") + "</div>" +
            "</div>" +
            '<div class="group-meta">' + groupMap[group].length + ' 个 ASIN <span class="collapse-caret">' + (collapsed ? "展开" : "收起") + "</span></div>" +
          "</div>" +
          '<div class="table-scroll">' +
            '<table class="result-table">' +
              "<thead><tr><th>ASIN / 商品标题</th><th>价格 / 较上次</th><th>通用SKU / ERP库存</th><th>状态</th></tr></thead>" +
              "<tbody>" + rows + "</tbody>" +
            "</table>" +
          "</div>" +
        "</section>"
      );
    }).join("");
  }

  function finishScrape(customMessage, customType) {
    setScrapingState(false);
    if (evtSource) {
      evtSource.close();
      evtSource = null;
    }

    comparisonFinalized = true;
    updateStats();
    renderResults();

    var success = Number(statSuccess.textContent || 0);
    var warning = Number(statWarning.textContent || 0);
    var fail = Number(statFail.textContent || 0);
    var summaryText = "成功 " + success + " · 异常 " + warning + " · 失败 " + fail;
    summaryBar.hidden = false;
    summaryBar.textContent = summaryText;
    saveCurrentResultsAsPrevious();
    if (!previousResults.length && sessionResults.length) {
      dashboardBaseline.textContent = "本次结果已保存，下次抓取将自动对比";
    }

    if (customMessage) {
      showMsg(customMessage, customType || "info");
      finishLogGroup(summaryText + " · " + customMessage);
      return;
    }

    if (fail > 0) {
      showMsg("抓取完成，但存在失败项。请优先检查失败和异常分组。", "error");
    } else if (warning > 0) {
      showMsg("抓取完成，存在缺货、跳转或价格提醒。", "info");
    } else {
      showMsg("抓取完成，结果已经按店铺链接名整理好。", "success");
    }
    finishLogGroup(summaryText);
  }

  function startScrape(options) {
    if (isScraping) {
      return;
    }

    options = options || {};
    var items = options.items || gatherInput();
    var carryResults = options.carryResults || [];
    if (!items.length) {
      showMsg("请至少输入一个有效的 ASIN 或 Amazon 链接。", "error");
      return;
    }

    if (previousResultsReady && !options.previousReadyChecked) {
      showMsg("正在读取上次抓取结果，稍后自动开始...", "info");
      previousResultsReady.finally(function() {
        var nextOptions = {};
        Object.keys(options).forEach(function(key) {
          nextOptions[key] = options[key];
        });
        nextOptions.previousReadyChecked = true;
        startScrape(nextOptions);
      });
      return;
    }

    loadPreviousResults();
    resetResults();
    if (carryResults.length) {
      sessionResults = carryResults.slice();
      renderResults();
    }
    hideMsg();
    setScrapingState(true);
    progressArea.hidden = false;
    statTotal.textContent = String(items.length + carryResults.length);
    startLogGroup(items);
    showMsg(options.retryFailed ? "正在重新抓取失败 ASIN..." : "正在启动抓取任务...", "info");

    fetch("/api/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: items,
        carry_results: carryResults,
        inventory_person_filter: inventoryPersonFilter ? inventoryPersonFilter.value : ""
      })
    })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data.error) {
          throw new Error(data.error);
        }

        currentSessionId = data.session_id;
        evtSource = new EventSource("/api/stream?session_id=" + encodeURIComponent(currentSessionId));

        evtSource.addEventListener("progress", function(event) {
          var payload = JSON.parse(event.data);
          var percent = Math.round((payload.current / payload.total) * 100);
          progressBar.style.width = percent + "%";
          progressText.textContent = payload.current + " / " + payload.total + " · " + payload.asin;
        });

        evtSource.addEventListener("result", function(event) {
          var payload = JSON.parse(event.data);
          sessionResults.push(payload);
          renderResults();
          addResultLog(payload);
        });

        evtSource.addEventListener("complete", function() {
          progressBar.style.width = "100%";
          finishScrape();
        });

        evtSource.addEventListener("stopped", function() {
          finishScrape("已停止剩余任务，当前结果已保留。", "info");
        });

        evtSource.addEventListener("error", function(event) {
          try {
            var payload = JSON.parse(event.data);
            finishScrape("抓取异常：" + payload.message, "error");
          } catch (error) {
            finishScrape("抓取过程中连接中断，请检查日志。", "error");
          }
        });

        evtSource.onerror = function() {
          if (isScraping) {
            finishScrape("实时连接中断，已结束监听。", "error");
          }
        };
      })
      .catch(function(error) {
        setScrapingState(false);
        showMsg(error.message || "启动失败", "error");
      });
  }

  function retryFailedAsins() {
    if (isScraping) {
      return;
    }
    var failedResults = sessionResults.filter(function(result) { return result.status === "error"; });
    if (!failedResults.length) {
      return;
    }
    var failedAsins = {};
    failedResults.forEach(function(result) { failedAsins[result.asin] = true; });
    var retryItems = gatherInput().filter(function(item) { return failedAsins[item.asin]; });
    var carryResults = sessionResults.filter(function(result) { return result.status !== "error"; });
    if (!retryItems.length) {
      showMsg("未在录入区找到失败 ASIN，无法重新抓取。", "error");
      return;
    }
    startScrape({ items: retryItems, carryResults: carryResults, retryFailed: true });
  }

  function stopScrape() {
    if (!currentSessionId) {
      return;
    }
    fetch("/api/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: currentSessionId })
    }).catch(function() {});
    showMsg("已请求停止，当前正在抓取的单个商品完成后会结束。", "info");
  }

  function exportExcel() {
    if (!currentSessionId) {
      return;
    }
    window.open("/api/export?session_id=" + encodeURIComponent(currentSessionId), "_blank");
  }

  function pasteFromClipboard() {
    navigator.clipboard.readText()
      .then(function(text) {
        var lines = text.split(/\r?\n/).map(function(line) { return line.trim(); }).filter(Boolean);
        if (!lines.length) {
          return;
        }

        if (hasContent() && !window.confirm("将替换当前录入内容，是否继续？")) {
          return;
        }

        inputRows.innerHTML = "";
        lines.forEach(function(line) {
          var parts = line.split(/\t|,/);
          createRow({
            asin: (parts[0] || "").trim(),
            category: (parts[1] || "").trim(),
            name: (parts[2] || "").trim(),
            price: (parts[3] || "").trim()
          });
        });
        scheduleSave();
        updateGroupPreview();
        showMsg("已从剪贴板导入 " + lines.length + " 行。", "success");
      })
      .catch(function() {
        showMsg("无法读取剪贴板，请检查浏览器权限。", "error");
      });
  }

  function hasContent() {
    return Array.prototype.some.call(inputRows.querySelectorAll(".asin-input"), function(input) {
      return !!(input.value || "").trim();
    });
  }

  function importExcel() {
    var file = importFile.files[0];
    if (!file) {
      return;
    }

    var formData = new FormData();
    formData.append("file", file);
    showMsg("正在解析 Excel...", "info");

    fetch("/api/import", { method: "POST", body: formData })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data.error) {
          throw new Error(data.error);
        }
        if (hasContent() && !window.confirm("将替换当前录入内容，共导入 " + data.rows.length + " 行，是否继续？")) {
          return;
        }

        inputRows.innerHTML = "";
        data.rows.forEach(function(row) {
          createRow({
            asin: row.asin,
            category: row.category || "",
            name: row.name || "",
            price: row.price || ""
          });
        });
        scheduleSave();
        updateGroupPreview();
        showMsg("已导入 " + data.rows.length + " 行数据。", "success");
      })
      .catch(function(error) {
        showMsg(error.message || "导入失败", "error");
      })
      .finally(function() {
        importFile.value = "";
      });
  }

  addRowBtn.addEventListener("click", function() { addRow(); });
  intakeToggle.addEventListener("click", function() {
    setIntakeCollapsed(!intakeCollapsed);
  });
  inputPageSizeSelect.addEventListener("keydown", function(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      applyInputPageSize();
      inputPageSizeSelect.blur();
    }
  });
  pageSizePresetButtons.forEach(function(button) {
    button.addEventListener("click", function() {
      applyInputPageSize(button.getAttribute("data-page-size-preset"));
    });
  });
  inputPrevPage.addEventListener("click", function() {
    inputCurrentPage -= 1;
    updateInputPagination();
  });
  inputNextPage.addEventListener("click", function() {
    inputCurrentPage += 1;
    updateInputPagination();
  });
  if (inputCategoryFilter) {
    inputCategoryFilter.addEventListener("input", updateInputFilters);
  }
  if (inputNoteFilter) {
    inputNoteFilter.addEventListener("input", updateInputFilters);
  }
  inputHeaderFilters.forEach(function(input) {
    input.addEventListener("input", updateInputFilters);
    input.addEventListener("keydown", function(event) {
      if (event.key === "Enter") {
        event.preventDefault();
        input.blur();
      }
    });
  });
  if (inputFilterClear) {
    inputFilterClear.addEventListener("click", function() {
      if (inputCategoryFilter) inputCategoryFilter.value = "";
      if (inputNoteFilter) inputNoteFilter.value = "";
      inputHeaderFilters.forEach(function(input) {
        input.value = "";
      });
      updateInputFilters();
    });
  }
  pasteBtn.addEventListener("click", pasteFromClipboard);
  importBtn.addEventListener("click", function() { importFile.click(); });
  importFile.addEventListener("change", importExcel);
  if (inventoryImportBtn && inventoryFile) {
    inventoryImportBtn.addEventListener("click", function() { inventoryFile.click(); });
    inventoryFile.addEventListener("change", function() {
      importInventoryContext(inventoryFile, "/api/inventory/import", "ERP库存");
    });
  }
  if (skuMapImportBtn && skuMapFile) {
    skuMapImportBtn.addEventListener("click", function() { skuMapFile.click(); });
    skuMapFile.addEventListener("change", function() {
      importInventoryContext(skuMapFile, "/api/sku-map/import", "SKU映射表");
    });
  }
  if (inventoryPersonFilter) {
    inventoryPersonFilter.addEventListener("change", saveInventoryPersonFilter);
  }
  if (erpConfigSaveBtn) {
    erpConfigSaveBtn.addEventListener("click", function() {
      saveErpConfig().catch(function() {});
    });
  }
  if (erpAutoUpdateBtn) {
    erpAutoUpdateBtn.addEventListener("click", function() {
      var password = erpPasswordInput ? erpPasswordInput.value : "";
      if (password || (erpUsernameInput && erpUsernameInput.value.trim())) {
        saveErpConfig()
          .then(autoUpdateErpInventory)
          .catch(function() {});
      } else {
        autoUpdateErpInventory();
      }
    });
  }
  startBtn.addEventListener("click", startScrape);
  stopBtn.addEventListener("click", stopScrape);
  exportBtn.addEventListener("click", exportExcel);
  retryFailedBtn.addEventListener("click", retryFailedAsins);
  dashboardPanel.addEventListener("click", function(event) {
    var riskTile = event.target.closest("[data-business-risk]");
    if (riskTile) {
      currentBusinessRiskFilter = riskTile.getAttribute("data-business-risk") || "全部业务风险";
      currentGroupFilter = "全部";
      renderResults();
      resultsArea.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    var tile = event.target.closest("[data-dashboard-filter]");
    if (!tile) {
      return;
    }
    dashboardFilter = tile.getAttribute("data-dashboard-filter") || "all";
    renderDashboard();
    comparisonList.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  comparisonList.addEventListener("click", function(event) {
    if (event.target.closest("a")) {
      return;
    }
    var toggle = event.target.closest(".comparison-toggle, .comparison-item-head, .comparison-item-summary");
    if (!toggle) {
      return;
    }
    var item = toggle.closest(".comparison-item");
    if (!item) {
      return;
    }
    var comparisonKey = item.getAttribute("data-comparison-item");
    var nextCollapsed = !item.classList.contains("comparison-item-collapsed");
    item.classList.toggle("comparison-item-collapsed", nextCollapsed);
    if (comparisonKey) {
      collapsedComparisons[comparisonKey] = nextCollapsed;
    }
    var togglePanel = item.querySelector(".comparison-toggle");
    if (togglePanel) {
      togglePanel.setAttribute("aria-expanded", nextCollapsed ? "false" : "true");
    }
  });

  document.addEventListener("keydown", function(event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !isScraping) {
      event.preventDefault();
      startScrape();
    }
  });

  window.addEventListener("beforeunload", function() {
    saveOperationLogs();
  });

  groupFilters.addEventListener("click", function(event) {
    var groupTarget = event.target.closest("[data-group]");
    var statusTarget = event.target.closest("[data-status]");
    var erpRiskTarget = event.target.closest("[data-erp-risk]");
    var businessRiskTarget = event.target.closest("[data-business-risk]");
    if (groupTarget) {
      currentGroupFilter = groupTarget.getAttribute("data-group");
      renderResults();
      return;
    }
    if (statusTarget) {
      currentStatusFilter = statusTarget.getAttribute("data-status");
      currentGroupFilter = "全部";
      renderResults();
      return;
    }
    if (erpRiskTarget) {
      currentErpRiskFilter = erpRiskTarget.getAttribute("data-erp-risk") || "全部ERP库存";
      currentGroupFilter = "全部";
      renderResults();
      return;
    }
    if (businessRiskTarget) {
      currentBusinessRiskFilter = businessRiskTarget.getAttribute("data-business-risk") || "全部业务风险";
      currentGroupFilter = "全部";
      renderResults();
      return;
    }
    var compareTarget = event.target.closest("[data-price-compare]");
    if (compareTarget) {
      currentPriceCompareFilter = compareTarget.getAttribute("data-price-compare") || "all";
      currentGroupFilter = "全部";
      renderResults();
    }
  });

  resultsGroups.addEventListener("click", function(event) {
    var statusTarget = event.target.closest("[data-status]");
    if (statusTarget) {
      currentStatusFilter = statusTarget.getAttribute("data-status");
      currentGroupFilter = "全部";
      renderResults();
      return;
    }

    var erpRiskTarget = event.target.closest("[data-erp-risk]");
    if (erpRiskTarget) {
      currentErpRiskFilter = erpRiskTarget.getAttribute("data-erp-risk") || "全部ERP库存";
      currentGroupFilter = "全部";
      renderResults();
      return;
    }

    var businessRiskTarget = event.target.closest("[data-business-risk]");
    if (businessRiskTarget) {
      currentBusinessRiskFilter = businessRiskTarget.getAttribute("data-business-risk") || "全部业务风险";
      currentGroupFilter = "全部";
      renderResults();
      return;
    }

    var compareTarget = event.target.closest("[data-price-compare]");
    if (compareTarget) {
      currentPriceCompareFilter = compareTarget.getAttribute("data-price-compare") || "all";
      currentGroupFilter = "全部";
      renderResults();
      return;
    }

    var groupTarget = event.target.closest("[data-toggle-group]");
    if (!groupTarget) {
      return;
    }
    var group = groupTarget.getAttribute("data-toggle-group");
    collapsedGroups[group] = !collapsedGroups[group];
    renderResults();
  });

  logToggle.addEventListener("click", function(event) {
    var header = event.target.closest(".log-group-header");
    if (header) {
      var parent = header.parentElement;
      if (parent) {
        parent.classList.toggle("collapsed");
      }
      return;
    }
    logVisible = !logVisible;
    logBody.hidden = !logVisible;
  });

  logEntries.addEventListener("click", function(event) {
    var header = event.target.closest(".log-group-header");
    if (!header) {
      return;
    }
    var parent = header.parentElement;
    if (parent) {
      parent.classList.toggle("collapsed");
    }
  });

  loadFromLS();
  loadOperationLogs();
  loadPreviousResults();
  loadPreviousResultsFromServer();
  loadErpConfig();
  loadInventoryStatus();
  renderDashboard();
})();
