"use strict";

(() => {
  const panel = document.getElementById("cloud-panel");
  const canvas = document.getElementById("cloud-view");
  const ctx = canvas.getContext("2d");
  const label = document.getElementById("cloud-info");
  let points = new DataView(new ArrayBuffer(0));
  let azimuth = -0.65;
  let elevation = 0.58;
  let zoom = 1;
  let pointer;

  function draw() {
    if (panel.hidden) return;
    const { width, height } = canvas.getBoundingClientRect();
    if (!width || !height) return;
    const ratio = window.devicePixelRatio || 1;
    const pixelWidth = Math.round(width * ratio);
    const pixelHeight = Math.round(height * ratio);
    if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
    if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const scale = Math.min(width, height) / 19 * zoom;
    const ca = Math.cos(azimuth), sa = Math.sin(azimuth);
    const ce = Math.cos(elevation), se = Math.sin(elevation);
    function project(x, y, z) {
      const side = x * ca - y * sa;
      const forward = x * sa + y * ca;
      return [width / 2 + side * scale, height / 2 + (forward * se - z * ce) * scale,
        forward * ce + z * se];
    }

    ctx.strokeStyle = "#29383e";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = -8; i <= 8; i += 2) {
      ctx.moveTo(...project(i, -8, -0.507).slice(0, 2));
      ctx.lineTo(...project(i, 8, -0.507).slice(0, 2));
      ctx.moveTo(...project(-8, i, -0.507).slice(0, 2));
      ctx.lineTo(...project(8, i, -0.507).slice(0, 2));
    }
    ctx.stroke();

    const visible = [];
    for (let i = 0; i < points.byteLength; i += 6) {
      const x = points.getInt16(i, true) / 50;
      const y = points.getInt16(i + 2, true) / 50;
      const z = points.getInt16(i + 4, true) / 50;
      const [px, py, depth] = project(x, y, z);
      if (px >= 0 && px < width && py >= 0 && py < height) visible.push({ px, py, depth, z });
    }
    visible.sort((a, b) => a.depth - b.depth);
    for (const { px, py, z } of visible) {
      ctx.fillStyle = z < -0.26 ? "#7e9db4" : z < 0.35 ? "#9dc9f1" : "#f7cc8e";
      ctx.fillRect(px - 1.1, py - 1.1, 2.2, 2.2);
    }

    const [x, y] = project(0, 0, 0);
    ctx.fillStyle = "#f2a872";
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  }

  function rotate(dx, dy) {
    azimuth += dx * 0.008;
    elevation = Math.min(1.48, Math.max(0.12, elevation + dy * 0.008));
    draw();
  }

  function changeZoom(factor) {
    zoom = Math.min(3.8, Math.max(0.55, zoom * factor));
    draw();
  }

  panel.addEventListener("lidar-frame", (event) => {
    const raw = atob(event.detail);
    const bytes = Uint8Array.from(raw, (char) => char.charCodeAt(0));
    points = new DataView(bytes.buffer);
    label.textContent = bytes.length ? `${bytes.length / 6} точек · фрейм лидара` : "Ожидаю скан";
    draw();
  });
  canvas.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    canvas.setPointerCapture(event.pointerId);
    pointer = event.pointerId;
  });
  canvas.addEventListener("pointermove", (event) => {
    if (event.pointerId === pointer) rotate(event.movementX, event.movementY);
  });
  canvas.addEventListener("lostpointercapture", () => { pointer = undefined; });
  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    changeZoom(Math.exp(-event.deltaY * 0.001));
  }, { passive: false });
  canvas.addEventListener("keydown", (event) => {
    const steps = {
      ArrowLeft: [-12, 0], ArrowRight: [12, 0], ArrowUp: [0, -12], ArrowDown: [0, 12],
    };
    if (steps[event.key]) rotate(...steps[event.key]);
    else if (event.key === "+" || event.key === "=") changeZoom(1.15);
    else if (event.key === "-") changeZoom(1 / 1.15);
    else return;
    event.preventDefault();
  });
  new ResizeObserver(draw).observe(canvas);
})();
