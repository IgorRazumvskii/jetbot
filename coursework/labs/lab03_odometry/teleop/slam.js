"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const panel = byId("slam-panel");
  const canvas = byId("slam-map");
  const raster = document.createElement("canvas");
  const graphToggle = byId("slam-graph");
  const headers = { "X-Teleop-Token": document.querySelector('meta[name="teleop-token"]')?.content || "" };
  const format = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });
  const plural = new Intl.PluralRules("ru-RU");
  const keyframes = { one: "ключевой кадр", few: "ключевых кадра", many: "ключевых кадров" };
  let map = null;
  let graph = null;
  let pose = null;
  let connected = true;

  function colors() {
    const style = getComputedStyle(document.documentElement);
    return Object.fromEntries(["occupied", "free", "graph", "pose"].map((key) => [
      key, style.getPropertyValue("--map-" + key).trim(),
    ]));
  }

  function updateRaster() {
    if (!map) return;
    const { width, height, cells } = map;
    const data = atob(cells);
    if (data.length !== width * height) throw new Error("Invalid occupancy grid");
    raster.width = width;
    raster.height = height;
    const context = raster.getContext("2d");
    const image = context.createImageData(width, height);
    const palette = colors();
    const rgb = (hex) => hex.slice(1).match(/../g).map((part) => parseInt(part, 16));
    const free = rgb(palette.free);
    const occupied = rgb(palette.occupied);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const cell = data.charCodeAt(y * width + x);
        if (cell > 100) continue;
        const offset = ((height - y - 1) * width + x) * 4;
        for (let channel = 0; channel < 3; channel++) {
          image.data[offset + channel] = free[channel] + (occupied[channel] - free[channel]) * cell / 100;
        }
        image.data[offset + 3] = 255;
      }
    }
    context.putImageData(image, 0, 0);
  }

  function draw() {
    if (panel.hidden) return;
    const { width, height } = canvas.getBoundingClientRect();
    if (width < 60 || height < 75) return;
    const pixelRatio = window.devicePixelRatio || 1;
    const pixelWidth = Math.round(width * pixelRatio);
    const pixelHeight = Math.round(height * pixelRatio);
    if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
    if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    byId("slam-empty").hidden = Boolean(map);
    byId("slam-empty").textContent = connected ? "Ожидаю карту SLAM…" : "Связь с потоком SLAM прервана";
    byId("slam-pose-status").textContent = map && !pose ? "Поза недоступна" : "";
    if (!map) return;

    const size = Math.min((width - 36) / map.width, (height - 51) / map.height);
    const left = (width - size * map.width) / 2;
    const top = (height - 22 - size * map.height) / 2;
    const [x0, y0, angle] = map.origin;
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    const meters = size / map.resolution;
    const project = (x, y) => {
      const dx = x - x0;
      const dy = y - y0;
      return [
        left + (c * dx + s * dy) * meters,
        top + size * map.height - (-s * dx + c * dy) * meters,
      ];
    };
    const palette = colors();
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(raster, left, top, size * map.width, size * map.height);
    if (graph && graphToggle.checked) {
      ctx.strokeStyle = palette.graph;
      ctx.fillStyle = palette.graph;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let index = 0; index + 1 < graph.edges.length; index += 2) {
        ctx.moveTo(...project(...graph.edges[index]));
        ctx.lineTo(...project(...graph.edges[index + 1]));
      }
      ctx.stroke();
      for (const point of graph.nodes) {
        const [x, y] = project(...point);
        ctx.beginPath();
        ctx.arc(x, y, 2.4, 0, 2 * Math.PI);
        ctx.fill();
      }
    }
    if (pose) {
      ctx.save();
      ctx.translate(...project(pose[0], pose[1]));
      ctx.rotate(angle - pose[2]);
      ctx.fillStyle = palette.pose;
      ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--viewer");
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(12, 0); ctx.lineTo(-7, -7); ctx.lineTo(-4, 0); ctx.lineTo(-7, 7);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.restore();
    }
    const bar = meters < 35 ? 2 : meters > 155 ? 0.5 : 1;
    const y = height - 15;
    ctx.strokeStyle = ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--ink");
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(14, y); ctx.lineTo(14 + bar * meters, y);
    ctx.stroke();
    ctx.font = "11px Inter, system-ui, sans-serif";
    ctx.fillText(format.format(bar) + " м", 20 + bar * meters, y + 4);
    const count = graph?.nodes.length;
    const graphLabel = count === undefined ? "" : count + " " + keyframes[plural.select(count)] + " · ";
    byId("slam-info").textContent = graphLabel +
      format.format(map.width * map.resolution) + " × " +
      format.format(map.height * map.resolution) + " м";
  }

  function applyState(update) {
    if (Object.hasOwn(update, "map")) {
      map = update.map;
      updateRaster();
    }
    ({ connected, pose, graph } = update);
    draw();
  }

  async function poll() {
    try {
      if (panel.hidden) return;
      const revision = map?.revision || "";
      const response = await fetch("/api/slam?revision=" + revision, {
        headers, signal: AbortSignal.timeout(1200),
      });
      if (!response.ok) throw new Error("SLAM data unavailable");
      applyState(await response.json());
    } catch {
      connected = false;
      pose = null;
      draw();
    } finally {
      setTimeout(poll, 400);
    }
  }

  graphToggle.addEventListener("change", draw);
  new ResizeObserver(draw).observe(canvas);
  new MutationObserver(() => { updateRaster(); draw(); })
    .observe(document.documentElement, { attributeFilter: ["data-theme"] });
  if (panel.dataset.source === "replay") {
    panel.addEventListener("slam-state", (event) => applyState(event.detail));
  } else {
    poll();
  }
})();
