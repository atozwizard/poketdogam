const elements = {
  rotomLine: document.querySelector("#rotomLine"),
  datasetVersion: document.querySelector("#datasetVersion"),
  systemStatus: document.querySelector("#systemStatus"),
  llmRuntime: document.querySelector("#llmRuntime"),
  lens: document.querySelector("#lens"),
  lensState: document.querySelector("#lensState"),
  lensScore: document.querySelector("#lensScore"),
  cameraInput: document.querySelector("#cameraInput"),
  imageScanButton: document.querySelector("#imageScanButton"),
  scanPreview: document.querySelector("#scanPreview"),
  uploadHint: document.querySelector("#uploadHint"),
  scanGuidance: document.querySelector("#scanGuidance"),
  ocrText: document.querySelector("#ocrText"),
  scanButton: document.querySelector("#scanButton"),
  clearButton: document.querySelector("#clearButton"),
  searchInput: document.querySelector("#searchInput"),
  searchButton: document.querySelector("#searchButton"),
  candidateList: document.querySelector("#candidateList"),
  detailEmpty: document.querySelector("#detailEmpty"),
  detailCard: document.querySelector("#detailCard"),
  detailNumber: document.querySelector("#detailNumber"),
  detailName: document.querySelector("#detailName"),
  detailEnglish: document.querySelector("#detailEnglish"),
  typeBadges: document.querySelector("#typeBadges"),
  detailHeight: document.querySelector("#detailHeight"),
  detailWeight: document.querySelector("#detailWeight"),
  detailForm: document.querySelector("#detailForm"),
  detailGeneration: document.querySelector("#detailGeneration"),
  detailVersion: document.querySelector("#detailVersion"),
  detailSource: document.querySelector("#detailSource"),
  detailUpdated: document.querySelector("#detailUpdated"),
  statBars: document.querySelector("#statBars"),
  typeMatchups: document.querySelector("#typeMatchups"),
  evolutionList: document.querySelector("#evolutionList"),
  saveButton: document.querySelector("#saveButton"),
  detailNarrationButton: document.querySelector("#detailNarrationButton"),
  saveHint: document.querySelector("#saveHint"),
  chatLog: document.querySelector("#chatLog"),
  chatInput: document.querySelector("#chatInput"),
  chatButton: document.querySelector("#chatButton"),
  suggestRow: document.querySelector("#suggestRow"),
  rotomFace: document.querySelector("#rotomFace"),
  faceScreen: document.querySelector(".face-screen"),
  dexShell: document.querySelector(".dex-shell"),
  llmBadge: document.querySelector("#llmBadge"),
  voiceStatus: document.querySelector("#voiceStatus"),
  voiceMode: document.querySelector("#voiceMode"),
  voiceStyleLabel: document.querySelector("#voiceStyleLabel"),
  voicePolicy: document.querySelector("#voicePolicy"),
  voiceScript: document.querySelector("#voiceScript"),
  voicePitch: document.querySelector("#voicePitch"),
  voiceSpeed: document.querySelector("#voiceSpeed"),
  voicePreviewButton: document.querySelector("#voicePreviewButton"),
  voiceStopButton: document.querySelector("#voiceStopButton"),
  autoNarration: document.querySelector("#autoNarration"),
  collectionList: document.querySelector("#collectionList"),
  collectionCount: document.querySelector("#collectionCount"),
  collectionFilter: document.querySelector("#collectionFilter"),
  exportButton: document.querySelector("#exportButton"),
  clearDataButton: document.querySelector("#clearDataButton"),
  qualitySummary: document.querySelector("#qualitySummary"),
  toast: document.querySelector("#toast"),
};

const appState = {
  candidates: [],
  selected: null,
  detail: null,
  confirmed: false,
  latestScanEventId: null,
  collection: loadCollection(),
  qualityEvents: loadQualityEvents(),
  selectedFile: null,
  previewUrl: null,
  collectionQuery: "",
  voiceStyle: "electric_device",
  audioContext: null,
  autoNarration: localStorage.getItem("poketdogam.autoNarration") === "true",
  sessionId: localStorage.getItem("poketdogam.sessionId") || null,
};

const statLabels = {
  hp: "HP",
  attack: "공격",
  defense: "방어",
  sp_attack: "특수공격",
  sp_defense: "특수방어",
  speed: "스피드",
  bst: "합계",
};

const typeLabels = {
  normal: "노말",
  fire: "불꽃",
  water: "물",
  electric: "전기",
  grass: "풀",
  ice: "얼음",
  fighting: "격투",
  poison: "독",
  ground: "땅",
  flying: "비행",
  psychic: "에스퍼",
  bug: "벌레",
  rock: "바위",
  ghost: "고스트",
  dragon: "드래곤",
  dark: "악",
  steel: "강철",
  fairy: "페어리",
};

const statusLabels = {
  idle: "준비",
  scanning: "분석 중",
  locked: "확정",
  low_confidence: "확인 필요",
  error: "오류",
};

const formLabels = {
  base: "기본",
  alola: "알로라",
  galar: "가라르",
  hisui: "히스이",
  paldea: "팔데아",
  mega: "메가",
  gmax: "거다이맥스",
  x: "X",
  y: "Y",
};

