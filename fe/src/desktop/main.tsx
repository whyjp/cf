import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("#root not found");

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// esc 단축키 — 원본 fe/index.legacy.html line ~1786. App also wires its
// own listener to clear pickedId; this CustomEvent kept for any future
// independent panel that wants to subscribe.
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    window.dispatchEvent(new CustomEvent("camfit:close-detail"));
  }
});
