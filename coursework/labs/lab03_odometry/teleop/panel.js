"use strict";

const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="teleop-token"]').content;
const headers = { "X-Teleop-Token": token };
const directionKeys = new Set(["KeyW", "KeyA", "KeyS", "KeyD"]);
const keys = new Set();
const format = new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
let lease = null;
let sequence = 0;
let sending = false;
let arming = false;
let ready = false;
let anotherSession = false;
let expandedButton = null;

function value(number, unit) {
  return Number.isFinite(number) ? `${format.format(number)} ${unit}` : "—";
}

function post(operation, data = {}) {
  return fetch(`/api/${operation}`, {
    method: "POST", headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(data), keepalive: operation === "stop",
  }).then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  });
}

function refreshKeys() {
  document.querySelectorAll("[data-key]").forEach((key) => {
    key.classList.toggle("down", keys.has(key.dataset.key));
  });
}

function renderArm() {
  $("arm").textContent = lease ? "Выключить управление" : "Включить управление";
  $("arm").disabled = arming || isExpandedTelemetry() || (!lease && (!ready || anotherSession));
  $("mode").dataset.armed = Boolean(lease);
  $("mode").textContent = lease ? "Управление включено" : anotherSession
    ? "Управление открыто в другой вкладке" : ready
      ? "Управление выключено" : "Ожидаю камеру и одометрию";
}

function stop() {
  const current = lease;
  lease = null;
  keys.clear();
  refreshKeys();
  renderArm();
  if (current) return post("stop", { lease: current }).catch(() => {});
  return Promise.resolve();
}

async function drive() {
  if (!lease || sending) return;
  if (document.hidden || !document.hasFocus() || isExpandedTelemetry()) {
    stop();
    return;
  }
  const current = lease;
  const linear = (Number(keys.has("KeyW")) - Number(keys.has("KeyS"))) * Number($("linear").value);
  const angular = (Number(keys.has("KeyA")) - Number(keys.has("KeyD"))) * Number($("angular").value);
  sending = true;
  try {
    const response = await post("drive", { lease: current, sequence: ++sequence, linear, angular });
    if (lease === current && !response.ok) stop();
  } catch {
    if (lease === current) stop();
  } finally {
    sending = false;
  }
}

$("arm").addEventListener("click", async () => {
  if (lease) {
    stop();
    return;
  }
  arming = true;
  renderArm();
  try {
    const response = await post("arm");
    if (response.ok) {
      lease = response.lease;
      sequence = 0;
      drive();
    }
  } catch {
    ready = false;
  } finally {
    arming = false;
    renderArm();
  }
});

$("stop").addEventListener("click", stop);

window.addEventListener("keydown", (event) => {
  if (!lease) return;
  if (event.code === "Space" || event.code === "Escape") {
    event.preventDefault();
    stop();
  } else if (directionKeys.has(event.code) && !event.altKey && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    if (event.repeat) return;
    keys.add(event.code);
    refreshKeys();
    drive();
  }
});

window.addEventListener("keyup", (event) => {
  if (!keys.delete(event.code)) return;
  refreshKeys();
  drive();
});
window.addEventListener("blur", stop);
window.addEventListener("pagehide", stop);
document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });

for (const [id, unit] of [["linear", "м/с"], ["angular", "рад/с"]]) {
  $(id).addEventListener("input", () => {
    $(`${id}-out`).value = value(Number($(id).value), unit);
  });
}

const tabs = [...document.querySelectorAll('[role="tab"]')];
const plot = $("trajectory");
const scanPlot = $("scan");
const sources = {
  wheel: { field: "odom", pose: null, trail: [] },
  lidar: { field: "lidar_odom", pose: null, trail: [] },
  fusion: { field: "ekf_odom", pose: null, trail: [] },
};
let sampleId = 0;
let alignment = null;
let runStart = null;
let marking = false;
let markError = false;
let activeOdom = "wheel";
let scan = null;

const page = document.documentElement;
const theme = $("theme");
const fullscreenButtons = [...document.querySelectorAll("[data-fullscreen]")];
let plotColors;

function isExpandedTelemetry() {
  return expandedButton !== null && expandedButton.dataset.fullscreen !== "page";
}

function setExpanded(button) {
  document.querySelector(".expanded-view")?.classList.remove("expanded-view");
  expandedButton = button;
  if (button && button.dataset.fullscreen !== "page") {
    $(button.dataset.fullscreen).classList.add("expanded-view");
  }
  for (const control of fullscreenButtons) {
    const expanded = control === button;
    const label = `${expanded ? "Свернуть" : "Развернуть"} ${control.dataset.label}`;
    control.setAttribute("aria-label", label);
    control.title = label;
    control.querySelector("use").setAttribute("href", expanded ? "#icon-collapse" : "#icon-expand");
  }
}

