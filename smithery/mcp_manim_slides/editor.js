(function () {
  "use strict";

  const LAYOUT_URL = "/__layout";
  const THEMES = [
    "black", "white", "league", "beige", "sky", "night",
    "serif", "simple", "solarized", "blood", "moon", "dracula",
  ];
  const CORNERS = ["nw", "ne", "sw", "se"];

  const state = {
    theme: "black",
    slides: [],
    selectedId: null,
    nextId: 1,
  };
  let statusTimer = null;

  function topSections() {
    return Array.from(document.querySelectorAll(".reveal .slides > section"));
  }

  function slideEntry(section) {
    return state.slides[Number(section.dataset.deckIndex)] || null;
  }

  function forEachOverlay(callback) {
    state.slides.forEach(function (slide) {
      slide.overlays.forEach(callback);
    });
  }

  function findOverlay(id) {
    let match = null;
    forEachOverlay(function (overlay) {
      if (overlay.id === id) match = overlay;
    });
    return match;
  }

  function clamp(value, low, high) {
    return Math.min(Math.max(value, low), high);
  }

  function round4(value) {
    return Math.round(value * 10000) / 10000;
  }

  function showStatus(message) {
    const status = document.getElementById("deck-status");
    if (!status) return;
    status.textContent = message;
    if (statusTimer) window.clearTimeout(statusTimer);
    statusTimer = window.setTimeout(function () {
      status.textContent = "";
    }, 4000);
  }

  function revealSync() {
    if (window.Reveal && typeof window.Reveal.sync === "function") {
      window.Reveal.sync();
    }
  }

  function revealSlide(index) {
    if (window.Reveal && typeof window.Reveal.slide === "function") {
      window.Reveal.slide(index);
    }
  }

  function currentSection() {
    if (window.Reveal && typeof window.Reveal.getCurrentSlide === "function") {
      const active = window.Reveal.getCurrentSlide();
      if (active && active.dataset && active.dataset.deckIndex !== undefined) {
        return active;
      }
    }
    return topSections()[0] || null;
  }

  function syncOverlayEl(overlay) {
    const el = overlay.el;
    if (!el) return;
    el.style.left = overlay.x + "%";
    el.style.top = overlay.y + "%";
    el.style.width = overlay.w + "%";
    el.style.height = overlay.h + "%";
    el.style.zIndex = String(overlay.z);
    const body = el.querySelector(".deck-overlay-body");
    if (!body) return;
    if (overlay.type === "image") {
      body.src = overlay.src || "";
    } else {
      body.textContent = overlay.text || "";
      body.style.color = overlay.color || "#ffffff";
      body.style.fontSize = (overlay.font_size || 32) + "px";
    }
  }

  function attachOverlayEl(section, overlay) {
    const el = document.createElement("div");
    el.className = "deck-overlay";
    el.dataset.overlayId = overlay.id;
    const body = document.createElement(overlay.type === "image" ? "img" : "div");
    body.className = "deck-overlay-body";
    if (overlay.type === "image") {
      body.alt = "";
    } else {
      body.addEventListener("dblclick", function () {
        body.contentEditable = "true";
        body.focus();
      });
      body.addEventListener("blur", function () {
        body.contentEditable = "false";
        overlay.text = body.textContent;
        updateInspector();
      });
    }
    el.appendChild(body);
    CORNERS.forEach(function (corner) {
      const handle = document.createElement("div");
      handle.className = "deck-handle";
      handle.dataset.corner = corner;
      handle.addEventListener("pointerdown", function (event) {
        event.preventDefault();
        event.stopPropagation();
        selectOverlay(overlay.id);
        startResize(event, section, overlay, corner);
      });
      el.appendChild(handle);
    });
    el.addEventListener("pointerdown", function (event) {
      if (event.target.classList.contains("deck-handle")) return;
      startDrag(event, section, overlay);
    });
    overlay.el = el;
    section.appendChild(el);
    syncOverlayEl(overlay);
  }

  function startDrag(event, section, overlay) {
    if (event.button !== 0) return;
    event.preventDefault();
    selectOverlay(overlay.id);
    const rect = section.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const originX = overlay.x;
    const originY = overlay.y;
    function onMove(moveEvent) {
      const dx = ((moveEvent.clientX - startX) / rect.width) * 100;
      const dy = ((moveEvent.clientY - startY) / rect.height) * 100;
      overlay.x = clamp(originX + dx, 0, 100 - overlay.w);
      overlay.y = clamp(originY + dy, 0, 100 - overlay.h);
      syncOverlayEl(overlay);
    }
    function onUp() {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      renderPanel();
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  function startResize(event, section, overlay, corner) {
    const rect = section.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const origin = { x: overlay.x, y: overlay.y, w: overlay.w, h: overlay.h };
    function onMove(moveEvent) {
      const dx = ((moveEvent.clientX - startX) / rect.width) * 100;
      const dy = ((moveEvent.clientY - startY) / rect.height) * 100;
      let x = origin.x;
      let y = origin.y;
      let w = origin.w;
      let h = origin.h;
      if (corner.indexOf("e") !== -1) w = clamp(origin.w + dx, 1, 100 - origin.x);
      if (corner.indexOf("s") !== -1) h = clamp(origin.h + dy, 1, 100 - origin.y);
      if (corner.indexOf("w") !== -1) {
        x = clamp(origin.x + dx, 0, origin.x + origin.w - 1);
        w = origin.w + (origin.x - x);
      }
      if (corner.indexOf("n") !== -1) {
        y = clamp(origin.y + dy, 0, origin.y + origin.h - 1);
        h = origin.h + (origin.y - y);
      }
      overlay.x = x;
      overlay.y = y;
      overlay.w = w;
      overlay.h = h;
      syncOverlayEl(overlay);
    }
    function onUp() {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  function selectOverlay(id) {
    state.selectedId = id;
    forEachOverlay(function (overlay) {
      if (overlay.el) {
        overlay.el.classList.toggle("deck-selected", overlay.id === id);
      }
    });
    updateInspector();
  }

  function updateInspector() {
    const textInput = document.getElementById("deck-text");
    const colorInput = document.getElementById("deck-color");
    const fontInput = document.getElementById("deck-font-size");
    if (!textInput || !colorInput || !fontInput) return;
    const overlay = findOverlay(state.selectedId);
    const editable = !!overlay && overlay.type === "text";
    textInput.disabled = !editable;
    colorInput.disabled = !editable;
    fontInput.disabled = !editable;
    textInput.value = editable ? overlay.text || "" : "";
    colorInput.value = editable ? overlay.color || "#ffffff" : "#ffffff";
    fontInput.value = editable ? String(overlay.font_size || 32) : "";
  }

  function makeOverlay(data) {
    const type = data && data.type === "image" ? "image" : "text";
    return {
      id: data && typeof data.id === "string" && data.id ? data.id : "o" + state.nextId++,
      type: type,
      x: Number(data && data.x) || 0,
      y: Number(data && data.y) || 0,
      w: Number(data && data.w) || (type === "image" ? 30 : 40),
      h: Number(data && data.h) || (type === "image" ? 40 : 15),
      z: Number(data && data.z) || 0,
      text: type === "text" ? String((data && data.text) || "") : null,
      src: type === "image" ? String((data && data.src) || "") : null,
      color: type === "text" ? String((data && data.color) || "#ffffff") : null,
      font_size: type === "text" ? Number(data && data.font_size) || 32 : null,
      slide: null,
      el: null,
    };
  }

  function pushOverlay(slide, overlay) {
    overlay.slide = slide;
    overlay.z = slide.overlays.length;
    slide.overlays.push(overlay);
    const numeric = Number(String(overlay.id).replace(/^o/, ""));
    if (numeric >= state.nextId) state.nextId = numeric + 1;
  }

  function addOverlay(type) {
    const section = currentSection();
    const slide = section ? slideEntry(section) : null;
    if (!slide || !section) {
      showStatus("No slide selected");
      return;
    }
    let overlay;
    if (type === "image") {
      const url = window.prompt("Image URL:");
      if (!url) return;
      overlay = makeOverlay({ type: "image", src: url, x: 35, y: 25, w: 30, h: 40 });
    } else {
      overlay = makeOverlay({
        type: "text", text: "Text", x: 30, y: 40, w: 40, h: 15,
        color: "#ffffff", font_size: 32,
      });
    }
    pushOverlay(slide, overlay);
    attachOverlayEl(section, overlay);
    selectOverlay(overlay.id);
    renderPanel();
  }

  function deleteSelected() {
    const overlay = findOverlay(state.selectedId);
    if (!overlay) return;
    const slide = overlay.slide;
    const position = slide.overlays.indexOf(overlay);
    if (position !== -1) slide.overlays.splice(position, 1);
    if (overlay.el && overlay.el.parentNode) {
      overlay.el.parentNode.removeChild(overlay.el);
    }
    selectOverlay(null);
    relayer(slide);
  }

  function relayer(slide) {
    slide.overlays.forEach(function (overlay, position) {
      overlay.z = position;
      if (overlay.el) {
        slide.section.appendChild(overlay.el);
        overlay.el.style.zIndex = String(position);
      }
    });
    renderPanel();
  }

  function bumpZ(delta) {
    const overlay = findOverlay(state.selectedId);
    if (!overlay) return;
    const slide = overlay.slide;
    const position = slide.overlays.indexOf(overlay);
    const target = position + delta;
    if (target < 0 || target >= slide.overlays.length) return;
    slide.overlays.splice(position, 1);
    slide.overlays.splice(target, 0, overlay);
    relayer(slide);
    showStatus(delta > 0 ? "Capa subida" : "Capa bajada");
  }

  function renderPanel() {
    const panel = document.getElementById("deck-slide-panel");
    if (!panel) return;
    panel.innerHTML = "";
    topSections().forEach(function (section, position) {
      const slide = slideEntry(section);
      const row = document.createElement("div");
      row.className = "deck-slide-row" + (slide && slide.hidden ? " deck-hidden" : "");
      row.draggable = true;
      row.dataset.position = String(position);
      const count = slide ? slide.overlays.length : 0;
      const label = slide && slide.hidden ? "Show" : "Hide";
      row.innerHTML =
        '<span class="deck-slide-label">Slide ' + (position + 1) + "</span>" +
        '<span class="deck-slide-count">' + count + "</span>" +
        '<button data-act="toggle-hidden">' + label + "</button>";
      row.querySelector("button").addEventListener("click", function () {
        if (slide) toggleHidden(slide);
      });
      row.addEventListener("dragstart", function (event) {
        event.dataTransfer.setData("text/plain", String(position));
      });
      row.addEventListener("dragover", function (event) {
        event.preventDefault();
      });
      row.addEventListener("drop", function (event) {
        event.preventDefault();
        moveSection(Number(event.dataTransfer.getData("text/plain")), position);
      });
      panel.appendChild(row);
    });
  }

  function toggleHidden(slide) {
    slide.hidden = !slide.hidden;
    if (slide.hidden) {
      slide.section.setAttribute("data-visibility", "hidden");
    } else {
      slide.section.removeAttribute("data-visibility");
    }
    revealSync();
    renderPanel();
  }

  function moveSection(from, to) {
    const sections = topSections();
    const last = sections.length - 1;
    if (from === to || from < 0 || to < 0 || from > last || to > last) return;
    const parent = sections[0].parentNode;
    const moving = sections[from];
    const reference = sections[to];
    parent.insertBefore(moving, from < to ? reference.nextSibling : reference);
    revealSync();
    revealSlide(Math.min(to, last));
    renderPanel();
    showStatus("Slides reordered");
  }

  function findThemeLink() {
    const links = document.querySelectorAll('link[rel="stylesheet"]');
    for (const link of links) {
      if (/\/theme\/[^/]+\.css/.test(link.getAttribute("href") || "")) return link;
    }
    return null;
  }

  function setTheme(theme) {
    state.theme = theme;
    const select = document.getElementById("deck-theme");
    if (select && select.value !== theme) select.value = theme;
    const link = findThemeLink();
    if (link) {
      link.href = link.href.replace(/\/theme\/[^/]+\.css/, "/theme/" + theme + ".css");
    } else {
      const fallback = document.createElement("link");
      fallback.rel = "stylesheet";
      fallback.href = "https://cdn.jsdelivr.net/npm/reveal.js@5/dist/theme/" + theme + ".css";
      document.head.appendChild(fallback);
    }
    showStatus("Theme: " + theme);
  }

  function buildLayout() {
    return {
      version: 1,
      theme: state.theme,
      slides: topSections().map(function (section, order) {
        const slide = slideEntry(section) || { index: order, hidden: false, overlays: [] };
        return {
          index: slide.index,
          order: order,
          hidden: !!slide.hidden,
          overlays: slide.overlays.map(function (overlay, position) {
            return {
              id: overlay.id,
              type: overlay.type,
              x: round4(overlay.x),
              y: round4(overlay.y),
              w: round4(overlay.w),
              h: round4(overlay.h),
              z: position,
              text: overlay.type === "text" ? overlay.text : null,
              src: overlay.type === "image" ? overlay.src : null,
              color: overlay.type === "text" ? overlay.color : null,
              font_size: overlay.type === "text" ? round4(overlay.font_size) : null,
            };
          }),
        };
      }),
    };
  }

  function applyLayout(data) {
    if (!data || data.version !== 1 || !Array.isArray(data.slides)) return false;
    if (typeof data.theme === "string" && THEMES.indexOf(data.theme) !== -1) {
      setTheme(data.theme);
    }
    const sections = topSections();
    const parent = sections.length ? sections[0].parentNode : null;
    const listed = {};
    const ordered = data.slides.slice().sort(function (a, b) {
      return (Number(a.order) || 0) - (Number(b.order) || 0);
    });
    ordered.forEach(function (entry) {
      const index = Number(entry.index);
      const slide = state.slides[index];
      const section = sections.find(function (item) {
        return Number(item.dataset.deckIndex) === index;
      });
      if (!slide || !section) return;
      listed[index] = true;
      if (parent) parent.appendChild(section);
      slide.hidden = !!entry.hidden;
      if (slide.hidden) {
        section.setAttribute("data-visibility", "hidden");
      } else {
        section.removeAttribute("data-visibility");
      }
      const overlays = Array.isArray(entry.overlays) ? entry.overlays : [];
      overlays.forEach(function (raw) {
        const overlay = makeOverlay(raw);
        pushOverlay(slide, overlay);
        attachOverlayEl(section, overlay);
      });
      slide.overlays.forEach(function (overlay, position) {
        overlay.z = position;
        syncOverlayEl(overlay);
      });
    });
    sections.forEach(function (section) {
      const index = Number(section.dataset.deckIndex);
      if (!listed[index] && parent) parent.appendChild(section);
    });
    revealSync();
    return true;
  }

  function saveLayout() {
    fetch(LAYOUT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildLayout()),
    })
      .then(function (response) { return response.json(); })
      .then(function (payload) {
        if (payload && payload.success) {
          showStatus("Layout saved");
        } else {
          showStatus("Save failed: " + ((payload && payload.error) || "unknown error"));
        }
      })
      .catch(function (error) { showStatus("Save failed: " + error); });
  }

  function loadLayout() {
    fetch(LAYOUT_URL)
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (applyLayout(data)) showStatus("Layout loaded");
        renderPanel();
      })
      .catch(function () { renderPanel(); });
  }

  function buildChrome() {
    const toolbar = document.createElement("div");
    toolbar.id = "deck-editor";
    toolbar.innerHTML = [
      '<button data-action="add-text">Add text</button>',
      '<button data-action="add-image">Add image</button>',
      '<button data-action="delete">Delete</button>',
      '<button data-action="z-up">Subir capa</button>',
      '<button data-action="z-down">Bajar capa</button>',
      '<label>Theme <select id="deck-theme"></select></label>',
      '<label>Text <input id="deck-text" type="text" size="16"></label>',
      '<label>Color <input id="deck-color" type="color" value="#ffffff"></label>',
      '<label>Size <input id="deck-font-size" type="number" min="8" max="400"></label>',
      '<button data-action="save">Save</button>',
      '<span id="deck-status"></span>',
    ].join("");
    document.body.appendChild(toolbar);
    const panel = document.createElement("div");
    panel.id = "deck-slide-panel";
    document.body.appendChild(panel);

    toolbar.addEventListener("click", function (event) {
      const button = event.target.closest("button[data-action]");
      if (!button) return;
      const action = button.dataset.action;
      if (action === "add-text") addOverlay("text");
      else if (action === "add-image") addOverlay("image");
      else if (action === "delete") deleteSelected();
      else if (action === "z-up") bumpZ(1);
      else if (action === "z-down") bumpZ(-1);
      else if (action === "save") saveLayout();
    });

    const themeSelect = document.getElementById("deck-theme");
    THEMES.forEach(function (name) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      themeSelect.appendChild(option);
    });
    themeSelect.value = state.theme;
    themeSelect.addEventListener("change", function () {
      setTheme(themeSelect.value);
    });

    const textInput = document.getElementById("deck-text");
    const colorInput = document.getElementById("deck-color");
    const fontInput = document.getElementById("deck-font-size");
    textInput.addEventListener("input", function () {
      const overlay = findOverlay(state.selectedId);
      if (!overlay || overlay.type !== "text") return;
      overlay.text = textInput.value;
      syncOverlayEl(overlay);
    });
    colorInput.addEventListener("input", function () {
      const overlay = findOverlay(state.selectedId);
      if (!overlay || overlay.type !== "text") return;
      overlay.color = colorInput.value;
      syncOverlayEl(overlay);
    });
    fontInput.addEventListener("input", function () {
      const overlay = findOverlay(state.selectedId);
      if (!overlay || overlay.type !== "text") return;
      overlay.font_size = Number(fontInput.value) || 32;
      syncOverlayEl(overlay);
    });

    const slidesRoot = document.querySelector(".reveal .slides");
    if (slidesRoot) {
      slidesRoot.addEventListener("pointerdown", function (event) {
        if (event.target.closest(".deck-overlay")) return;
        selectOverlay(null);
      });
    }
  }

  function init() {
    if (!document.querySelector(".reveal .slides")) {
      console.warn("[deck-editor] no Reveal slides found");
      return;
    }
    topSections().forEach(function (section, index) {
      section.dataset.deckIndex = String(index);
      state.slides.push({ index: index, hidden: false, overlays: [], section: section });
    });
    buildChrome();
    renderPanel();
    updateInspector();
    loadLayout();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
