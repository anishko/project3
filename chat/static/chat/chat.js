(function () {
  "use strict";

  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");
  const log = document.getElementById("chat-log");
  if (!form) return;

  const endpoint = form.dataset.endpoint;
  const csrfToken = form.querySelector("input[name=csrfmiddlewaretoken]").value;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text; // textContent: never inject HTML from the API
    return node;
  }

  function addMessage(role, text) {
    const msg = el("div", "chat-msg " + role);
    const bubble = el("div", "chat-bubble", text);
    msg.appendChild(bubble);
    log.appendChild(msg);
    log.scrollTop = log.scrollHeight;
    return msg;
  }

  // Same card markup/classes as the Story #4 citation UI.
  function renderSources(msg, sources) {
    const wrap = el("div", "chat-sources");
    const header = el("div", "source-header");
    const heading = el("div");
    heading.appendChild(el("p", "eyebrow", "Verification"));
    heading.appendChild(el("h2", "", "Sources used"));
    header.appendChild(heading);
    header.appendChild(el("span", "source-count", sources.length + " source" + (sources.length === 1 ? "" : "s")));
    wrap.appendChild(header);

    if (!sources.length) {
      wrap.appendChild(el("div", "empty-state", "No sources matched this question. ReliefRoute will not invent a citation."));
      msg.appendChild(wrap);
      return;
    }

    const list = el("div", "source-list");
    sources.forEach(function (s) {
      const card = el("article", "source-card");
      const top = el("div", "source-card-top");
      top.appendChild(el("span", "verified-badge", "Source"));
      if (s.disaster) top.appendChild(el("span", "metadata-chip", s.disaster));
      card.appendChild(top);
      card.appendChild(el("h3", "", s.title));
      const meta = el("div", "source-meta");
      if (s.source_name) meta.appendChild(el("span", "", s.source_name));
      if (s.published_date) meta.appendChild(el("span", "", s.published_date));
      if (meta.childNodes.length) card.appendChild(meta);
      if (s.excerpt) card.appendChild(el("p", "", s.excerpt));
      if (s.url && /^https?:\/\//i.test(s.url)) {
        const a = el("a", "source-link", "Open original source ↗");
        a.href = s.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        card.appendChild(a);
      }
      list.appendChild(card);
    });
    wrap.appendChild(list);
    msg.appendChild(wrap);
  }

  function setLoading(on) {
    sendBtn.disabled = on;
    input.disabled = on;
    sendBtn.textContent = on ? "Thinking…" : "Send";
  }

  async function ask(question) {
    addMessage("user", question);
    const pending = addMessage("bot loading", "Searching sources");
    pending.querySelector(".chat-bubble").appendChild(el("span", "dots"));
    setLoading(true);

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ question: question }),
      });
      let data = {};
      try { data = await res.json(); } catch (e) { /* non-JSON error page */ }
      pending.remove();
      if (!res.ok || data.error) {
        addMessage("bot error", data.error || "Something went wrong (HTTP " + res.status + "). Please try again.");
      } else {
        const msg = addMessage("bot", data.answer);
        renderSources(msg, data.sources || []);
      }
    } catch (err) {
      pending.remove();
      addMessage("bot error", "Couldn't reach the server. Check your connection and try again.");
    } finally {
      setLoading(false);
      input.focus();
      log.scrollTop = log.scrollHeight;
    }
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    const q = input.value.trim();
    if (!q || sendBtn.disabled) return;
    input.value = "";
    ask(q);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  log.addEventListener("click", function (e) {
    if (e.target.classList.contains("chat-suggestion") && !sendBtn.disabled) ask(e.target.textContent);
  });
})();