function closeExpanded() {
  const control = expandedButton;
  setExpanded(null);
  stop();
  control?.focus({ preventScroll: true });
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
}

for (const button of fullscreenButtons) {
  button.addEventListener("click", () => {
    if (button === expandedButton) {
      closeExpanded();
      return;
    }
    setExpanded(button);
    stop();
    if (!document.fullscreenElement) page.requestFullscreen?.().catch(() => {});
  });
}
document.addEventListener("fullscreenchange", () => {
  if (!document.fullscreenElement && expandedButton) closeExpanded();
});
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && expandedButton && !document.fullscreenElement) closeExpanded();
});

function setTheme(next) {
  page.dataset.theme = next;
  const label = next === "light" ? "Светлая тема. Включить тёмную" : "Тёмная тема. Включить светлую";
  theme.setAttribute("aria-label", label);
  theme.title = label;
  const style = getComputedStyle(page);
  plotColors = ["--muted", "--line", "--control-line", "--accent", "--trajectory-lidar",
                "--trajectory-fusion"].map((name) => style.getPropertyValue(name).trim());
  renderTrajectory();
  renderScan();
}

theme.addEventListener("click", () => {
  const next = page.dataset.theme === "light" ? "dark" : "light";
  setTheme(next);
  localStorage.setItem("jetbot-theme", next);
});
setTheme(page.dataset.theme || "dark");

function canvasView(canvas) {
  const { width, height } = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const pixelsWide = Math.round(width * dpr);
  const pixelsHigh = Math.round(height * dpr);
  if (canvas.width !== pixelsWide) canvas.width = pixelsWide;
  if (canvas.height !== pixelsHigh) canvas.height = pixelsHigh;
  const context = canvas.getContext("2d");
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, width, height);
  return { context, width, height };
}

function relativePose(pose, origin) {
  const dx = pose[0] - origin[0];
  const dy = pose[1] - origin[1];
  const c = Math.cos(origin[2]);
  const s = Math.sin(origin[2]);
  const yaw = pose[2] - origin[2];
  return [c * dx + s * dy, -s * dx + c * dy, Math.atan2(Math.sin(yaw), Math.cos(yaw)),
          pose[3], pose[4]];
}

function displayedPose(id) {
  const pose = sources[id].pose;
  if (!pose || (!runStart && activeOdom !== "fusion")) return pose;
  const origin = alignment?.origins[id];
  return origin ? relativePose(pose, origin) : null;
}

function displayedSeries() {
  const ids = activeOdom === "fusion" ? Object.keys(sources) : [activeOdom];
  return ids.flatMap((id) => {
    const pose = displayedPose(id);
    if (!pose) return [];
    const { trail } = sources[id];
    const origin = (runStart || activeOdom === "fusion") && alignment?.origins[id];
    const points = origin
      ? trail.filter((entry) => entry.id >= alignment.id).map((entry) => relativePose(entry.pose, origin))
      : trail.map((entry) => entry.pose);
    return [{ id, trail: points, pose }];
  });
}

function renderTrajectory() {
  if (activeOdom === "slam") return;
  const { context, width, height } = canvasView(plot);
  const series = displayedSeries();
  if (!series.length) return;

  const points = [[0, 0], ...series.flatMap(({ trail, pose }) => [...trail, pose])];
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  const bounds = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const cx = (bounds[0] + bounds[1]) / 2;
  const cy = (bounds[2] + bounds[3]) / 2;
  const scale = Math.min((width - 70) / Math.max(1.2, bounds[1] - bounds[0]),
                         (height - 66) / Math.max(1.2, bounds[3] - bounds[2]));
  if (scale <= 0) return;
  const projectX = (x) => width / 2 + (x - cx) * scale;
  const projectY = (y) => height / 2 - (y - cy) * scale;
  const target = 46 / scale;
  const magnitude = 10 ** Math.floor(Math.log10(target));
  const step = [1, 2, 5, 10].map((n) => n * magnitude).find((n) => n >= target);
  const minX = cx - width / (2 * scale);
  const minY = cy - height / (2 * scale);

  const [text, grid, axes, wheel, lidar, fusion] = plotColors;
  context.font = "11px Inter, system-ui, sans-serif";
  context.lineWidth = 1;
  context.fillStyle = text;
  for (let i = Math.ceil(minX / step); i * step < cx + width / (2 * scale); i++) {
    const pixel = projectX(i * step);
    context.strokeStyle = i === 0 ? axes : grid;
    context.beginPath(); context.moveTo(pixel, 0); context.lineTo(pixel, height); context.stroke();
    if (pixel > 27 && pixel < width - 72) context.fillText(format.format(i * step), pixel + 3, height - 12);
  }
  for (let i = Math.ceil(minY / step); i * step < cy + height / (2 * scale); i++) {
    const pixel = projectY(i * step);
    context.strokeStyle = i === 0 ? axes : grid;
    context.beginPath(); context.moveTo(0, pixel); context.lineTo(width, pixel); context.stroke();
    if (pixel > 20 && pixel < height - 24) context.fillText(format.format(i * step), 8, pixel - 5);
  }
  context.fillText("Y, м", 8, 16);
  context.fillText("X, м", width - 38, height - 12);

  const colors = { wheel, lidar, fusion };
  context.lineJoin = "round";
  for (const { id, trail, pose } of series) {
    context.save();
    context.strokeStyle = colors[id];
    context.lineWidth = id === "fusion" ? 3 : 2;
    context.setLineDash(activeOdom === "fusion" && id === "lidar" ? [6, 4] : []);
    context.beginPath();
    [...trail, pose].forEach(([x, y], index) => {
      if (index === 0) context.moveTo(projectX(x), projectY(y));
      else context.lineTo(projectX(x), projectY(y));
    });
    context.stroke();
    context.translate(projectX(pose[0]), projectY(pose[1]));
    context.rotate(-pose[2]);
    context.fillStyle = colors[id];
    context.beginPath();
    context.moveTo(12, 0); context.lineTo(-7, 6); context.lineTo(-4, 0); context.lineTo(-7, -6);
    context.closePath(); context.fill();
    context.restore();
  }
}