const voiceStyleLabels = {
  electric_device: "전기 디바이스",
  bright_guide: "맑은 안내",
  machine_pulse: "기계 펄스",
};

document.querySelectorAll(".nav-button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-button").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    document.querySelector(`#${button.dataset.target}`).scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

document.querySelectorAll("[data-sample]").forEach((button) => {
  button.addEventListener("click", () => {
    elements.ocrText.value = button.dataset.sample;
    setStatus("idle", "샘플 장전 완료다-로.", "READY");
  });
});

elements.scanButton.addEventListener("click", scanText);
elements.cameraInput.addEventListener("change", handleImageSelection);
elements.imageScanButton.addEventListener("click", scanImage);
elements.clearButton.addEventListener("click", () => {
  appState.candidates = [];
  appState.selected = null;
  appState.detail = null;
  appState.confirmed = false;
  appState.latestScanEventId = null;
  elements.ocrText.value = "";
  elements.cameraInput.value = "";
  appState.selectedFile = null;
  if (appState.previewUrl) {
    URL.revokeObjectURL(appState.previewUrl);
    appState.previewUrl = null;
  }
  elements.scanPreview.removeAttribute("src");
  elements.scanPreview.hidden = true;
  elements.imageScanButton.disabled = true;
  elements.uploadHint.textContent = "PNG·JPEG·WebP·HEIC·TIFF, 최대 8MB";
  elements.scanGuidance.textContent = "이미지를 선택하거나 이름을 검색하면 후보가 표시됩니다.";
  elements.lensScore.textContent = "match --";
  renderCandidates();
  renderDetail();
  setStatus("idle", "렌즈 대기 중이다-로.", "READY");
});

elements.searchButton.addEventListener("click", searchPokedex);
elements.searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    searchPokedex();
  }
});

elements.collectionFilter.addEventListener("input", () => {
  appState.collectionQuery = elements.collectionFilter.value.trim().toLowerCase();
  renderCollection();
});
elements.exportButton.addEventListener("click", exportLocalData);
elements.clearDataButton.addEventListener("click", clearLocalData);

elements.saveButton.addEventListener("click", () => {
  if (!appState.detail) {
    showToast("저장할 도감 데이터가 없습니다.");
    return;
  }
  if (!appState.confirmed) {
    showToast("후보를 먼저 확정하세요.");
    return;
  }

  const now = new Date().toISOString();
  const existing = appState.collection.find((item) => item.form_id === appState.detail.form_id);
  const saved = {
    form_id: appState.detail.form_id,
    pokemon_id: appState.detail.pokemon_id,
    name_ko: appState.detail.name_ko,
    types: appState.detail.types,
    discovered_count: Number(existing?.discovered_count || 0) + 1,
    first_saved_at: existing?.first_saved_at || existing?.saved_at || now,
    last_saved_at: now,
    favorite: Boolean(existing?.favorite),
  };
  appState.collection = [
    saved,
    ...appState.collection.filter((item) => item.form_id !== appState.detail.form_id),
  ];
  saveCollection(appState.collection);
  renderCollection();
  showToast(`${appState.detail.name_ko} ${saved.discovered_count}회 발견`);
});

elements.chatButton.addEventListener("click", sendChat);
elements.chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    sendChat();
  }
});

document.querySelectorAll("[data-voice-style]").forEach((button) => {
  button.addEventListener("click", () => {
    appState.voiceStyle = button.dataset.voiceStyle;
    document.querySelectorAll("[data-voice-style]").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    elements.voiceStyleLabel.textContent = voiceStyleLabels[appState.voiceStyle] || "전기 디바이스";
  });
});

elements.voicePreviewButton.addEventListener("click", previewVoice);
elements.voiceStopButton.addEventListener("click", stopVoice);
elements.detailNarrationButton.addEventListener("click", () => loadNarration(true));
elements.autoNarration.checked = appState.autoNarration;
elements.autoNarration.addEventListener("change", () => {
  appState.autoNarration = elements.autoNarration.checked;
  localStorage.setItem("poketdogam.autoNarration", String(appState.autoNarration));
  showToast(appState.autoNarration ? "폼 확정 후 자동 낭독을 켰습니다." : "자동 낭독을 껐습니다.");
});

