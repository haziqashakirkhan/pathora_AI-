(async function () {
  try {
    if (document.getElementById("pc-btn")) return;

    var pcConfigResponse = await fetch("/api/chat-config");
    if (!pcConfigResponse.ok) return;
    var pcConfig = await pcConfigResponse.json();
    if (!pcConfig || pcConfig.enabled !== true) return;
    if (document.getElementById("pc-btn")) return;

    var pcReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var pcHistory = [];
    var pcOpened = false;
    var pcIntroShown = false;
    var pcPending = false;
    var pcButton = document.createElement("button");
    pcButton.id = "pc-btn";
    pcButton.type = "button";
    pcButton.setAttribute("aria-label", "Open assistant");
    pcButton.setAttribute("aria-expanded", "false");
    Object.assign(pcButton.style, {
      position: "fixed",
      right: "calc(24px - (100vw - 100%))",
      bottom: "24px",
      width: "56px",
      height: "56px",
      border: "0",
      borderRadius: "50%",
      background: "#E13A52",
      color: "#ECEDEF",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      cursor: "pointer",
      zIndex: "1000",
      outlineOffset: "3px",
      boxShadow: "0 4px 16px rgba(0, 0, 0, 0.35)"
    });

    var pcIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    pcIcon.setAttribute("viewBox", "0 0 24 24");
    pcIcon.setAttribute("width", "25");
    pcIcon.setAttribute("height", "25");
    pcIcon.setAttribute("fill", "none");
    pcIcon.setAttribute("stroke", "currentColor");
    pcIcon.setAttribute("stroke-width", "2");
    pcIcon.setAttribute("stroke-linecap", "round");
    pcIcon.setAttribute("stroke-linejoin", "round");
    pcIcon.setAttribute("aria-hidden", "true");
    var pcIconPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    pcIconPath.setAttribute("d", "M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8z");
    pcIcon.appendChild(pcIconPath);
    pcButton.appendChild(pcIcon);

    var pcPanel = document.createElement("section");
    pcPanel.id = "pc-panel";
    pcPanel.setAttribute("role", "dialog");
    pcPanel.setAttribute("aria-label", "Pathora AI Assistant");
    pcPanel.setAttribute("aria-modal", "false");
    Object.assign(pcPanel.style, {
      position: "fixed",
      right: window.innerWidth < 480 ? "calc(8px - (100vw - 100%))" : "calc(24px - (100vw - 100%))",
      bottom: "96px",
      width: window.innerWidth < 480 ? "calc(100vw - 16px)" : "360px",
      maxWidth: window.innerWidth < 480 ? "none" : "calc(100vw - 16px)",
      height: "460px",
      maxHeight: "min(460px, 70vh)",
      display: "none",
      flexDirection: "column",
      overflow: "hidden",
      border: "1px solid #292A30",
      borderRadius: "16px",
      background: "#19191F",
      color: "#ECEDEF",
      fontFamily: "inherit",
      zIndex: "1000",
      boxSizing: "border-box",
      opacity: "0",
      transition: pcReducedMotion ? "none" : "opacity 150ms ease",
      boxShadow: "0 8px 28px rgba(0, 0, 0, 0.45)"
    });

    var pcHeader = document.createElement("header");
    Object.assign(pcHeader.style, {
      minHeight: "56px",
      padding: "0 14px",
      background: "#B8243A",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "12px",
      boxSizing: "border-box"
    });
    var pcTitle = document.createElement("strong");
    pcTitle.textContent = "Pathora AI Assistant";
    pcTitle.style.fontSize = "15px";
    var pcClose = document.createElement("button");
    pcClose.type = "button";
    pcClose.setAttribute("aria-label", "Close assistant");
    pcClose.textContent = "×";
    Object.assign(pcClose.style, {
      width: "34px",
      height: "34px",
      border: "0",
      borderRadius: "8px",
      background: "transparent",
      color: "#ECEDEF",
      fontSize: "24px",
      cursor: "pointer",
      outlineOffset: "2px"
    });
    pcHeader.append(pcTitle, pcClose);

    var pcMessages = document.createElement("div");
    pcMessages.id = "pc-messages";
    pcMessages.setAttribute("aria-live", "polite");
    pcMessages.setAttribute("aria-relevant", "additions text");
    Object.assign(pcMessages.style, {
      flex: "1",
      minHeight: "0",
      overflowY: "auto",
      padding: "14px",
      display: "flex",
      flexDirection: "column",
      gap: "10px",
      boxSizing: "border-box"
    });

    var pcForm = document.createElement("form");
    pcForm.id = "pc-form";
    Object.assign(pcForm.style, {
      display: "flex",
      gap: "8px",
      padding: "12px",
      borderTop: "1px solid #292A30",
      boxSizing: "border-box"
    });
    var pcInput = document.createElement("input");
    pcInput.id = "pc-input";
    pcInput.type = "text";
    pcInput.maxLength = 500;
    pcInput.autocomplete = "off";
    pcInput.setAttribute("aria-label", "Message the assistant");
    pcInput.placeholder = "Ask about opportunities...";
    Object.assign(pcInput.style, {
      flex: "1",
      minWidth: "0",
      padding: "10px 11px",
      border: "1px solid #292A30",
      borderRadius: "8px",
      background: "#111115",
      color: "#ECEDEF",
      font: "inherit",
      outlineOffset: "2px"
    });
    var pcSend = document.createElement("button");
    pcSend.id = "pc-send";
    pcSend.type = "submit";
    pcSend.textContent = "Send";
    Object.assign(pcSend.style, {
      padding: "0 14px",
      border: "0",
      borderRadius: "8px",
      background: "#B8243A",
      color: "#ECEDEF",
      font: "inherit",
      fontWeight: "600",
      cursor: "pointer",
      outlineOffset: "2px"
    });
    pcForm.append(pcInput, pcSend);
    pcPanel.append(pcHeader, pcMessages, pcForm);
    document.body.append(pcButton, pcPanel);

    function pcSetFocusOutline(pcElement) {
      pcElement.addEventListener("focus", function () {
        try {
          pcElement.style.outline = "2px solid #ECEDEF";
        } catch (pcError) {
        }
      });
      pcElement.addEventListener("blur", function () {
        try {
          pcElement.style.outline = "none";
        } catch (pcError) {
        }
      });
    }

    function pcAddMessage(pcText, pcRole) {
      var pcBubble = document.createElement("div");
      pcBubble.setAttribute("data-role", pcRole);
      Object.assign(pcBubble.style, {
        alignSelf: pcRole === "Student" ? "flex-end" : "flex-start",
        maxWidth: "88%",
        padding: "10px 12px",
        borderRadius: "12px",
        background: pcRole === "Student" ? "#B8243A" : "#292A30",
        color: "#ECEDEF",
        fontSize: "14px",
        lineHeight: "1.45",
        overflowWrap: "anywhere",
        whiteSpace: "pre-wrap"
      });
      var pcParts = String(pcText).split(/(https?:\/\/[^\s<>"']+)/gi);
      pcParts.forEach(function (pcPart) {
        if (/^https?:\/\//i.test(pcPart)) {
          var pcUrl = pcPart.replace(/[),.!?;:]+$/, "");
          var pcTrailing = pcPart.slice(pcUrl.length);
          try {
            var pcParsedUrl = new URL(pcUrl);
            if (pcParsedUrl.protocol === "http:" || pcParsedUrl.protocol === "https:") {
              var pcAnchor = document.createElement("a");
              pcAnchor.href = pcParsedUrl.href;
              pcAnchor.target = "_blank";
              pcAnchor.rel = "noopener noreferrer";
              pcAnchor.textContent = pcUrl;
              pcAnchor.style.color = "#ECEDEF";
              pcAnchor.style.textDecoration = "underline";
              pcBubble.appendChild(pcAnchor);
              var pcSuffix = document.createElement("span");
              pcSuffix.textContent = pcTrailing;
              pcBubble.appendChild(pcSuffix);
              return;
            }
          } catch (pcError) {
          }
        }
        var pcTextSpan = document.createElement("span");
        pcTextSpan.textContent = pcPart;
        pcBubble.appendChild(pcTextSpan);
      });
      pcMessages.appendChild(pcBubble);
      pcMessages.scrollTop = pcMessages.scrollHeight;
      return pcBubble;
    }

    function pcUpdateLayout() {
      var pcMobile = window.innerWidth < 480;
      pcPanel.style.right = pcMobile
        ? "calc(8px - (100vw - 100%))"
        : "calc(24px - (100vw - 100%))";
      pcPanel.style.width = pcMobile ? "calc(100vw - 16px)" : "360px";
      pcPanel.style.maxWidth = pcMobile ? "none" : "calc(100vw - 16px)";
      pcButton.style.right = "calc(24px - (100vw - 100%))";
    }

    function pcSetPanelOpen(pcOpen) {
      pcOpened = pcOpen;
      pcReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      pcPanel.style.transition = pcReducedMotion ? "none" : "opacity 150ms ease";
      pcButton.setAttribute("aria-expanded", String(pcOpen));
      if (pcOpen) {
        pcUpdateLayout();
        pcPanel.style.display = "flex";
        pcPanel.style.opacity = "0";
        window.requestAnimationFrame(function () {
          try {
            pcPanel.style.opacity = "1";
          } catch (pcError) {
          }
        });
        if (!pcIntroShown) {
          pcIntroShown = true;
          pcAddMessage("Hi! Ask me about scholarships, internships, fellowships or entry-level jobs.", "Assistant");
        }
        pcInput.focus();
      } else {
        pcPanel.style.opacity = "0";
        window.setTimeout(function () {
          try {
            if (!pcOpened) pcPanel.style.display = "none";
          } catch (pcError) {
          }
        }, pcReducedMotion ? 0 : 150);
        pcButton.focus();
      }
    }

    async function pcSendMessage(pcEvent) {
      pcEvent.preventDefault();
      if (pcPending) return;
      var pcMessage = pcInput.value.trim().slice(0, 500);
      if (!pcMessage) return;

      pcPending = true;
      pcInput.value = "";
      pcInput.disabled = true;
      pcSend.disabled = true;
      pcSend.style.opacity = "0.65";
      var pcPreviousHistory = pcHistory.slice(-6);
      pcHistory.push({ role: "Student", text: pcMessage });
      pcHistory = pcHistory.slice(-6);
      pcAddMessage(pcMessage, "Student");
      var pcThinking = pcAddMessage("Thinking...", "Assistant");
      var pcController = new AbortController();
      var pcTimer = window.setTimeout(function () {
        pcController.abort();
      }, 20000);

      try {
        var pcResponse = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: pcMessage, history: pcPreviousHistory }),
          signal: pcController.signal
        });
        if (!pcResponse.ok) throw new Error("Chat request failed");
        var pcData = await pcResponse.json();
        if (!pcData || typeof pcData.reply !== "string") throw new Error("Invalid chat response");
        pcThinking.remove();
        pcAddMessage(pcData.reply, "Assistant");
        pcHistory.push({ role: "Assistant", text: pcData.reply });
        pcHistory = pcHistory.slice(-6);
      } catch (pcError) {
        pcThinking.remove();
        pcAddMessage("Sorry, I couldn't reach the assistant. Please try again.", "Assistant");
      } finally {
        window.clearTimeout(pcTimer);
        pcPending = false;
        pcInput.disabled = false;
        pcSend.disabled = false;
        pcSend.style.opacity = "1";
        pcInput.focus();
      }
    }

    [pcButton, pcClose, pcInput, pcSend].forEach(pcSetFocusOutline);
    pcButton.addEventListener("click", function () {
      try {
        pcSetPanelOpen(!pcOpened);
      } catch (pcError) {
      }
    });
    pcClose.addEventListener("click", function () {
      try {
        pcSetPanelOpen(false);
      } catch (pcError) {
      }
    });
    pcForm.addEventListener("submit", function (pcEvent) {
      pcSendMessage(pcEvent).catch(function () {});
    });
    document.addEventListener("keydown", function (pcEvent) {
      try {
        if (pcEvent.key === "Escape" && pcOpened) pcSetPanelOpen(false);
      } catch (pcError) {
      }
    });
    window.addEventListener("resize", function () {
      try {
        pcUpdateLayout();
      } catch (pcError) {
      }
    });
  } catch (pcError) {
  }
})();