function renderScan() {
  if (activeOdom !== "lidar") return;
  const { context, width, height } = canvasView(scanPlot);
  $("scan-empty").hidden = Boolean(scan);
  if (!scan) {
    $("scan-info").textContent = "Нет свежего скана";
    return;
  }
  const radius = Number($("scan-radius").value);
  const pixels = Math.min(width - 40, height - 28) / 2;
  if (pixels <= 0) return;
  const scale = pixels / radius;
  const x = width / 2;
  const y = height / 2;
  const [text, grid, axes, points] = plotColors;
  context.font = "11px Inter, system-ui, sans-serif";
  context.strokeStyle = grid;
  context.fillStyle = text;
  for (const ring of [0.5, 1]) {
    context.beginPath();
    context.arc(x, y, pixels * ring, 0, 2 * Math.PI);
    context.stroke();
    context.fillText(`${radius * ring} м`, x + pixels * ring + 4, y - 5);
  }
  context.strokeStyle = axes;
  context.beginPath();
  context.moveTo(x - pixels, y); context.lineTo(x + pixels, y);
  context.moveTo(x, y - pixels); context.lineTo(x, y + pixels);
  context.stroke();
  context.fillText("+X", x + 6, y - pixels + 9);
  context.fillText("+Y", x - pixels - 18, y - 5);
  context.fillRect(x - 2, y - 2, 4, 4);

  let visible = 0;
  context.fillStyle = points;
  for (const [index, distance] of scan.ranges.entries()) {
    if (distance === null || distance > radius) continue;
    const angle = scan.angle_min + index * scan.angle_increment;
    const u = x - Math.sin(angle) * distance * scale;
    const v = y - Math.cos(angle) * distance * scale;
    context.fillRect(u - 1.15, v - 1.15, 2.3, 2.3);
    visible++;
  }
  $("scan-info").textContent = `${scan.frame} · ${visible} точек`;
}

function renderOdom() {
  if (activeOdom === "slam") return;
  const comparing = activeOdom === "fusion";
  const shown = displayedPose(activeOdom);
  const [x, y, yaw, speed, turn] = shown || [];
  $("x").textContent = value(x, "м");
  $("y").textContent = value(y, "м");
  $("yaw").textContent = value(yaw * 180 / Math.PI, "°");
  $("speed").textContent = value(speed, "м/с");
  $("turn").textContent = value(turn, "рад/с");
  const hasPlot = comparing ? Object.keys(sources).some(displayedPose) : shown;
  $("plot-empty").hidden = Boolean(hasPlot);
  if (!hasPlot) {
    $("plot-empty").textContent = {
      wheel: "Ожидаю колёсную одометрию…",
      lidar: "Ожидаю одометрию RF2O…",
      fusion: "Ожидаю данные трёх одометрий…",
    }[activeOdom];
  }
  if (comparing) {
    for (const id of Object.keys(sources)) {
      const pose = displayedPose(id);
      $("distance-" + id).textContent = pose ? value(100 * Math.hypot(pose[0], pose[1]), "см") : "—";
    }
  }
  const pending = runStart && !runStart.reference;
  const title = comparing ? "Траектории от общего старта" : "Траектория RF2O";
  $("trajectory-title").textContent = pending ? title + " · Старт подготовлен" : title;
  $("start-state").hidden = !pending && !markError;
  $("start-state").textContent = markError ? "Для отметки старта остановите робота"
    : "Старт подготовлен. Ноль фиксируется при начале движения.";
  $("clear").disabled = marking || Boolean(lease) || anotherSession || !ready;
  renderTrajectory();
  renderScan();
}