async function scanText() {
  const ocrText = elements.ocrText.value.trim();
  if (!ocrText) {
    setStatus("error", "읽을 텍스트가 없다-로.", "EMPTY");
    showToast("OCR Text를 입력하세요.");
    return;
  }

  setStatus("scanning", "전기 신호 분석 중이다-로.", "SCAN");
  elements.scanButton.disabled = true;

  try {
    const response = await fetch("/v1/scan/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ocr_text: ocrText, filename: "rotom-ui-fixture.txt" }),
    });
    if (!response.ok) {
      throw new Error(`scan failed: ${response.status}`);
    }
    const data = await response.json();
    appState.candidates = data.top_candidates || [];
    appState.selected = appState.candidates[0] || null;
    appState.confirmed = Boolean(appState.selected) && !data.requires_user_confirmation;
    appState.latestScanEventId = data.event_id || null;
    recordQualityEvent(data, appState.selected, appState.confirmed ? "matcher_test" : "matcher_test_pending", "matcher_only");
    elements.scanGuidance.textContent = data.guidance || "개발용 텍스트 매처 결과입니다.";
    renderCandidates();

    if (!appState.selected) {
      setStatus("error", "후보를 못 찾았다-로.", "MISS");
      renderDetail();
      return;
    }

    const topScore = Number(appState.selected.confidence || 0);
    const status = data.requires_user_confirmation ? "low_confidence" : "locked";
    const line = data.requires_user_confirmation
      ? "후보를 확인해줘-로."
      : `${appState.selected.name_ko} 잠금 완료다-로.`;
    setStatus(status, line, data.requires_user_confirmation ? "CHECK" : "LOCK");
    elements.lensScore.textContent = `match ${Math.round(topScore * 100)}%`;
    await loadDetail(appState.selected.form_id);
  } catch (error) {
    setStatus("error", "스캔 회로가 끊겼다-로.", "ERROR");
    showToast(error.message);
  } finally {
    elements.scanButton.disabled = false;
  }
}

function handleImageSelection() {
  const file = elements.cameraInput.files?.[0] || null;
  if (!file) {
    return;
  }
  if (file.size > 8 * 1024 * 1024) {
    elements.cameraInput.value = "";
    showToast("이미지는 8MB 이하여야 합니다.");
    return;
  }
  appState.selectedFile = file;
  if (appState.previewUrl) {
    URL.revokeObjectURL(appState.previewUrl);
  }
  appState.previewUrl = URL.createObjectURL(file);
  elements.scanPreview.src = appState.previewUrl;
  elements.scanPreview.hidden = false;
  elements.imageScanButton.disabled = false;
  elements.uploadHint.textContent = `${file.name} · ${formatBytes(file.size)} · 분석 전`;
  elements.scanGuidance.textContent = "이미지는 분석 중에만 사용되며 서버에 보관되지 않습니다.";
  setStatus("idle", "이미지 장전 완료. 이름과 외형을 함께 분석할게-로.", "READY");
}

async function scanImage() {
  if (!appState.selectedFile) {
    showToast("먼저 포켓몬 이미지를 선택하세요.");
    return;
  }
  const formData = new FormData();
  formData.append("image", appState.selectedFile, appState.selectedFile.name);
  setStatus("scanning", "이름과 외형 신호를 결합하는 중이다-로.", "FUSION");
  elements.imageScanButton.disabled = true;
  try {
    const response = await fetch("/v1/scan", { method: "POST", body: formData });
    const data = await readJsonResponse(response);
    appState.candidates = data.top_candidates || [];
    appState.selected = appState.candidates[0] || null;
    appState.confirmed = Boolean(appState.selected) && !data.requires_user_confirmation;
    appState.latestScanEventId = data.event_id || null;
    recordQualityEvent(
      data,
      appState.selected,
      appState.confirmed ? "auto" : "pending",
      data.recognition_mode || "image_ocr",
    );
    elements.uploadHint.textContent =
      `${appState.selectedFile.name} · ${data.recognition_mode || data.ocr_engine} · ${Math.round(data.latency_ms)}ms`;
    elements.scanGuidance.textContent = data.guidance || "";
    renderCandidates();
    if (!appState.selected) {
      appState.detail = null;
      renderDetail();
      setStatus("error", "이름을 읽지 못했어. 검색으로 이어가줘-로.", "MISS");
      elements.searchInput.focus();
      return;
    }
    const topScore = Number(appState.selected.confidence || 0);
    const status = data.requires_user_confirmation ? "low_confidence" : "locked";
    setStatus(
      status,
      data.requires_user_confirmation
        ? "비슷한 후보가 있어. 맞는 이름을 골라줘-로."
        : `${appState.selected.name_ko} 후보가 가장 강해-로.`,
      data.requires_user_confirmation ? "CHECK" : "LOCK",
    );
    elements.lensScore.textContent = `일치도 ${Math.round(topScore * 100)}%`;
    await loadDetail(appState.selected.form_id);
  } catch (error) {
    setStatus("error", "이미지 분석에 실패했어. 이름 검색을 사용해줘-로.", "ERROR");
    elements.scanGuidance.textContent = error.message;
    showToast(error.message);
  } finally {
    elements.imageScanButton.disabled = false;
  }
}

async function searchPokedex() {
  const query = elements.searchInput.value.trim();
  if (!query) {
    showToast("검색할 이름을 입력하세요.");
    return;
  }

  elements.searchButton.disabled = true;
  setStatus("scanning", "이름 색인을 찾는 중이다-로.", "SEARCH");
  try {
    const response = await fetch(`/v1/pokedex/search?query=${encodeURIComponent(query)}&limit=10`);
    const data = await readJsonResponse(response);
    appState.candidates = data.matches || [];
    appState.selected = null;
    appState.detail = null;
    appState.confirmed = false;
    appState.latestScanEventId = null;
    elements.datasetVersion.textContent = data.dataset_version || "unknown";
    elements.lensScore.textContent = `${appState.candidates.length} candidates`;
    renderCandidates();
    renderDetail();
    elements.scanGuidance.textContent = appState.candidates.length
      ? "검색 결과는 자동 확정하지 않습니다. 정확한 폼을 선택하세요."
      : "검색 결과가 없습니다. 철자나 띄어쓰기를 바꿔보세요.";
    setStatus(
      appState.candidates.length ? "low_confidence" : "error",
      appState.candidates.length ? "검색 후보를 하나 골라줘-로." : "이름 신호를 못 찾았다-로.",
      appState.candidates.length ? "CHECK" : "MISS",
    );
  } catch (error) {
    setStatus("error", "검색 회로가 끊겼다-로.", "ERROR");
    showToast(error.message);
  } finally {
    elements.searchButton.disabled = false;
  }
}

