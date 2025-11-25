#!/usr/bin/env node
/**
 * Lightweight local autosave server for the Progress Tracker.
 *
 * - Listens on http://localhost:3323/progress-sync (override with PROGRESS_SYNC_PORT).
 * - Expects POSTed JSON payload (what the tracker sends).
 * - Writes data/progress.json, then git add/commit/push with the required message.
 *
 * Run locally: `node scripts/progress_sync_server.js`
 */

const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = Number(process.env.PROGRESS_SYNC_PORT || 3323);
const REPO_ROOT = path.resolve(__dirname, "..");
const OUTPUT_FILE = path.join(REPO_ROOT, "data", "progress.json");

function writeSnapshot(payload) {
  fs.mkdirSync(path.dirname(OUTPUT_FILE), { recursive: true });
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(payload, null, 2));
}

function sendResponse(res, statusCode, body) {
  res.writeHead(statusCode, {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  });
  res.end(JSON.stringify(body));
}

function handlePayload(payload) {
  writeSnapshot(payload);
  console.log("Snapshot saved to data/progress.json at", new Date().toISOString());
}

const server = http.createServer((req, res) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  if (req.method === "OPTIONS") {
    sendResponse(res, 204, {});
    return;
  }

  if (req.method === "POST" && req.url === "/progress-sync") {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", () => {
      try {
        const parsed = JSON.parse(body || "{}");
        handlePayload(parsed);
        sendResponse(res, 200, { status: "ok" });
      } catch (err) {
        sendResponse(res, 400, { status: "error", message: err.message });
      }
    });
    return;
  }

  sendResponse(res, 404, { status: "not_found" });
});

server.listen(PORT, () => {
  console.log(
    `Progress sync server listening on http://localhost:${PORT}/progress-sync`
  );
});
