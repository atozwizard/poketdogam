const elements = {
  rotomLine: document.querySelector("#rotomLine"),
  datasetVersion: document.querySelector("#datasetVersion"),
  systemStatus: document.querySelector("#systemStatus"),
  llmRuntime: document.querySelector("#llmRuntime"),
  lens: document.querySelector("#lens"),
  lensState: document.querySelector("#lensState"),
  lensScore: document.querySelector("#lensScore"),
  ocrText: document.querySelector("#ocrText"),
  scanButton: document.querySelector("#scanButton"),
  clearButton: document.querySelector("#clearButton"),
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
  detailVersion: document.querySelector("#detailVersion"),
  statBars: document.querySelector("#statBars"),
  saveButton: document.querySelector("#saveButton"),
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
  collectionList: document.querySelector("#collectionList"),
  toast: document.querySelector("#toast"),
};

const appState = {
  candidates: [],
  selected: null,
  detail: null,
  collection: loadCollection(),
  voiceStyle: "electric_device",
  audioContext: null,
  sessionId: localStorage.getItem("poketdogam.sessionId") || null,
};

const statLabels = {
  hp: "HP",
  attack: "Attack",
  defense: "Defense",
  sp_attack: "Sp. Atk",
  sp_defense: "Sp. Def",
  speed: "Speed",
  bst: "BST",
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
elements.clearButton.addEventListener("click", () => {
  appState.candidates = [];
  appState.selected = null;
  appState.detail = null;
  elements.ocrText.value = "";
  renderCandidates();
  renderDetail();
  setStatus("idle", "렌즈 대기 중이다-로.", "READY");
});

elements.saveButton.addEventListener("click", () => {
  if (!appState.detail) {
    showToast("저장할 도감 데이터가 없습니다.");
    return;
  }
  const next = appState.collection.filter((item) => item.form_id !== appState.detail.form_id);
  next.unshift({
    form_id: appState.detail.form_id,
    pokemon_id: appState.detail.pokemon_id,
    name_ko: appState.detail.name_ko,
    types: appState.detail.types,
    saved_at: new Date().toISOString(),
  });
  appState.collection = next.slice(0, 12);
  saveCollection(appState.collection);
  renderCollection();
  showToast(`${appState.detail.name_ko} 저장 완료`);
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

async function loadDetail(formId) {
  try {
    const response = await fetch(`/v1/pokedex/forms/${encodeURIComponent(formId)}`);
    if (!response.ok) {
      throw new Error(`detail failed: ${response.status}`);
    }
    appState.detail = await response.json();
    elements.datasetVersion.textContent = appState.detail.source_meta?.dataset_version || "unknown";
    renderDetail();
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
      form_id: appState.selected?.form_id || null,
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
      form_id: appState.selected?.form_id || null,
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
      const types = (candidate.types || []).join(" / ") || "unknown";
      const score = Math.round(Number(candidate.confidence || 0) * 100);
      return `
        <button class="candidate-item${selected}" type="button" data-form-id="${candidate.form_id}">
          <span class="candidate-main">
            <span>
              <span class="candidate-name">${index + 1}. ${escapeHtml(candidate.name_ko)}</span>
              <span class="candidate-meta">${escapeHtml(candidate.name_en || "")} · ${escapeHtml(types)}</span>
            </span>
            <span class="candidate-score">${score}%</span>
          </span>
          <span class="candidate-meta">alias ${escapeHtml(candidate.matched_alias || "-")} · ${escapeHtml(candidate.match_reason || "-")}</span>
        </button>
      `;
    })
    .join("");

  elements.candidateList.querySelectorAll("[data-form-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      appState.selected = appState.candidates.find((candidate) => candidate.form_id === button.dataset.formId);
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
    return;
  }

  elements.detailEmpty.hidden = true;
  elements.detailCard.hidden = false;
  elements.detailNumber.textContent = `No.${String(detail.pokemon_id).padStart(4, "0")}`;
  elements.detailName.textContent = detail.name_ko;
  elements.detailEnglish.textContent = detail.name_en || "-";
  elements.typeBadges.innerHTML = (detail.types || []).map((type) => `<span class="type-badge">${escapeHtml(type)}</span>`).join("");
  elements.detailHeight.textContent = detail.height_m ? `${detail.height_m} m` : "-";
  elements.detailWeight.textContent = detail.weight_kg ? `${detail.weight_kg} kg` : "-";
  elements.detailForm.textContent = detail.form_name || "base";
  elements.detailVersion.textContent = detail.source_meta?.dataset_version || "-";
  renderStats(detail.stats || {});
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

function renderCollection() {
  if (!appState.collection.length) {
    elements.collectionList.innerHTML = `<div class="empty-state">EMPTY BOX</div>`;
    return;
  }

  elements.collectionList.innerHTML = appState.collection
    .map((item) => {
      const types = (item.types || []).join(" / ");
      return `
        <button class="collection-item" type="button" data-form-id="${item.form_id}">
          <span class="candidate-main">
            <span>
              <span class="candidate-name">No.${String(item.pokemon_id).padStart(4, "0")} ${escapeHtml(item.name_ko)}</span>
              <span class="candidate-meta">${escapeHtml(types)}</span>
            </span>
          </span>
        </button>
      `;
    })
    .join("");

  elements.collectionList.querySelectorAll("[data-form-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await loadDetail(button.dataset.formId);
      document.querySelector("#detailPanel").scrollIntoView({ behavior: "smooth", block: "start" });
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
  elements.systemStatus.textContent = status;
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
  const label = `${runtime}${model && model !== runtime ? ` · ${model}` : ""}`;
  elements.llmRuntime.textContent = runtime;
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
    return JSON.parse(window.localStorage.getItem("poketdogam.collection") || "[]");
  } catch {
    return [];
  }
}

function saveCollection(collection) {
  window.localStorage.setItem("poketdogam.collection", JSON.stringify(collection));
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
scanText();