async function loadDetail(formId) {
  try {
    const response = await fetch(`/v1/pokedex/forms/${encodeURIComponent(formId)}`);
    if (!response.ok) {
      throw new Error(`detail failed: ${response.status}`);
    }
    appState.detail = await response.json();
    elements.datasetVersion.textContent = appState.detail.source_meta?.dataset_version || "unknown";
    renderDetail();
    if (appState.confirmed) {
      await loadNarration(appState.autoNarration);
    }
  } catch (error) {
    appState.detail = null;
    renderDetail();
    showToast(error.message);
  }
}

async function sendChat() {
  const message = elements.chatInput.value.trim();
  if (!message) {
    return;
  }
  appendSpeech(message, "user");
  elements.chatInput.value = "";
  const rotomBubble = appendSpeech("", "rotom");
  rotomBubble.classList.add("is-streaming");
  setStatus("scanning", "메모리 폴더 검색 중이다-로.", "THINK");
  elements.chatButton.disabled = true;

  try {
    await streamChat(message, rotomBubble);
  } catch (streamError) {
    try {
      await completeChat(message, rotomBubble);
    } catch (error) {
      rotomBubble.textContent = "응답 회로가 흔들렸다-로.";
      setStatus("error", "대화 실패다-로.", "ERROR");
      showToast(error.message);
    }
  } finally {
    rotomBubble.classList.remove("is-streaming");
    elements.chatButton.disabled = false;
  }
}

async function streamChat(message, bubble) {
  const response = await fetch("/v1/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      form_id: appState.detail?.form_id || appState.selected?.form_id || null,
      session_id: appState.sessionId,
    }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let doneEvent = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const result = consumeSseBuffer(buffer, bubble);
    buffer = result.buffer;
    doneEvent = doneEvent || result.doneEvent;
  }

  buffer += decoder.decode();
  const result = consumeSseBuffer(buffer, bubble, true);
  doneEvent = doneEvent || result.doneEvent;
  if (!doneEvent) {
    throw new Error("stream ended before done");
  }
}

async function completeChat(message, bubble) {
  const response = await fetch("/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      form_id: appState.detail?.form_id || appState.selected?.form_id || null,
      session_id: appState.sessionId,
    }),
  });
  if (!response.ok) {
    throw new Error(`chat failed: ${response.status}`);
  }
  const data = await response.json();
  if (data.session_id) {
    appState.sessionId = data.session_id;
    localStorage.setItem("poketdogam.sessionId", data.session_id);
  }
  bubble.textContent = data.answer;
  setLlmRuntime(data.llm_runtime || "template", data.llm_model || "template");
  renderSuggestions(data.suggested_actions || []);
  setStatus("idle", "답변 완료다-로.", "READY");
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
}

function consumeSseBuffer(buffer, bubble, flush = false) {
  const frames = buffer.split("\n\n");
  const pending = flush ? "" : frames.pop() || "";
  let doneEvent = false;
  frames.forEach((frame) => {
    const dataLine = frame
      .split("\n")
      .find((line) => line.startsWith("data:"));
    if (!dataLine) {
      return;
    }
    const event = JSON.parse(dataLine.slice(5).trim());
    doneEvent = applyChatStreamEvent(event, bubble) || doneEvent;
  });
  return { buffer: pending, doneEvent };
}

function applyChatStreamEvent(event, bubble) {
  if (event.session_id) {
    appState.sessionId = event.session_id;
    localStorage.setItem("poketdogam.sessionId", event.session_id);
  }
  if (event.event === "meta") {
    setLlmRuntime(event.runtime || "template", event.model || "template");
    setMood("think");
    return false;
  }
  if (event.event === "delta") {
    bubble.textContent += event.text || "";
    elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
    return false;
  }
  if (event.event === "replace") {
    bubble.textContent = event.text || "";
    elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
    return false;
  }
  if (event.event === "done") {
    if (event.answer) {
      bubble.textContent = event.answer;
    }
    setLlmRuntime(event.runtime || "template", event.model || "template");
    renderSuggestions(event.suggested_actions || []);
    setStatus("idle", "답변 완료다-로.", "READY");
    elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
    return true;
  }
  return false;
}

function renderSuggestions(actions) {
  if (!elements.suggestRow) {
    return;
  }
  elements.suggestRow.innerHTML = "";
  actions.forEach((action) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = action;
    button.addEventListener("click", () => {
      elements.chatInput.value = action;
      sendChat();
    });
    elements.suggestRow.appendChild(button);
  });
}