function selectTab(tab) {
  activeOdom = tab.id;
  const mapping = activeOdom === "slam";
  $("odom-panel").hidden = mapping;
  $("slam-panel").hidden = !mapping;
  $("clear").hidden = mapping;
  $("odom-title").textContent = mapping ? "Картирование" : "Одометрия";
  $("panel-context").textContent = mapping ? "ЛР 4 · SLAM" : "ЛР 3 · Одометрия";
  if (mapping) $("start-state").hidden = true;
  $("scan-view").hidden = activeOdom !== "lidar";
  $("trajectory-header").hidden = activeOdom === "wheel";
  $("compare-legend").hidden = activeOdom !== "fusion";
  tabs.forEach((entry) => {
    const selected = entry === tab;
    entry.setAttribute("aria-selected", selected);
    entry.tabIndex = selected ? 0 : -1;
  });
  if (!mapping) $("odom-panel").setAttribute("aria-labelledby", tab.id);
  renderOdom();
}
tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => selectTab(tab));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    const offset = event.key === "ArrowLeft" ? -1 : 1;
    const next = tabs[(index + offset + tabs.length) % tabs.length];
    selectTab(next);
    next.focus();
  });
});
selectTab(tabs[0]);
new ResizeObserver(renderTrajectory).observe(plot);
new ResizeObserver(renderScan).observe(scanPlot);
$("scan-radius").addEventListener("change", renderScan);
$("clear").addEventListener("click", async () => {
  marking = true;
  markError = false;
  renderOdom();
  try {
    const response = await post("mark-start");
    markError = !response.ok;
  } catch {
    markError = true;
  } finally {
    marking = false;
    renderOdom();
  }
});

function renderStatus(status, observedLease = lease) {
  ready = status.ready;
  if (!status.armed && lease && lease === observedLease && !arming) stop();
  anotherSession = status.armed && !lease;
  $("connection").dataset.live = status.ros;
  $("connection").textContent = status.ros ? "JetBot подключён" : "Нет связи с ROS";
  $("live").dataset.live = status.camera;
  $("live").textContent = status.camera ? "Прямой эфир" : "Ожидаю кадр";
  $("camera").parentElement.dataset.live = status.camera;
  $("camera-empty").textContent = status.error || "Подключаю камеру…";
  scan = status.scan || null;
  sampleId++;
  if (status.ros) {
    const next = status.start || null;
    if (next?.id !== runStart?.id || next?.reference?.utc !== runStart?.reference?.utc) {
      alignment = null;
      markError = false;
      for (const { trail } of Object.values(sources)) trail.length = 0;
    }
    runStart = next;
  }
  for (const source of Object.values(sources)) {
    source.pose = status[source.field] || null;
    const { pose, trail } = source;
    if (!pose) continue;
    if (runStart && !runStart.reference) continue;
    const last = trail.at(-1)?.pose;
    if (!last || Math.hypot(pose[0] - last[0], pose[1] - last[1]) > 0.003) {
      if (trail.length >= 2000) trail.shift();
      trail.push({ id: sampleId, pose });
    }
  }
  if (runStart?.reference && !alignment) {
    alignment = {
      id: sampleId,
      origins: Object.fromEntries(Object.entries(sources)
        .map(([id, source]) => [id, runStart.reference.origins[source.field]])),
    };
    for (const [id, source] of Object.entries(sources)) {
      if (alignment.origins[id]) source.trail.unshift({ id: sampleId, pose: alignment.origins[id] });
    }
  } else if (runStart && !runStart.reference) {
    alignment = {
      id: sampleId,
      origins: Object.fromEntries(Object.entries(sources).map(([id, source]) => [id, source.pose])),
    };
  } else if (!alignment && Object.values(sources).every((source) => source.pose)) {
    alignment = {
      id: sampleId,
      origins: Object.fromEntries(Object.entries(sources).map(([id, source]) => [id, source.pose])),
    };
    for (const { trail, pose } of Object.values(sources)) {
      if (trail.at(-1)?.id === sampleId) continue;
      if (trail.length >= 2000) trail.shift();
      trail.push({ id: sampleId, pose });
    }
  }
  renderOdom();
  $("current-command").textContent = `${value(status.command[0], "м/с")} · ${value(status.command[1], "рад/с")}`;
  renderArm();
}

async function pollStatus() {
  const observedLease = lease;
  try {
    const response = await fetch("/api/status", { headers, signal: AbortSignal.timeout(900) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderStatus(await response.json(), observedLease);
  } catch {
    stop();
    renderStatus({ command: [0, 0], error: "Пульт отключён" });
  } finally {
    setTimeout(pollStatus, 200);
  }
}

setInterval(drive, 55);
pollStatus();
