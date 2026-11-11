const form = document.querySelector("#download-form");
const input = document.querySelector("#post-url");
const submitButton = document.querySelector("#submit-button");
const saveButton = document.querySelector("#save-button");
const mp3Button = document.querySelector("#mp3-button");
const qualitySelect = document.querySelector("#quality-select");
const feedback = document.querySelector("#feedback");
const resultCard = document.querySelector("#result-card");
const apiPrefix = form.dataset.apiPrefix;
let activeUrl = "";

function setBusy(button, busy, label) {
  button.disabled = busy;
  const text = button.querySelector("span");
  if (text) {
    if (busy) {
      button.dataset.label = text.textContent;
      text.textContent = label;
    } else {
      text.textContent = button.dataset.label || text.textContent;
    }
  }
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) return "";
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.floor(seconds % 60);
  return `${minutes}:${String(remaining).padStart(2, "0")}`;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  feedback.textContent = "";
  feedback.className = "feedback loading";
  feedback.textContent = "Gönderi kontrol ediliyor…";
  resultCard.hidden = true;
  activeUrl = input.value.trim();
  setBusy(submitButton, true, "Kontrol ediliyor");

  try {
    const response = await fetch(`${apiPrefix}/video`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: activeUrl }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Gönderi alınamadı.");

    document.querySelector("#video-title").textContent = data.title;
    document.querySelector("#video-uploader").textContent = data.uploader;
    document.querySelector("#duration").textContent = formatDuration(data.duration);
    qualitySelect.replaceChildren(
      ...(data.qualities || [{ value: "best", label: "En yüksek kalite" }]).map((quality) => {
        const option = document.createElement("option");
        option.value = quality.value;
        option.textContent = quality.label;
        return option;
      }),
    );
    const thumbnail = document.querySelector("#thumbnail");
    if (data.thumbnail) thumbnail.src = data.thumbnail;
    else thumbnail.removeAttribute("src");
    resultCard.hidden = false;
    feedback.textContent = "";
    feedback.className = "feedback";
  } catch (error) {
    feedback.className = "feedback";
    feedback.textContent = error.message || "Bir hata oluştu. Lütfen yeniden deneyin.";
  } finally {
    setBusy(submitButton, false);
  }
});

async function downloadMedia({ audioOnly = false } = {}) {
  feedback.className = "feedback loading";
  feedback.textContent = audioOnly ? "MP3 hazırlanıyor…" : "Video hazırlanıyor…";
  setBusy(saveButton, true, "İndiriliyor");
  setBusy(mp3Button, true, "…");

  try {
    const response = await fetch(`${apiPrefix}/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: activeUrl,
        quality: qualitySelect.value,
        audio_only: audioOnly,
      }),
    });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || "Video indirilemedi.");
    }

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = `${apiPrefix.includes("youtube") ? "yt" : "x"}-${audioOnly ? "audio.mp3" : "video"}`;
    if (!audioOnly) {
      const disposition = response.headers.get("Content-Disposition");
      const filename = disposition?.match(/filename="?([^";]+)"?/i)?.[1];
      if (filename) anchor.download = filename;
    }
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    feedback.className = "feedback";
    feedback.textContent = audioOnly ? "MP3 indirmesi başladı." : "İndirme başladı.";
  } catch (error) {
    feedback.className = "feedback";
    feedback.textContent = error.message || "Bir hata oluştu. Lütfen yeniden deneyin.";
  } finally {
    setBusy(saveButton, false);
    setBusy(mp3Button, false);
  }
}

saveButton.addEventListener("click", () => downloadMedia());
mp3Button.addEventListener("click", () => downloadMedia({ audioOnly: true }));