function setMood(expression) {
  if (elements.faceScreen) {
    elements.faceScreen.dataset.expression = expression;
  }
  if (elements.dexShell) {
    elements.dexShell.dataset.mood = expression;
  }
}

function renderCandidates() {
  if (!appState.candidates.length) {
    elements.candidateList.innerHTML = `<div class="empty-state">NO SIGNAL</div>`;
    return;
  }

  elements.candidateList.innerHTML = appState.candidates
    .map((candidate, index) => {
      const selected = appState.selected?.form_id === candidate.form_id ? " is-selected" : "";
      const types = (candidate.types || []).map(localizeType).join(" / ") || "미확인";
      const form = localizeForm(candidate.form_name || "base");
      const score = Math.round(Number(candidate.confidence || 0) * 100);
      const evidence = [];
      if (candidate.ocr_confidence !== null && candidate.ocr_confidence !== undefined) {
        evidence.push(`OCR ${Math.round(Number(candidate.ocr_confidence) * 100)}%`);
      }
      if (candidate.visual_confidence !== null && candidate.visual_confidence !== undefined) {
        evidence.push(`이미지 ${Math.round(Number(candidate.visual_confidence) * 100)}%`);
      }
      const evidenceLabel = evidence.join(" · ") || candidate.match_reason || "-";
      return `
        <button class="candidate-item${selected}" type="button" data-form-id="${candidate.form_id}">
          <span class="candidate-main">
            <span>
              <span class="candidate-name">${index + 1}. ${escapeHtml(candidate.name_ko)} · ${escapeHtml(form)}</span>
              <span class="candidate-meta">${escapeHtml(candidate.name_en || "")} · ${escapeHtml(types)}</span>
            </span>
            <span class="candidate-score">${score}%</span>
          </span>
          <span class="candidate-meta">${escapeHtml(evidenceLabel)} · Top-${index + 1}</span>
        </button>
      `;
    })
    .join("");

  elements.candidateList.querySelectorAll("[data-form-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      appState.selected = appState.candidates.find((candidate) => candidate.form_id === button.dataset.formId);
      appState.confirmed = Boolean(appState.selected);
      if (appState.selected) {
        confirmQualityEvent(appState.selected.form_id);
      }
      renderCandidates();
      if (appState.selected) {
        setStatus("locked", `${appState.selected.name_ko} 선택이다-로.`, "LOCK");
        await loadDetail(appState.selected.form_id);
      }
    });
  });
}

function renderDetail() {
  const detail = appState.detail;
  if (!detail) {
    elements.detailEmpty.hidden = false;
    elements.detailCard.hidden = true;
    elements.saveButton.disabled = true;
    elements.detailNarrationButton.disabled = true;
    return;
  }

  elements.detailEmpty.hidden = true;
  elements.detailCard.hidden = false;
  elements.detailNumber.textContent =
    Number(detail.pokemon_id) > 0
      ? `No.${String(detail.pokemon_id).padStart(4, "0")}`
      : "공식 발표 · 번호 미확정";
  elements.detailName.textContent = detail.name_ko;
  elements.detailEnglish.textContent = detail.name_en || "-";
  elements.typeBadges.innerHTML = (detail.types || [])
    .map((type) => `<span class="type-badge">${escapeHtml(localizeType(type))}</span>`)
    .join("");
  elements.detailHeight.textContent = detail.height_m ? `${detail.height_m} m` : "-";
  elements.detailWeight.textContent = detail.weight_kg ? `${detail.weight_kg} kg` : "-";
  elements.detailForm.textContent = localizeForm(detail.form_name || "base");
  elements.detailGeneration.textContent = detail.generation ? `${detail.generation}세대` : "-";
  elements.detailVersion.textContent = detail.source_meta?.dataset_version || "-";
  elements.detailSource.textContent = `출처: ${detail.source_meta?.source || "미확인"}`;
  elements.detailUpdated.textContent = `갱신: ${formatDate(detail.source_meta?.updated_at)}`;
  renderStats(detail.stats || {});
  renderTypeMatchups(detail);
  renderEvolutions(detail.evolutions || []);
  elements.saveButton.disabled = !appState.confirmed;
  elements.detailNarrationButton.disabled = !appState.confirmed;
  elements.saveButton.textContent = appState.confirmed ? "컬렉션 저장" : "후보 확정 필요";
  elements.saveHint.hidden = appState.confirmed;
}

function renderStats(stats) {
  const keys = ["hp", "attack", "defense", "sp_attack", "sp_defense", "speed", "bst"];
  elements.statBars.innerHTML = keys
    .filter((key) => stats[key] !== undefined)
    .map((key) => {
      const value = Number(stats[key]);
      const max = key === "bst" ? 780 : 180;
      const width = Math.min(100, Math.round((value / max) * 100));
      return `
        <div class="stat-row">
          <span>${statLabels[key]}</span>
          <span class="stat-track"><span class="stat-fill" style="width: ${width}%"></span></span>
          <strong>${value}</strong>
        </div>
      `;
    })
    .join("");
}

