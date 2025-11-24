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
const { execSync } = require("child_process");

const PORT = Number(process.env.PROGRESS_SYNC_PORT || 3323);
const REPO_ROOT = path.resolve(__dirname, "..");
const OUTPUT_FILE = path.join(REPO_ROOT, "data", "progress.json");
const COMMIT_MESSAGE = 'AUTOSAVE: Progress update via tracker.';

function writeSnapshot(payload) {
  fs.mkdirSync(path.dirname(OUTPUT_FILE), { recursive: true });
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(payload, null, 2));
}

function hasChanges() {
  try {
    const status = execSync("git status --porcelain data/progress.json", {
      cwd: REPO_ROOT,
    })
      .toString()
      .trim();
    return status.length > 0;
  } catch (err) {
    console.error("Could not inspect git status", err);
    return false;
  }
}

function gitCommitAndPush() {
  if (!hasChanges()) {
    return;
  }

  execSync("git add data/progress.json", {
    cwd: REPO_ROOT,
    stdio: "inherit",
  });
  execSync(`git commit -m "${COMMIT_MESSAGE}"`, {
    cwd: REPO_ROOT,
    stdio: "inherit",
  });
  const branch = execSync("git rev-parse --abbrev-ref HEAD", {
    cwd: REPO_ROOT,
  })
    .toString()
    .trim();
  execSync(`git push origin ${branch}`, {
    cwd: REPO_ROOT,
    stdio: "inherit",
  });
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
  try {
    gitCommitAndPush();
  } catch (err) {
    console.error("Git autosave failed", err);
  }
}

const server = http.createServer((req, res) => {
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
