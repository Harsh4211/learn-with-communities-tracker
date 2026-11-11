/**
 * Learn With Communities Campaign Tracker - Frontend Application
 */

document.addEventListener("DOMContentLoaded", () => {
  // Lucide Icons initialization
  if (window.lucide) lucide.createIcons();

  // App State
  const state = {
    records: [],
    results: [],
    filter: "ALL",
    searchQuery: "",
    isScanning: false,
    campaignBadges: [],
    eventSource: null
  };

  // DOM Elements
  const btnLoadSample = document.getElementById("btnLoadSample");
  const csvFileInput = document.getElementById("csvFileInput");
  const btnSingleUrl = document.getElementById("btnSingleUrl");
  const btnStartScan = document.getElementById("btnStartScan");
  const btnExportCsv = document.getElementById("btnExportCsv");
  const btnToggleBadgesModal = document.getElementById("btnToggleBadgesModal");
  const searchInput = document.getElementById("searchInput");
  const rateLimitSlider = document.getElementById("rateLimitSlider");
  const rateLimitVal = document.getElementById("rateLimitVal");
  const concurrencySelect = document.getElementById("concurrencySelect");

  // KPI elements
  const statTotal = document.getElementById("statTotal");
  const statCompleted = document.getElementById("statCompleted");
  const statCompletedPct = document.getElementById("statCompletedPct");
  const statInProgress = document.getElementById("statInProgress");
  const statNotStarted = document.getElementById("statNotStarted");
  const statPrivate = document.getElementById("statPrivate");

  // Filter Counts
  const countAll = document.getElementById("countAll");
  const countCompleted = document.getElementById("countCompleted");
  const countInProgress = document.getElementById("countInProgress");
  const countNotStarted = document.getElementById("countNotStarted");
  const countPrivate = document.getElementById("countPrivate");

  // Progress Elements
  const progressBar = document.getElementById("progressBar");
  const progressPercent = document.getElementById("progressPercent");
  const progressDetails = document.getElementById("progressDetails");
  const scanStatusDot = document.getElementById("scanStatusDot");
  const scanStatusText = document.getElementById("scanStatusText");
  const candidatesTableBody = document.getElementById("candidatesTableBody");

  // Modals
  const candidateModal = document.getElementById("candidateModal");
  const btnCloseModal = document.getElementById("btnCloseModal");
  const btnCloseModalBottom = document.getElementById("btnCloseModalBottom");
  const campaignBadgesModal = document.getElementById("campaignBadgesModal");
  const btnCloseBadgesModal = document.getElementById("btnCloseBadgesModal");
  const singleUrlModal = document.getElementById("singleUrlModal");
  const btnCloseSingleUrlModal = document.getElementById("btnCloseSingleUrlModal");
  const btnCancelSingleUrl = document.getElementById("btnCancelSingleUrl");
  const btnSubmitSingleUrl = document.getElementById("btnSubmitSingleUrl");
  const singleUrlInput = document.getElementById("singleUrlInput");

  // Rate limit slider change
  rateLimitSlider.addEventListener("input", (e) => {
    rateLimitVal.textContent = `${parseFloat(e.target.value).toFixed(1)}s`;
  });

  // Fetch Campaign Badges Reference on init
  async function loadCampaignBadges() {
    try {
      const res = await fetch("/api/campaign-badges");
      const data = await res.json();
      state.campaignBadges = data.badges || [];
      renderOfficialBadgesModal();
    } catch (err) {
      console.error("Failed to load campaign badges", err);
    }
  }

  // Load Sample CSV on click
  btnLoadSample.addEventListener("click", async () => {
    try {
      progressDetails.textContent = "Loading sample candidate dataset...";
      const res = await fetch("/api/sample-csv");
      const data = await res.json();
      state.records = data.records || [];
      state.results = state.records.map((r, i) => ({
        url: r.url,
        original_info: r.info,
        name: r.name || `Candidate #${i+1}`,
        status: "PENDING",
        status_label: "Pending Verification",
        campaign_completed: 0,
        campaign_total: 10,
        completion_percentage: 0,
        total_badges: 0,
        earned_campaign_badges: [],
        missing_campaign_badges: state.campaignBadges
      }));

      updateStats();
      renderTable();
      progressDetails.textContent = `Loaded ${state.records.length} sample candidate profiles. Click "Start Live Verification".`;
      if (window.lucide) lucide.createIcons();
    } catch (err) {
      alert("Error loading sample CSV: " + err.message);
    }
  });

  // CSV File Upload
  csvFileInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    progressDetails.textContent = `Uploading ${file.name}...`;
    try {
      const res = await fetch("/api/upload-csv", { method: "POST", body: formData });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Upload failed");
      }
      const data = await res.json();
      state.records = data.records || [];
      state.results = state.records.map((r, i) => ({
        url: r.url,
        original_info: r.info,
        name: r.name || `Candidate #${i+1}`,
        status: "PENDING",
        status_label: "Pending Verification",
        campaign_completed: 0,
        campaign_total: 10,
        completion_percentage: 0,
        total_badges: 0,
        earned_campaign_badges: [],
        missing_campaign_badges: state.campaignBadges
      }));

      updateStats();
      renderTable();
      progressDetails.textContent = `Loaded ${state.records.length} candidates from ${file.name}. Ready to verify.`;
      if (window.lucide) lucide.createIcons();
    } catch (err) {
      alert("Error uploading CSV: " + err.message);
    }
  });

  // Start Live Scan via SSE
  btnStartScan.addEventListener("click", () => {
    if (state.isScanning) return;
    if (state.records.length === 0) {
      alert("Please load or upload candidate CSV records first!");
      return;
    }

    startLiveVerification();
  });

  function startLiveVerification() {
    state.isScanning = true;
    btnStartScan.disabled = true;
    btnStartScan.classList.add("opacity-50", "cursor-not-allowed");
    scanStatusDot.className = "w-2.5 h-2.5 rounded-full bg-googleYellow scanning-pulse";
    scanStatusText.textContent = "Scanning active profiles...";
    progressBar.style.width = "0%";
    progressPercent.textContent = "0%";

    const delay = rateLimitSlider.value;
    const concurrency = concurrencySelect.value;
    const sseUrl = `/api/scan-stream?delay=${delay}&concurrency=${concurrency}`;

    if (state.eventSource) {
      state.eventSource.close();
    }

    state.eventSource = new EventSource(sseUrl);

    state.eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "start") {
          progressDetails.textContent = `Starting verification of ${payload.total} candidates...`;
        } else if (payload.type === "progress") {
          const item = payload.item;
          const curr = payload.current;
          const tot = payload.total;
          const pct = Math.round((curr / tot) * 100);

          progressBar.style.width = `${pct}%`;
          progressPercent.textContent = `${pct}%`;
          progressDetails.textContent = `[${curr}/${tot}] Verified ${item.name} (${item.campaign_completed}/10 badges)`;

          // Update result in state
          const matchIdx = state.results.findIndex(r => r.url === item.url);
          if (matchIdx !== -1) {
            state.results[matchIdx] = item;
          } else {
            state.results.push(item);
          }

          updateStats();
          renderTable();
          if (window.lucide) lucide.createIcons();
        } else if (payload.type === "complete") {
          state.isScanning = false;
          btnStartScan.disabled = false;
          btnStartScan.classList.remove("opacity-50", "cursor-not-allowed");
          scanStatusDot.className = "w-2.5 h-2.5 rounded-full bg-googleGreen";
          scanStatusText.textContent = "Verification Complete";
          progressDetails.textContent = `All ${payload.summary.total} profiles verified! ${payload.summary.completed} achieved 10/10.`;
          progressBar.style.width = "100%";
          progressPercent.textContent = "100%";

          state.eventSource.close();
          state.eventSource = null;

          // Confetti celebration if anyone completed!
          if (payload.summary.completed > 0 && window.confetti) {
            triggerConfetti();
          }
        } else if (payload.type === "error") {
          alert("Scan error: " + payload.message);
          state.isScanning = false;
          btnStartScan.disabled = false;
          btnStartScan.classList.remove("opacity-50", "cursor-not-allowed");
          state.eventSource.close();
        }
      } catch (e) {
        console.error("SSE parse error", e);
      }
    };

    state.eventSource.onerror = (err) => {
      console.warn("SSE stream closed or interrupted", err);
      state.isScanning = false;
      btnStartScan.disabled = false;
      btnStartScan.classList.remove("opacity-50", "cursor-not-allowed");
      if (state.eventSource) state.eventSource.close();
    };
  }

  // Confetti effect
  function triggerConfetti() {
    window.confetti({
      particleCount: 80,
      spread: 70,
      origin: { y: 0.6 }
    });
  }

  // Update Stats & Counts
  function updateStats() {
    const total = state.results.length;
    const completed = state.results.filter(r => r.status === "COMPLETED").length;
    const inProgress = state.results.filter(r => r.status === "IN_PROGRESS").length;
    const notStarted = state.results.filter(r => r.status === "NOT_STARTED").length;
    const privateProfiles = state.results.filter(r => r.status === "PRIVATE_PROFILE").length;

    statTotal.textContent = total;
    statCompleted.textContent = completed;
    statCompletedPct.textContent = total > 0 ? `(${Math.round(completed / total * 100)}%)` : "(0%)";
    statInProgress.textContent = inProgress;
    statNotStarted.textContent = notStarted;
    statPrivate.textContent = privateProfiles;

    countAll.textContent = total;
    countCompleted.textContent = completed;
    countInProgress.textContent = inProgress;
    countNotStarted.textContent = notStarted;
    countPrivate.textContent = privateProfiles;
  }

  // Filter Tabs click
  document.querySelectorAll(".filter-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".filter-tab").forEach(t => {
        t.classList.remove("active", "bg-slate-800", "text-white");
        t.classList.add("text-slate-400");
      });
      tab.classList.add("active", "bg-slate-800", "text-white");
      tab.classList.remove("text-slate-400");

      state.filter = tab.dataset.filter;
      renderTable();
      if (window.lucide) lucide.createIcons();
    });
  });

  // Search input live filtering
  searchInput.addEventListener("input", (e) => {
    state.searchQuery = e.target.value.toLowerCase().trim();
    renderTable();
    if (window.lucide) lucide.createIcons();
  });

  // Render Candidates Table
  function renderTable() {
    let list = state.results;

    // Apply Filter
    if (state.filter !== "ALL") {
      list = list.filter(r => r.status === state.filter);
    }

    // Apply Search
    if (state.searchQuery) {
      list = list.filter(r => {
        const name = (r.name || "").toLowerCase();
        const url = (r.url || "").toLowerCase();
        const info = (r.original_info || "").toLowerCase();
        const badges = (r.earned_campaign_badges || []).map(b => b.title.toLowerCase()).join(" ");
        return name.includes(state.searchQuery) || url.includes(state.searchQuery) || info.includes(state.searchQuery) || badges.includes(state.searchQuery);
      });
    }

    if (list.length === 0) {
      candidatesTableBody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center py-10 text-slate-500">
            <i data-lucide="search-x" class="w-6 h-6 mx-auto mb-1 opacity-50"></i>
            No candidate records found matching current filter or search criteria.
          </td>
        </tr>
      `;
      return;
    }

    candidatesTableBody.innerHTML = list.map((c, idx) => {
      const completed = c.campaign_completed || 0;
      const total = c.campaign_total || 10;
      const pct = c.completion_percentage || 0;

      // Status chip styling
      let statusChip = "";
      let barColor = "bg-slate-700";

      if (c.status === "COMPLETED") {
        statusChip = `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <i data-lucide="check-circle" class="w-3.5 h-3.5"></i> 10/10 Completed
        </span>`;
        barColor = "bg-emerald-500";
      } else if (c.status === "IN_PROGRESS") {
        statusChip = `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">
          <i data-lucide="hourglass" class="w-3.5 h-3.5"></i> ${completed}/10 In Progress
        </span>`;
        barColor = "bg-yellow-500";
      } else if (c.status === "PRIVATE_PROFILE") {
        statusChip = `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-500/15 text-red-400 border border-red-500/30" title="Account profile is set to private. Make it public in settings.">
          <i data-lucide="lock" class="w-3.5 h-3.5"></i> Private Profile
        </span>`;
        barColor = "bg-red-500";
      } else if (c.status === "NOT_STARTED") {
        statusChip = `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
          <i data-lucide="circle" class="w-3.5 h-3.5"></i> 0/10 Not Started
        </span>`;
      } else {
        statusChip = `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-500">
          <i data-lucide="clock" class="w-3.5 h-3.5"></i> Pending
        </span>`;
      }

      const defaultAvatar = "https://www.gstatic.com/images/branding/product/2x/avatar_square_grey_96dp.png";
      const avatarSrc = c.avatar || defaultAvatar;

      return `
        <tr class="hover:bg-slate-900/50 transition-colors">
          <td class="py-3.5 px-4 text-center font-mono text-slate-500">${idx + 1}</td>
          <td class="py-3.5 px-4">
            <div class="flex items-center gap-3">
              <img src="${avatarSrc}" alt="avatar" class="w-9 h-9 rounded-xl border border-slate-700 object-cover bg-slate-800" onerror="this.src='${defaultAvatar}'">
              <div>
                <div class="font-semibold text-slate-100 flex items-center gap-1.5">
                  ${escapeHtml(c.name || 'Unknown')}
                  ${c.league ? `<span class="text-[10px] px-1.5 py-0.2 bg-slate-800 text-slate-400 rounded border border-slate-700">${escapeHtml(c.league)}</span>` : ''}
                </div>
                <a href="${c.url}" target="_blank" class="text-[11px] text-googleBlue hover:underline flex items-center gap-1 mt-0.5 font-mono truncate max-w-xs">
                  ${truncate(c.url, 40)} <i data-lucide="external-link" class="w-2.5 h-2.5 flex-shrink-0"></i>
                </a>
              </div>
            </div>
          </td>
          <td class="py-3.5 px-4 font-mono font-bold text-slate-200">
            <span class="text-sm ${completed === 10 ? 'text-emerald-400 font-extrabold' : (completed > 0 ? 'text-yellow-400' : 'text-slate-400')}">${completed}</span>
            <span class="text-xs text-slate-500">/ 10</span>
          </td>
          <td class="py-3.5 px-4 text-center">
            <div class="w-28 mx-auto space-y-1">
              <div class="flex justify-between text-[10px] text-slate-400 font-mono">
                <span>Progress</span>
                <span class="font-semibold text-slate-300">${pct}%</span>
              </div>
              <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div class="${barColor} h-full rounded-full transition-all duration-300" style="width: ${pct}%"></div>
              </div>
            </div>
          </td>
          <td class="py-3.5 px-4 text-center whitespace-nowrap">
            ${statusChip}
          </td>
          <td class="py-3.5 px-4 text-center font-mono text-cyan-400 font-semibold">
            ${c.total_badges || 0}
          </td>
          <td class="py-3.5 px-4 text-xs text-slate-400 max-w-xs truncate" title="${escapeHtml(c.original_info || '')}">
            ${escapeHtml(c.original_info || '—')}
          </td>
          <td class="py-3.5 px-4 text-right">
            <button onclick="openCandidateDetails('${c.url}')" class="px-3 py-1.5 text-xs font-semibold bg-slate-800 hover:bg-slate-700 hover:text-white text-slate-300 border border-slate-700 rounded-lg inline-flex items-center gap-1.5 transition-all shadow-sm">
              <i data-lucide="eye" class="w-3.5 h-3.5 text-googleBlue"></i>
              Badges
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  // Open Candidate Details Modal
  window.openCandidateDetails = (url) => {
    const candidate = state.results.find(r => r.url === url);
    if (!candidate) return;

    document.getElementById("modalName").textContent = candidate.name || "Candidate Profile";
    document.getElementById("modalAvatar").src = candidate.avatar || "https://www.gstatic.com/images/branding/product/2x/avatar_square_grey_96dp.png";
    document.getElementById("modalProfileLink").href = candidate.url;
    document.getElementById("modalBadgeScore").textContent = `${candidate.campaign_completed || 0} / 10 Badges Completed`;

    const chip = document.getElementById("modalStatusChip");
    chip.textContent = candidate.status_label || candidate.status;
    if (candidate.status === "COMPLETED") {
      chip.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
    } else if (candidate.status === "IN_PROGRESS") {
      chip.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-yellow-500/20 text-yellow-400 border border-yellow-500/30";
    } else if (candidate.status === "PRIVATE_PROFILE") {
      chip.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-red-500/20 text-red-400 border border-red-500/30";
    } else {
      chip.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-slate-800 text-slate-400";
    }

    // Render 10 Badges Checklist
    const earnedTitles = new Set((candidate.earned_campaign_badges || []).map(b => b.title.toLowerCase().trim()));
    const earnedDetails = new Map((candidate.earned_campaign_badges || []).map(b => [b.title.toLowerCase().trim(), b]));

    const modalBadgesList = document.getElementById("modalBadgesList");
    modalBadgesList.innerHTML = state.campaignBadges.map((badge, idx) => {
      const isEarned = earnedTitles.has(badge.title.toLowerCase().trim());
      const details = earnedDetails.get(badge.title.toLowerCase().trim());
      const earnedDate = details ? details.earned_date : null;
      const badgeImg = details && details.badge_image ? details.badge_image : "https://cdn.qwiklabs.com/Ep488ur7qy53c%2Fwb0D1OS%2BeWzeTrNgXPu2ZbDDurm3E%3D";

      if (isEarned) {
        return `
          <div class="p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-950/20 flex items-start gap-3 shadow-sm">
            <img src="${badgeImg}" alt="badge" class="w-12 h-12 rounded-xl object-contain bg-slate-900 border border-emerald-500/30 p-1 flex-shrink-0">
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between gap-1">
                <span class="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">${escapeHtml(badge.category)}</span>
                <span class="text-[10px] font-bold text-emerald-400 bg-emerald-500/20 px-1.5 py-0.5 rounded-md flex items-center gap-1">
                  <i data-lucide="check" class="w-3 h-3"></i> Completed
                </span>
              </div>
              <h5 class="text-xs font-bold text-white mt-0.5 leading-snug">${escapeHtml(badge.title)}</h5>
              <p class="text-[11px] text-emerald-300/80 mt-1 flex items-center gap-1 font-mono">
                <i data-lucide="calendar" class="w-3 h-3 text-emerald-400"></i> Earned: ${escapeHtml(earnedDate || 'Verified')}
              </p>
            </div>
          </div>
        `;
      } else {
        return `
          <div class="p-3.5 rounded-xl border border-slate-800 bg-slate-900/40 flex items-start gap-3 opacity-60">
            <div class="w-12 h-12 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-500 flex-shrink-0">
              <i data-lucide="award" class="w-6 h-6"></i>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between gap-1">
                <span class="text-[11px] font-medium text-slate-400 uppercase tracking-wider">${escapeHtml(badge.category)}</span>
                <span class="text-[10px] font-medium text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded-md flex items-center gap-1">
                  <i data-lucide="x" class="w-3 h-3"></i> Missing
                </span>
              </div>
              <h5 class="text-xs font-semibold text-slate-300 mt-0.5 leading-snug">${escapeHtml(badge.title)}</h5>
              <p class="text-[10px] text-slate-500 mt-1">Pending campaign completion</p>
            </div>
          </div>
        `;
      }
    }).join("");

    // Other Badges
    const otherBadges = candidate.other_badges || [];
    const otherContainer = document.getElementById("modalOtherBadgesContainer");
    const otherList = document.getElementById("modalOtherBadgesList");
    if (otherBadges.length > 0) {
      otherContainer.classList.remove("hidden");
      otherList.innerHTML = otherBadges.map(b => `
        <span class="px-2.5 py-1 text-[11px] rounded-lg bg-slate-800 text-slate-300 border border-slate-700 font-medium">
          ${escapeHtml(b.title)}
        </span>
      `).join("");
    } else {
      otherContainer.classList.add("hidden");
    }

    candidateModal.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
  };

  // Close modals
  btnCloseModal.addEventListener("click", () => candidateModal.classList.add("hidden"));
  btnCloseModalBottom.addEventListener("click", () => candidateModal.classList.add("hidden"));
  candidateModal.addEventListener("click", (e) => {
    if (e.target === candidateModal) candidateModal.classList.add("hidden");
  });

  // Official Badges Reference Modal
  btnToggleBadgesModal.addEventListener("click", () => {
    campaignBadgesModal.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
  });
  btnCloseBadgesModal.addEventListener("click", () => campaignBadgesModal.classList.add("hidden"));
  campaignBadgesModal.addEventListener("click", (e) => {
    if (e.target === campaignBadgesModal) campaignBadgesModal.classList.add("hidden");
  });

  function renderOfficialBadgesModal() {
    const list = document.getElementById("officialBadgesList");
    list.innerHTML = state.campaignBadges.map((b, i) => `
      <div class="p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-start gap-3.5">
        <span class="w-7 h-7 rounded-lg bg-googleBlue/20 text-googleBlue flex items-center justify-center font-bold text-xs flex-shrink-0">
          ${i + 1}
        </span>
        <div class="flex-1">
          <div class="flex items-center gap-2">
            <h4 class="text-xs font-bold text-white">${escapeHtml(b.title)}</h4>
            <span class="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">${escapeHtml(b.category)}</span>
          </div>
          <p class="text-xs text-slate-400 mt-1">${escapeHtml(b.description)}</p>
        </div>
      </div>
    `).join("");
  }

  // Single URL Check Modal
  btnSingleUrl.addEventListener("click", () => {
    singleUrlInput.value = "";
    singleUrlModal.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
  });
  btnCloseSingleUrlModal.addEventListener("click", () => singleUrlModal.classList.add("hidden"));
  btnCancelSingleUrl.addEventListener("click", () => singleUrlModal.classList.add("hidden"));

  btnSubmitSingleUrl.addEventListener("click", async () => {
    const url = singleUrlInput.value.trim();
    if (!url) return;
    singleUrlModal.classList.add("hidden");

    progressDetails.textContent = `Verifying candidate URL: ${url}...`;
    try {
      const res = await fetch("/api/check-single", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url })
      });
      const data = await res.json();

      // Add or update
      const existingIdx = state.results.findIndex(r => r.url === data.url);
      if (existingIdx !== -1) {
        state.results[existingIdx] = data;
      } else {
        state.results.unshift(data);
      }

      updateStats();
      renderTable();
      openCandidateDetails(data.url);
      progressDetails.textContent = `Verified ${data.name} (${data.campaign_completed}/10 badges)`;
      if (window.lucide) lucide.createIcons();
    } catch (err) {
      alert("Verification error: " + err.message);
    }
  });

  // Export to CSV
  btnExportCsv.addEventListener("click", () => {
    if (state.results.length === 0) {
      alert("No verification results available to export!");
      return;
    }
    window.location.href = "/api/export/csv";
  });

  // Helpers
  function escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function truncate(str, len) {
    if (!str) return "";
    return str.length > len ? str.substring(0, len) + "..." : str;
  }

  // Kickstart
  loadCampaignBadges();
  // Auto-click sample on initial load for instant demonstration
  btnLoadSample.click();
});
