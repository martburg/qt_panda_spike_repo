// ==UserScript==
// @name         Obsidian Saver (Chat + Web)
// @namespace    wiredworks.obsidian.saver
// @version      2.0.0
// @description  Save ChatGPT chats and any webpage to your local Obsidian saver (chat: POST /, web: POST /web)
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @match        https://*/*
// @match        http://*/*
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @grant        unsafeWindow
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

(function () {
  "use strict";

  // ===== CONFIG =====
  const ENDPOINT = "http://127.0.0.1:8765";
  const LS_LAST = "chat_saver_project_last";

  // ===== Utilities =====
  function gm(method, url, headers = {}, data = null, timeout = 30000) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method, url, headers, data, timeout,
        onload: (r) => resolve(r),
        onerror: (e) => reject(e),
        ontimeout: () => reject(new Error("timeout")),
      });
    });
  }

  async function getProjects() {
    try {
      const r = await gm("GET", ENDPOINT + "/projects");
      const j = JSON.parse(r.responseText || "{}");
      if (j.ok && Array.isArray(j.projects) && j.projects.length) return j.projects;
    } catch (_) {}
    return ["Inbox"];
  }

  function pageMeta() {
    const url = location.href;
    const title = (document.title || url).replace(/\s*[-|—]\s*ChatGPT.*$/i, "").trim() || url;
    return { url, title };
  }

  // ===== Picker UI (shared) =====
  function showPicker({ projects, initial, titleDefault, includeMode=false, defaultMode="readable" }) {
    return new Promise((resolve) => {
      const root = document.createElement("div");
      root.id = "obsidian-picker";
      root.innerHTML = `
      <style>
        #obsidian-picker { position: fixed; inset: 0; z-index: 2147483647; display: grid; place-items: center; background: rgba(0,0,0,.35); font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
        #obsidian-card { width: min(560px, 92vw); background: #fff; color: #111; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,.25); padding: 16px; }
        @media (prefers-color-scheme: dark) {
          #obsidian-card { background: #1f1f1f; color: #eee; }
          #obsidian-card select, #obsidian-card input, #obsidian-card textarea { background:#111; color:#eee; border-color:#333; }
        }
        #obsidian-card h3 { margin: 0 0 8px; font-size: 16px; }
        .row { display: grid; grid-template-columns: 1fr; gap: 8px; margin-top: 8px; }
        select, input, textarea { padding: 8px 10px; font-size: 14px; border: 1px solid #ccc; border-radius: 8px; outline: none; }
        textarea { min-height: 64px; resize: vertical; }
        #obsidian-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
        .btn { padding: 8px 12px; border: 0; border-radius: 8px; font-weight: 600; cursor: pointer; }
        .btn.save { background: #16a34a; color: white; }
        .btn.cancel { background: #e5e7eb; }
        @media (prefers-color-scheme: dark) { .btn.cancel { background: #333; color:#eee; } }
      </style>
      <div id="obsidian-card" role="dialog" aria-label="Save to Obsidian">
        <h3>Save to Obsidian</h3>
        <div class="row">
          <label>Project</label>
          <select id="ob-sel"></select>
          <input id="ob-inp" type="text" placeholder="…or type a new project" />
        </div>
        <div class="row" id="ob-mode-row" style="display:${includeMode?'grid':'none'}">
          <label>Mode</label>
          <select id="ob-mode">
            <option value="readable"${defaultMode==="readable"?' selected':''}>Readable + Link (default)</option>
            <option value="link">Link only</option>
            <option value="snapshot">Snapshot (browser HTML)</option>
          </select>
        </div>
        <div class="row">
          <label>Title (optional override)</label>
          <input id="ob-title" type="text" />
        </div>
        <div class="row">
          <label>Note (optional)</label>
          <textarea id="ob-note" placeholder="Add a short note…"></textarea>
        </div>
        <div id="obsidian-actions">
          <button class="btn cancel" id="ob-cancel">Cancel</button>
          <button class="btn save" id="ob-save">Save</button>
        </div>
      </div>`;
      document.body.appendChild(root);

      const sel = root.querySelector("#ob-sel");
      const inp = root.querySelector("#ob-inp");
      const modeSel = root.querySelector("#ob-mode");
      const titleInp = root.querySelector("#ob-title");
      const noteArea = root.querySelector("#ob-note");
      const btnSave = root.querySelector("#ob-save");
      const btnCancel = root.querySelector("#ob-cancel");

      (projects || ["Inbox"]).forEach(p => {
        const opt = document.createElement("option");
        opt.value = p; opt.textContent = p;
        sel.appendChild(opt);
      });
      const preset = initial && projects.includes(initial) ? initial : (projects[0] || "Inbox");
      sel.value = preset;
      titleInp.value = titleDefault || "";
      noteArea.value = "";

      const close = () => root.remove();
      btnCancel.onclick = () => { close(); resolve(null); };
      btnSave.onclick = () => {
        const typed = inp.value.trim();
        const project = typed || sel.value || "Inbox";
        const mode = includeMode ? modeSel.value : undefined;
        const title = titleInp.value.trim();
        const note = noteArea.value.trim();
        close();
        resolve({ project, mode, title, note });
      };
      root.addEventListener("keydown", (e) => {
        if (e.key === "Escape") { close(); resolve(null); }
        if (e.key === "Enter") { btnSave.click(); }
      });
      setTimeout(() => inp.focus(), 0);
    });
  }

  // ===== Chat (ChatGPT) =====
  function collectChat() {
    const title = (document.title || "chat").replace(/\s*[-|—]\s*ChatGPT.*$/i, "").trim() || "chat";
    const roots = new Set();
    [
      '[data-message-author-role]',
      '[data-message-id]',
      'article[role="article"]',
      'article',
      'main div[class*="conversation"]',
      'main div[class*="chat"]'
    ].forEach(sel => document.querySelectorAll(sel).forEach(n => roots.add(n)));

    const messages = [];
    const seen = new Set();
    for (const n of roots) {
      const mid = n.getAttribute?.("data-message-id") || n.id || null;
      if (mid && seen.has(mid)) continue;
      if (mid) seen.add(mid);

      let role = (n.getAttribute?.("data-message-author-role") || n.getAttribute?.("data-message-author") || "");
      if (!role) {
        const txt = (n.innerText || "").slice(0, 400);
        role = /^(you|user)\b/i.test(txt) ? "user" : "assistant";
      }
      role = /user/i.test(role) ? "user" : "assistant";

      let text = "";
      const candidates = [
        '.markdown', '[data-testid="markdown"]',
        '[class*="prose"]', '[class*="markdown"]',
        'article .markdown', 'article [class*="prose"]',
        'p, li, pre, code'
      ];
      if (n.querySelector) {
        for (const sel of candidates) {
          const el = n.matches(sel) ? n : n.querySelector(sel);
          if (el && el.innerText) {
            text = el.innerText.trim();
            if (text) break;
          }
        }
      }
      if (!text) text = (n.innerText || "").trim();
      if (!text) continue;
      if (/^regenerate/i.test(text) && text.length < 30) continue;

      messages.push({ role, text });
    }

    if (!messages.length) {
      const last = document.querySelector('main') || document.body;
      const txt = (last && last.innerText || "").trim();
      if (txt) messages.push({ role: "assistant", text: txt.slice(0, 5000) });
    }
    return { title, messages };
  }

  async function saveChat() {
    const projects = await getProjects().catch(() => ["Inbox"]);
    const last = localStorage.getItem(LS_LAST) || (projects[0] || "Inbox");
    const meta = pageMeta();
    const pick = await showPicker({ projects, initial: last, titleDefault: meta.title, includeMode:false });
    if (!pick) return;
    let { project, title, note } = pick;
    if (project && typeof project !== "string") project = undefined; // guard against accidental event objects
    localStorage.setItem(LS_LAST, project);

    const { title: tFromPage, messages } = collectChat();
    const finalTitle = title || tFromPage || "chat";

    if (!messages.length) {
      const go = confirm("I couldn't extract messages from this chat. Save an empty stub anyway?");
      if (!go) return;
    }

    const body = { title: finalTitle, project, messages };
    if (note) {
      // prepend your note as a user message
      body.messages = [{ role: "user", text: `Note: ${note}` }, ...messages];
    }

    const resp = await gm("POST", ENDPOINT + "/", { "Content-Type": "application/json" }, JSON.stringify(body));
    const txt = resp.responseText || "";
    let j = null; try { j = JSON.parse(txt); } catch {}
    if (resp.status >= 200 && resp.status < 300 && j && j.ok) {
      alert(`Saved chat to "${j.project}":\n${j.vault_rel || "(no path returned)"}`);
    } else {
      alert(`Chat save failed (HTTP ${resp.status}).\n${txt.slice(0, 1200)}`);
    }
  }

  // ===== Web (any page) =====
  async function saveWeb(defaultMode = "readable") {
    const projects = await getProjects().catch(() => ["Inbox"]);
    const last = localStorage.getItem(LS_LAST) || (projects[0] || "Inbox");
    const meta = pageMeta();
    const pick = await showPicker({ projects, initial: last, titleDefault: meta.title, includeMode:true, defaultMode });
    if (!pick) return;
    let { project, mode, title, note } = pick;
    if (project && typeof project !== "string") project = undefined;
    localStorage.setItem(LS_LAST, project);

    const chosenMode = mode || defaultMode;
    const payload = {
      mode: chosenMode,
      url: meta.url,
      project,
      title: title || meta.title,
      note,
      tags: []
    };
    if (chosenMode === "readable" || chosenMode === "snapshot") {
      payload.html = "<!doctype html>\n" + document.documentElement.outerHTML;
    }

    const resp = await gm("POST", ENDPOINT + "/web", { "Content-Type": "application/json" }, JSON.stringify(payload));
    const txt = resp.responseText || "";
    let j = null; try { j = JSON.parse(txt); } catch {}
    if (resp.status >= 200 && resp.status < 300 && j && j.ok) {
      alert(`Saved page to "${j.project}":\n${j.vault_rel || "(no path returned)"}`);
    } else {
      alert(`Page save failed (HTTP ${resp.status}).\n${txt.slice(0, 1200)}`);
    }
  }

  // ===== Menus =====
  GM_registerMenuCommand("Save Chat to Obsidian (project picker)", () => saveChat());
  GM_registerMenuCommand("Save Page → Readable + Link (default)", () => saveWeb("readable"));
  GM_registerMenuCommand("Save Page → Link only", () => saveWeb("link"));
  GM_registerMenuCommand("Save Page → Snapshot (browser HTML)", () => saveWeb("snapshot"));

  // Console helpers
  unsafeWindow._obsidianSaveChat = () => saveChat();
  unsafeWindow._obsidianSavePage = (mode) => saveWeb(mode || "readable");
})();
