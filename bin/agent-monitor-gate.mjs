// agent-monitor-gate: the agent dashboard's only LAN listener.
//
// The dashboard stays on loopback, where its hooks and Run page need no
// credentials. This gate accepts LAN requests that carry the shared bearer token
// (sent by the cluster proxy behind the internal ingress), refuses the hook
// routes, and forwards everything else, WebSockets included, to loopback.
// Run by `agent-monitor gate`; configuration comes from the environment.

import { createHash, timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import http from "node:http";
import net from "node:net";

const listenHost = process.env.GATE_LISTEN_HOST || "0.0.0.0";
const listenPort = Number(process.env.GATE_PORT || 4821);
const upstreamPort = Number(process.env.GATE_UPSTREAM_PORT || 4820);
const upstreamHost = "127.0.0.1";
// The dashboard's Host allowlist accepts loopback names, so forwarded requests
// present themselves as local.
const upstreamHostHeader = `${upstreamHost}:${upstreamPort}`;

// Headers that describe one hop and must not be forwarded as-is.
const HOP_BY_HOP = new Set([
  "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailer", "transfer-encoding", "upgrade",
]);

function fail(message) {
  console.error(`agent-monitor-gate: ${message}`);
  process.exit(78); // EX_CONFIG
}

function readToken() {
  const file = process.env.GATE_TOKEN_FILE;
  if (!file) fail("GATE_TOKEN_FILE is not set");
  let token;
  try {
    token = readFileSync(file, "utf8").trim();
  } catch (error) {
    fail(`cannot read ${file}: ${error.message}`);
  }
  if (token.length < 32) fail(`${file} holds fewer than 32 characters`);
  return token;
}

const expectedDigest = createHash("sha256").update(readToken()).digest();

// Comparing digests keeps the comparison constant-time for any input length.
function authorized(headers) {
  const value = headers.authorization || "";
  if (!value.startsWith("Bearer ")) return false;
  const digest = createHash("sha256").update(value.slice(7)).digest();
  return timingSafeEqual(digest, expectedDigest);
}

// Hooks only ever arrive from the Mac's own loopback.
function isHookRoute(url) {
  const path = (url || "").split("?")[0];
  return path === "/api/hooks" || path.startsWith("/api/hooks/");
}

function forwardedHeaders(req) {
  const headers = {};
  for (const [name, value] of Object.entries(req.headers)) {
    if (!HOP_BY_HOP.has(name) && name !== "authorization" && name !== "host") headers[name] = value;
  }
  headers.host = upstreamHostHeader;
  headers["x-forwarded-for"] = [req.headers["x-forwarded-for"], req.socket.remoteAddress].filter(Boolean).join(", ");
  headers["x-forwarded-host"] = req.headers["x-forwarded-host"] || req.headers.host || "";
  return headers;
}

function deny(req, status) {
  console.error(`agent-monitor-gate: ${status} ${req.method} ${req.url} from ${req.socket.remoteAddress}`);
}

const server = http.createServer((req, res) => {
  if (!authorized(req.headers)) {
    deny(req, 401);
    res.writeHead(401, { "content-type": "text/plain" }).end("unauthorized\n");
    return;
  }
  if (isHookRoute(req.url)) {
    deny(req, 404);
    res.writeHead(404, { "content-type": "text/plain" }).end("not found\n");
    return;
  }
  const upstream = http.request(
    { host: upstreamHost, port: upstreamPort, method: req.method, path: req.url, headers: forwardedHeaders(req) },
    (response) => {
      res.writeHead(response.statusCode, response.headers);
      response.pipe(res);
    },
  );
  // Bounds only the connection, not the response: exports and streams run long.
  // A reused keep-alive socket is already connected and never emits "connect".
  const connectTimer = setTimeout(() => upstream.destroy(new Error("upstream connect timeout")), 10_000);
  upstream.on("socket", (socket) => {
    if (socket.connecting) socket.once("connect", () => clearTimeout(connectTimer));
    else clearTimeout(connectTimer);
  });
  upstream.on("close", () => clearTimeout(connectTimer));
  upstream.on("error", (error) => {
    if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" }).end("dashboard unavailable\n");
    else res.destroy(error);
  });
  req.pipe(upstream);
});

// WebSocket upgrades are relayed as raw byte streams after the same checks.
server.on("upgrade", (req, client, head) => {
  const status = !authorized(req.headers) ? 401 : isHookRoute(req.url) ? 404 : 0;
  if (status) {
    deny(req, status);
    const reason = status === 401 ? "Unauthorized" : "Not Found";
    client.end(`HTTP/1.1 ${status} ${reason}\r\nConnection: close\r\n\r\n`);
    return;
  }
  const upstream = net.connect(upstreamPort, upstreamHost, () => {
    const headers = forwardedHeaders(req);
    headers.connection = "Upgrade";
    headers.upgrade = req.headers.upgrade;
    const lines = [`${req.method} ${req.url} HTTP/1.1`];
    for (const [name, value] of Object.entries(headers)) {
      for (const item of Array.isArray(value) ? value : [value]) lines.push(`${name}: ${item}`);
    }
    upstream.write(`${lines.join("\r\n")}\r\n\r\n`);
    if (head.length) upstream.write(head);
    upstream.pipe(client);
    client.pipe(upstream);
  });
  const close = () => {
    upstream.destroy();
    client.destroy();
  };
  upstream.on("error", close);
  client.on("error", close);
});

server.listen(listenPort, listenHost, () => {
  console.log(`agent-monitor-gate: listening on ${listenHost}:${listenPort}, forwarding to ${upstreamHostHeader}`);
});

function shutdown() {
  server.close(() => process.exit(0));
  server.closeAllConnections();
  setTimeout(() => process.exit(0), 5_000).unref();
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