function renderTypeMatchups(detail) {
  const groups = [
    ["약점", detail.weaknesses || []],
    ["반감", detail.resistances || []],
    ["무효", detail.immunities || []],
  ];
  elements.typeMatchups.innerHTML = groups
    .map(([label, items]) => {
      const badges = items.length
        ? items
            .map(
              (item) =>
                `<span class="matchup-badge">${escapeHtml(localizeType(item.type))} ×${Number(item.multiplier).toFixed(
                  Number(item.multiplier) % 1 ? 2 : 0,
                )}</span>`,
            )
            .join("")
        : `<span class="muted">없음</span>`;
      return `<div class="matchup-row"><strong>${label}</strong><span>${badges}</span></div>`;
    })
    .join("");
}

function renderEvolutions(evolutions) {
  if (!evolutions.length) {
    elements.evolutionList.innerHTML = `<span class="muted">연결 정보 없음</span>`;
    return;
  }
  elements.evolutionList.innerHTML = evolutions
    .map((item) => {
      const trigger = formatEvolutionCondition(item);
      return `
        <div class="evolution-item">
          <strong>${escapeHtml(item.from_name)} → ${escapeHtml(item.to_name)}</strong>
          <span class="muted">${escapeHtml(trigger)}</span>
        </div>
      `;
    })
    .join("");
}

function renderCollection() {
  const filtered = appState.collection.filter((item) => {
    if (!appState.collectionQuery) {
      return true;
    }
    const searchText = `${item.name_ko} ${(item.types || []).join(" ")}`.toLowerCase();
    return searchText.includes(appState.collectionQuery);
  });
  elements.collectionCount.textContent = `${appState.collection.length}종`;
  renderQualitySummary();
  if (!filtered.length) {
    elements.collectionList.innerHTML = `<div class="empty-state">${
      appState.collection.length ? "검색 결과가 없습니다." : "아직 저장한 포켓몬이 없습니다."
    }</div>`;
    return;
  }

  elements.collectionList.innerHTML = filtered
    .map((item) => {
      const types = (item.types || []).map(localizeType).join(" / ");
      return `
        <div class="collection-item">
          <button class="collection-open" type="button" data-open-form="${item.form_id}">
          <span class="candidate-main">
            <span>
              <span class="candidate-name">No.${String(item.pokemon_id).padStart(4, "0")} ${escapeHtml(item.name_ko)}</span>
              <span class="candidate-meta">${escapeHtml(types)} · ${Number(item.discovered_count || 1)}회 발견</span>
            </span>
          </span>
          </button>
          <button class="favorite-button${item.favorite ? " is-favorite" : ""}" type="button" data-favorite-form="${
            item.form_id
          }" aria-label="${escapeHtml(item.name_ko)} 즐겨찾기">${item.favorite ? "★" : "☆"}</button>
        </div>
      `;
    })
    .join("");

  elements.collectionList.querySelectorAll("[data-open-form]").forEach((button) => {
    button.addEventListener("click", async () => {
      appState.selected = null;
      appState.confirmed = true;
      await loadDetail(button.dataset.openForm);
      document.querySelector("#detailPanel").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  elements.collectionList.querySelectorAll("[data-favorite-form]").forEach((button) => {
    button.addEventListener("click", () => {
      appState.collection = appState.collection.map((item) =>
        item.form_id === button.dataset.favoriteForm ? { ...item, favorite: !item.favorite } : item,
      );
      saveCollection(appState.collection);
      renderCollection();
    });
  });
}

function appendSpeech(text, speaker) {
  const bubble = document.createElement("div");
  bubble.className = `speech is-${speaker}`;
  bubble.textContent = text;
  elements.chatLog.appendChild(bubble);
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
  return bubble;
}

function setStatus(status, line, lensText) {
  elements.systemStatus.textContent = statusLabels[status] || status;
  elements.rotomLine.textContent = line;
  elements.lensState.textContent = lensText;
  elements.lens.classList.remove("is-scanning", "is-locked", "is-error");
  if (status === "scanning") {
    elements.lens.classList.add("is-scanning");
    setMood("think");
  } else if (status === "locked" || status === "low_confidence") {
    elements.lens.classList.add("is-locked");
    setMood(status === "locked" ? "lock" : "surprise");
  } else if (status === "error") {
    elements.lens.classList.add("is-error");
    setMood("error");
  } else {
    setMood("happy");
  }
}

function setLlmRuntime(runtime, model) {
  const runtimeLabel = runtime === "template" ? "근거 템플릿" : runtime === "ollama" ? "로컬 LLM" : "안전 폴백";
  const label = `${runtimeLabel}${model && model !== runtime && model !== "grounded_template" ? ` · ${model}` : ""}`;
  elements.llmRuntime.textContent = runtimeLabel;
  elements.llmBadge.textContent = label;
  elements.llmBadge.classList.toggle("is-live", runtime === "ollama");
  elements.llmBadge.classList.toggle("is-waiting", runtime !== "ollama");
}

async function loadVoiceStatus() {
  try {
    const response = await fetch("/v1/voice/status");
    if (!response.ok) {
      throw new Error(`voice status failed: ${response.status}`);
    }
    const data = await response.json();
    elements.voiceStatus.textContent = data.stage || "preview";
    elements.voiceMode.textContent = data.runtime || "browser";
    elements.voicePolicy.textContent = data.original_ai_voice_allowed ? "독자 합성" : "대기";
    elements.voiceStatus.classList.toggle("is-live", Boolean(data.original_ai_voice_allowed));
    elements.voiceStatus.classList.toggle("is-waiting", !data.original_ai_voice_allowed);
  } catch (error) {
    elements.voiceStatus.textContent = "offline";
    elements.voiceMode.textContent = "unavailable";
    elements.voiceStatus.classList.add("is-waiting");
  }
}

async function loadNarration(autoPlay = false) {
  if (!appState.detail || !appState.confirmed) {
    showToast("정확한 폼을 먼저 확정하세요.");
    return;
  }
  elements.detailNarrationButton.disabled = true;
  try {
    const response = await fetch("/v1/voice/narration", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ form_id: appState.detail.form_id }),
    });
    const data = await readJsonResponse(response);
    if (data.form_id !== appState.detail.form_id) {
      throw new Error("선택 폼과 낭독 데이터가 일치하지 않습니다.");
    }
    elements.voiceScript.value = data.narration_text;
    if (autoPlay) {
      await previewVoice();
    }
  } catch (error) {
    showToast(error.message);
  } finally {
    elements.detailNarrationButton.disabled = false;
  }
}

async function previewVoice() {
  const text = elements.voiceScript.value.trim();
  if (!text) {
    showToast("Preview Text를 입력하세요.");
    return;
  }
  elements.voicePreviewButton.disabled = true;
  elements.voiceStatus.textContent = "preparing";

  try {
    const response = await fetch("/v1/voice/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        style: appState.voiceStyle,
        pitch: Number(elements.voicePitch.value),
        speed: Number(elements.voiceSpeed.value),
      }),
    });
    if (!response.ok) {
      throw new Error(`voice preview failed: ${response.status}`);
    }
    const data = await response.json();
    playSpeechPreview(data);
  } catch (error) {
    elements.voiceStatus.textContent = "blocked";
    showToast(error.message);
  } finally {
    elements.voicePreviewButton.disabled = false;
  }
}

