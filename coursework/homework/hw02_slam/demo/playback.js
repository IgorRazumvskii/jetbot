"use strict";

(() => {
  const get = (id) => document.getElementById(id);
  const video = get("camera");
  const cameraImage = get("camera-image");
  const cameraContext = cameraImage.getContext("2d");
  const play = get("play");
  const seek = get("seek");
  const time = get("time");
  const mapPanel = get("slam-panel");
  const cloudPanel = get("cloud-panel");
  const tabs = [get("map-tab"), get("cloud-tab")];
  const expandButtons = [...document.querySelectorAll(".expand")];
  let data;
  let lastMap = null;
  let lastState;
  let lastCloud;
  let expanded;
  let cameraLoop = 0;

  function paintCamera() {
    if (video.readyState < 2) return;
    if (cameraImage.width !== video.videoWidth || cameraImage.height !== video.videoHeight) {
      cameraImage.width = video.videoWidth;
      cameraImage.height = video.videoHeight;
    }
    cameraContext.drawImage(video, 0, 0);
  }

  function playCamera() {
    paintCamera();
    cameraLoop = video.paused ? 0 : requestAnimationFrame(playCamera);
  }

  function format(seconds) {
    const rounded = Math.floor(Math.max(0, seconds));
    return Math.floor(rounded / 60) + ":" + String(rounded % 60).padStart(2, "0");
  }

  function atTime(track, t) {
    let start = 0;
    let end = track.length;
    while (start < end) {
      const middle = (start + end) >> 1;
      if (track[middle].t <= t) start = middle + 1;
      else end = middle;
    }
    return track[start - 1];
  }

  function update() {
    if (!data) return;
    const t = video.currentTime;
    seek.value = Math.min(t, data.duration);
    time.textContent = format(t) + " / " + format(data.duration + 0.5);
    seek.setAttribute("aria-valuetext", time.textContent);
    const state = atTime(data.timeline, t);
    if (lastState !== state) {
      lastState = state;
      const points = state?.path || [];
      const edges = [];
      for (let i = 1; i < points.length; i++) edges.push(points[i - 1], points[i]);
      const updateMap = {
        connected: true, pose: state?.pose || null,
        graph: points.length ? { nodes: points, edges } : null,
      };
      const grid = data.maps[state?.map] || null;
      if (lastMap !== grid) {
        updateMap.map = grid;
        lastMap = grid;
      }
      mapPanel.dispatchEvent(new CustomEvent("slam-state", { detail: updateMap }));
    }
    if (!cloudPanel.hidden) {
      const cloud = atTime(data.clouds, t);
      if (lastCloud !== cloud) {
        lastCloud = cloud;
        cloudPanel.dispatchEvent(new CustomEvent("lidar-frame", { detail: cloud?.points || "" }));
      }
    }
  }

  function report(text) {
    const error = get("replay-error");
    error.textContent = text;
    error.hidden = false;
  }

  play.addEventListener("click", async () => {
    if (!video.paused) {
      video.pause();
      return;
    }
    if (video.ended) video.currentTime = 0;
    try {
      await video.play();
    } catch {
      report("Не удалось воспроизвести видео. Обновите страницу.");
    }
  });
  seek.addEventListener("input", () => {
    video.currentTime = Number(seek.value);
    update();
  });
  for (const event of ["timeupdate", "seeking", "seeked", "loadedmetadata"]) {
    video.addEventListener(event, update);
  }
  video.addEventListener("loadeddata", paintCamera);
  video.addEventListener("seeked", paintCamera);
  video.addEventListener("play", () => {
    if (!cameraLoop) playCamera();
  });
  for (const event of ["play", "pause", "ended"]) {
    video.addEventListener(event, () => {
      play.textContent = video.ended ? "С начала" : video.paused ? "Воспроизвести" : "Пауза";
    });
  }
  video.addEventListener("error", () => report("Видео не загрузилось. Обновите страницу."));

  function selectTab(tab) {
    tabs.forEach((item) => {
      const active = item === tab;
      item.setAttribute("aria-selected", active);
      item.tabIndex = active ? 0 : -1;
      get(item.getAttribute("aria-controls")).hidden = !active;
    });
    update();
  }

  for (const tab of tabs) {
    tab.addEventListener("click", () => selectTab(tab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const target = event.key === "Home" ? tabs[0] : event.key === "End" ? tabs[1] :
        tabs[1 - tabs.indexOf(tab)];
      selectTab(target);
      target.focus();
    });
  }

  function updateFullscreen(panel) {
    if (expanded) expanded.classList.remove("expanded-view");
    expanded = panel;
    for (const button of expandButtons) {
      const active = panel?.id === button.dataset.target;
      button.setAttribute("aria-pressed", active);
      button.textContent = active ? "Свернуть" : "На весь экран";
    }
  }

  for (const button of expandButtons) {
    button.addEventListener("click", async () => {
      const panel = get(button.dataset.target);
      if (expanded === panel) {
        if (document.fullscreenElement) await document.exitFullscreen();
        else updateFullscreen(null);
        return;
      }
      if (panel.requestFullscreen) {
        try {
          await panel.requestFullscreen();
          return;
        } catch { /* The CSS mode also works in embedded browsers. */ }
      }
      updateFullscreen(panel);
      panel.classList.add("expanded-view");
    });
  }
  document.addEventListener("fullscreenchange", () => updateFullscreen(document.fullscreenElement));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && expanded && !document.fullscreenElement) updateFullscreen(null);
  });

  fetch("/replay.json").then((response) => {
    if (!response.ok) throw new Error("Missing replay data");
    return response.json();
  }).then((recording) => {
    data = recording;
    seek.max = data.duration;
    seek.disabled = play.disabled = false;
    update();
  }).catch(() => report("Запись SLAM не загрузилась. Обновите страницу."));
})();