function playSpeechPreview(data) {
  if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
    elements.voiceStatus.textContent = "unsupported";
    showToast("이 브라우저는 음성 프리뷰를 지원하지 않습니다.");
    return;
  }

  window.speechSynthesis.cancel();
  playElectricPing("start");

  const utterance = new SpeechSynthesisUtterance(data.preview_text);
  utterance.lang = "ko-KR";
  utterance.pitch = Number(data.pitch) || 1.1;
  utterance.rate = Number(data.speed) || 1.0;
  utterance.volume = 0.92;
  const voice = pickKoreanVoice();
  if (voice) {
    utterance.voice = voice;
  }

  utterance.onstart = () => {
    elements.voiceStatus.textContent = "speaking";
    elements.voiceStatus.classList.add("is-live");
  };
  utterance.onend = () => {
    elements.voiceStatus.textContent = "preview";
    playElectricPing("end");
  };
  utterance.onerror = () => {
    elements.voiceStatus.textContent = "error";
  };

  window.speechSynthesis.speak(utterance);
}

function stopVoice() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  elements.voiceStatus.textContent = "preview";
  playElectricPing("end");
}

function pickKoreanVoice() {
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((voice) => voice.lang?.toLowerCase().startsWith("ko")) ||
    voices.find((voice) => voice.lang?.toLowerCase().startsWith("en")) ||
    null
  );
}

function playElectricPing(kind) {
  try {
    appState.audioContext = appState.audioContext || new AudioContext();
    const now = appState.audioContext.currentTime;
    const oscillator = appState.audioContext.createOscillator();
    const gain = appState.audioContext.createGain();
    oscillator.type = appState.voiceStyle === "machine_pulse" ? "square" : "triangle";
    oscillator.frequency.setValueAtTime(kind === "start" ? 740 : 520, now);
    oscillator.frequency.exponentialRampToValueAtTime(kind === "start" ? 1180 : 330, now + 0.08);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.08, now + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.12);
    oscillator.connect(gain);
    gain.connect(appState.audioContext.destination);
    oscillator.start(now);
    oscillator.stop(now + 0.13);
  } catch {
    // AudioContext can be blocked before user interaction; speech preview still works.
  }
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.classList.remove("is-visible");
  }, 2200);
}

function loadCollection() {
  try {
    const payload = JSON.parse(window.localStorage.getItem("poketdogam.collection") || "[]");
    const saved = Array.isArray(payload) ? payload : payload?.items;
    if (!Array.isArray(saved)) {
      return [];
    }
    return saved.map((item) => ({
      ...item,
      discovered_count: Number(item.discovered_count || 1),
      first_saved_at: item.first_saved_at || item.saved_at || null,
      last_saved_at: item.last_saved_at || item.saved_at || null,
      favorite: Boolean(item.favorite),
    }));
  } catch {
    return [];
  }
}

function saveCollection(collection) {
  window.localStorage.setItem(
    "poketdogam.collection",
    JSON.stringify({ schema_version: 2, saved_at: new Date().toISOString(), items: collection }),
  );
}

function loadQualityEvents() {
  try {
    const events = JSON.parse(window.localStorage.getItem("poketdogam.qualityEvents") || "[]");
    return Array.isArray(events) ? events : [];
  } catch {
    return [];
  }
}

function saveQualityEvents(events) {
  window.localStorage.setItem("poketdogam.qualityEvents", JSON.stringify(events.slice(0, 100)));
}

function recordQualityEvent(data, candidate, confirmationMethod, metricScope = "image_ocr") {
  const event = {
    event_id: data.event_id,
    trace_id: data.trace_id,
    recorded_at: new Date().toISOString(),
    ocr_engine: data.ocr_engine || "unknown",
    visual_engine: data.visual_engine || "unavailable",
    recognition_mode: data.recognition_mode || "ocr",
    match_score: candidate ? Number(candidate.confidence || 0) : null,
    dataset_version: data.dataset_version || "unknown",
    latency_ms: Number(data.latency_ms || 0),
    requires_user_confirmation: Boolean(data.requires_user_confirmation),
    confirmed: confirmationMethod === "auto",
    confirmation_method: confirmationMethod,
    metric_scope: metricScope,
    confirmed_form_id: confirmationMethod === "auto" ? candidate?.form_id || null : null,
  };
  appState.qualityEvents = [event, ...appState.qualityEvents.filter((item) => item.event_id !== event.event_id)].slice(
    0,
    100,
  );
  saveQualityEvents(appState.qualityEvents);
  renderQualitySummary();
}

function confirmQualityEvent(formId) {
  if (!appState.latestScanEventId) {
    return;
  }
  appState.qualityEvents = appState.qualityEvents.map((event) =>
    event.event_id === appState.latestScanEventId
      ? {
          ...event,
          confirmed: true,
          confirmation_method: "user",
          confirmed_form_id: formId,
        }
      : event,
  );
  saveQualityEvents(appState.qualityEvents);
  renderQualitySummary();
}

function renderQualitySummary() {
  const latest = appState.qualityEvents[0];
  if (!latest) {
    elements.qualitySummary.textContent = "품질 로그 대기 중";
    return;
  }
  const score = latest.match_score === null ? "MISS" : `${Math.round(latest.match_score * 100)}%`;
  const confirmation = latest.confirmed ? "확정" : "확인 대기";
  const scope =
    latest.metric_scope === "matcher_only"
      ? "텍스트 매처"
      : latest.metric_scope === "ocr+visual_embedding"
        ? "OCR+이미지"
        : latest.metric_scope === "visual_embedding"
          ? "이미지"
          : "이미지 OCR";
  elements.qualitySummary.textContent = `최근 ${scope} ${score} · ${Math.round(
    latest.latency_ms,
  )}ms · ${confirmation} · ${latest.dataset_version}`;
}

function localizeType(type) {
  return typeLabels[type] || type || "미확인";
}

function localizeForm(formName) {
  const parts = String(formName || "base").split("-");
  return parts.map((part) => formLabels[part] || part).join(" ");
}

function formatEvolutionCondition(item) {
  const condition = item.condition || {};
  const bits = [];
  if (condition.min_level) bits.push(`레벨 ${condition.min_level}`);
  if (condition.item) bits.push(`${condition.item} 사용`);
  if (condition.held_item) bits.push(`${condition.held_item} 소지`);
  if (condition.min_happiness) bits.push(`친밀도 ${condition.min_happiness}+`);
  if (condition.known_move) bits.push(`${condition.known_move} 습득`);
  if (condition.time_of_day) bits.push(condition.time_of_day === "day" ? "낮" : condition.time_of_day === "night" ? "밤" : condition.time_of_day);
  if (condition.location) bits.push(condition.location);
  if (condition.region) bits.push(`${condition.region} 지역`);
  return bits.join(" · ") || item.trigger_value || item.trigger_type || "조건 미확정";
}

function formatBytes(bytes) {
  return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)}KB` : `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

function formatDate(value) {
  if (!value) return "미확인";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("ko-KR").format(date);
}

async function readJsonResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `요청 실패 (${response.status})`);
  }
  return payload;
}

function exportLocalData() {
  const payload = {
    exported_at: new Date().toISOString(),
    collection: appState.collection,
    quality_events: appState.qualityEvents,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `poketdogam-local-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
  showToast("로컬 데이터를 JSON으로 내보냈습니다.");
}

async function clearLocalData() {
  if (!window.confirm("컬렉션, 품질 로그, 현재 대화를 이 기기에서 모두 삭제할까요?")) {
    return;
  }
  if (appState.sessionId) {
    await fetch(`/v1/sessions/${encodeURIComponent(appState.sessionId)}`, { method: "DELETE" }).catch(() => null);
  }
  ["poketdogam.collection", "poketdogam.qualityEvents", "poketdogam.sessionId"].forEach((key) =>
    localStorage.removeItem(key),
  );
  appState.collection = [];
  appState.qualityEvents = [];
  appState.sessionId = null;
  renderCollection();
  showToast("이 기기의 포켓도감 데이터를 삭제했습니다.");
}

async function loadHealth() {
  try {
    const health = await readJsonResponse(await fetch("/health"));
    elements.datasetVersion.textContent = health.dataset_version || "미확인";
  } catch {
    elements.datasetVersion.textContent = "연결 확인 필요";
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

renderCandidates();
renderDetail();
renderCollection();
loadVoiceStatus();
loadHealth();
