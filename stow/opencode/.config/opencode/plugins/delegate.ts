/**
 * delegate: run Claude Code and Codex sessions as background jobs from an
 * OpenCode agent, and wake that agent's session when a job finishes.
 *
 * A job is a detached `claude -p` or `codex exec` process. Its state lives on
 * disk under $DELEGATE_STATE_DIR/jobs/<id>/, so a job outlives the OpenCode
 * server and a restarted server picks it back up:
 *
 *   job.json      the job record (worker, model, owner session, final state)
 *   prompt.md     the brief, fed to the worker on stdin
 *   events.jsonl  the worker's JSON event stream (stdout)
 *   stderr.log    the worker's stderr
 *   exit          the worker's exit code, written once it exits
 *   result.md     the worker's final message
 *   cancelled     present when delegate_cancel stopped the job
 *   notified      present once the owner session has been told it finished
 *
 * Usage, configuration and operations: README.md in the opencode stow package.
 */
import { type Plugin, type PluginInput, tool } from "@opencode-ai/plugin"
import { spawn } from "node:child_process"
import { randomBytes } from "node:crypto"
import * as fs from "node:fs"
import * as os from "node:os"
import * as path from "node:path"

type Worker = "claude" | "codex"
type Access = "read" | "write"
type State = "running" | "done" | "failed" | "cancelled" | "lost"

const EFFORTS = ["low", "medium", "high", "xhigh", "max"] as const
type Effort = (typeof EFFORTS)[number]

// Aliases and defaults mirror the interactive launchers in the zsh config:
// claudemore = opus[1m] at xhigh, claudemax = fable[1m], gptmax = gpt-6-astra at max.
const MODELS: Record<Worker, Record<string, string>> = {
  claude: { opus: "opus[1m]", fable: "fable[1m]", sonnet: "sonnet", haiku: "haiku" },
  codex: { astra: "gpt-6-astra", sol: "gpt-6.1-sol" },
}
const DEFAULTS: Record<Worker, { model: string; effort: Effort }> = {
  claude: { model: "opus", effort: "xhigh" },
  codex: { model: "astra", effort: "max" },
}
const MODEL_ALIASES = ["opus", "fable", "sonnet", "haiku", "astra", "sol"] as const

const env = process.env
const config = {
  stateDir:
    env.DELEGATE_STATE_DIR ??
    path.join(env.XDG_STATE_HOME ?? path.join(os.homedir(), ".local", "state"), "opencode-delegate"),
  claudeBin: env.DELEGATE_CLAUDE_BIN ?? "claude",
  codexBin: env.DELEGATE_CODEX_BIN ?? "codex",
  maxRunning: positiveInt(env.DELEGATE_MAX_RUNNING, 4),
  pollMs: positiveInt(env.DELEGATE_POLL_MS, 5000),
  resultChars: positiveInt(env.DELEGATE_RESULT_CHARS, 12000),
  retentionDays: positiveInt(env.DELEGATE_RETENTION_DAYS, 14),
}
const jobsDir = path.join(config.stateDir, "jobs")
const JOB_ID = /^(claude|codex)-\d{8}-\d{6}-[0-9a-f]{4}$/

// Runs the worker with the brief on stdin and records its exit code atomically,
// so a reader never sees a half-written `exit`. Worker output can carry secrets
// from the session, so everything it writes here is owner-only.
const WRAPPER = [
  "umask 077",
  '"$@" < "$DELEGATE_JOB_DIR/prompt.md" > "$DELEGATE_JOB_DIR/events.jsonl" 2> "$DELEGATE_JOB_DIR/stderr.log"',
  'printf "%s\\n" "$?" > "$DELEGATE_JOB_DIR/exit.tmp" && mv "$DELEGATE_JOB_DIR/exit.tmp" "$DELEGATE_JOB_DIR/exit"',
].join("\n")

interface Owner {
  sessionID: string
  agent: string
  directory: string
}

interface Job {
  id: string
  worker: Worker
  modelAlias: string
  model: string
  effort: Effort
  access: Access
  cwd: string
  title: string
  owner: Owner
  parent?: string
  resumeFrom?: string
  pid?: number
  startedAt: string
  // Set once the job is finalized.
  state?: State
  finishedAt?: string
  exitCode?: number
  sessionID?: string
  error?: string
  costUSD?: number
  turns?: number
}

interface Outcome {
  state: State
  exitCode?: number
  sessionID?: string
  result?: string
  error?: string
  costUSD?: number
  turns?: number
}

interface StartInput {
  worker: Worker
  modelAlias: string
  effort: Effort
  access: Access
  cwd: string
  title: string
  task: string
  parent?: string
  resumeFrom?: string
}

// ── job store ────────────────────────────────────────────────────────────────

function jobFile(id: string, name: string): string {
  return path.join(jobsDir, id, name)
}

function readJob(id: string): Job {
  // The id comes from model output and becomes a path: validate before use.
  if (!JOB_ID.test(id)) throw new Error(`"${id}" is not a job id; call delegate_status to list jobs`)
  try {
    return JSON.parse(fs.readFileSync(jobFile(id, "job.json"), "utf8"))
  } catch {
    throw new Error(`no job "${id}"; call delegate_status to list jobs`)
  }
}

function writeJob(job: Job): void {
  const tmp = jobFile(job.id, "job.json.tmp")
  fs.writeFileSync(tmp, JSON.stringify(job, null, 2), { mode: 0o600 })
  fs.renameSync(tmp, jobFile(job.id, "job.json"))
}

function listJobs(): Job[] {
  let ids: string[]
  try {
    ids = fs.readdirSync(jobsDir).filter((id) => JOB_ID.test(id))
  } catch {
    return []
  }
  const jobs = ids.flatMap((id) => {
    try {
      return [readJob(id)]
    } catch {
      return []
    }
  })
  return jobs.sort((a, b) => a.startedAt.localeCompare(b.startedAt))
}

function readText(file: string): string | undefined {
  try {
    return fs.readFileSync(file, "utf8")
  } catch {
    return undefined
  }
}

// Reads JSON lines from the head or tail of a file. Event logs of long sessions
// run to megabytes, and status only ever needs either end.
function readEvents(file: string, end: "head" | "tail", bytes: number): any[] {
  let fd: number
  try {
    fd = fs.openSync(file, "r")
  } catch {
    return []
  }
  try {
    const size = fs.fstatSync(fd).size
    const len = Math.min(size, bytes)
    const buf = Buffer.alloc(len)
    fs.readSync(fd, buf, 0, len, end === "head" ? 0 : size - len)
    const lines = buf.toString("utf8").split("\n")
    if (len < size) {
      if (end === "head") lines.pop()
      else lines.shift()
    }
    return lines.flatMap((line) => {
      if (!line.trim()) return []
      try {
        return [JSON.parse(line)]
      } catch {
        return []
      }
    })
  } finally {
    fs.closeSync(fd)
  }
}

// ── inspection ───────────────────────────────────────────────────────────────

function alive(pid: number | undefined): boolean {
  if (!pid) return false
  try {
    process.kill(pid, 0)
    return true
  } catch (err: any) {
    return err?.code === "EPERM"
  }
}

function findSessionID(job: Job): string | undefined {
  for (const e of readEvents(jobFile(job.id, "events.jsonl"), "head", 64 * 1024)) {
    if (job.worker === "claude" && typeof e.session_id === "string") return e.session_id
    if (job.worker === "codex" && e.type === "thread.started") return e.thread_id
  }
  return undefined
}

function stderrTail(job: Job): string {
  const text = readText(jobFile(job.id, "stderr.log")) ?? ""
  return text.trim().split("\n").slice(-5).join("\n")
}

function inspect(job: Job): Outcome {
  const sessionID = job.sessionID ?? findSessionID(job)
  if (fs.existsSync(jobFile(job.id, "cancelled"))) return { state: "cancelled", sessionID }
  const exit = readText(jobFile(job.id, "exit"))
  if (exit === undefined) return { state: alive(job.pid) ? "running" : "lost", sessionID }
  const exitCode = Number.parseInt(exit.trim(), 10)
  return job.worker === "claude" ? claudeOutcome(job, exitCode, sessionID) : codexOutcome(job, exitCode, sessionID)
}

function claudeOutcome(job: Job, exitCode: number, sessionID?: string): Outcome {
  const events = readEvents(jobFile(job.id, "events.jsonl"), "tail", 1 << 20)
  const result = events.reverse().find((e) => e.type === "result")
  if (!result) {
    return { state: "failed", exitCode, sessionID, error: stderrTail(job) || `claude exited ${exitCode} without a result` }
  }
  const failed = result.is_error === true || exitCode !== 0
  const text = typeof result.result === "string" ? result.result : ""
  return {
    state: failed ? "failed" : "done",
    exitCode,
    sessionID: result.session_id ?? sessionID,
    result: text,
    error: failed ? `${result.subtype ?? "error"}: ${firstLine(text) || stderrTail(job)}` : undefined,
    costUSD: result.total_cost_usd,
    turns: result.num_turns,
  }
}

function codexOutcome(job: Job, exitCode: number, sessionID?: string): Outcome {
  const events = readEvents(jobFile(job.id, "events.jsonl"), "tail", 1 << 20)
  const lastTurn = [...events].reverse().find((e) => e.type === "turn.completed" || e.type === "turn.failed")
  const lastError = [...events].reverse().find((e) => e.type === "error")
  const failed = exitCode !== 0 || lastTurn?.type !== "turn.completed"
  const error =
    lastTurn?.error?.message ?? lastError?.message ?? (stderrTail(job) || `codex exited ${exitCode} without completing a turn`)
  return {
    state: failed ? "failed" : "done",
    exitCode,
    sessionID,
    result: readText(jobFile(job.id, "result.md")) ?? "",
    error: failed ? error : undefined,
  }
}

function activity(job: Job, limit: number): string[] {
  const lines: string[] = []
  for (const e of readEvents(jobFile(job.id, "events.jsonl"), "tail", 256 * 1024)) {
    if (job.worker === "claude" && e.type === "assistant") {
      for (const c of e.message?.content ?? []) {
        if (c.type === "tool_use") lines.push(`${c.name} ${summarizeInput(c.input)}`)
        else if (c.type === "text" && c.text?.trim()) lines.push(`says: ${c.text}`)
      }
    } else if (job.worker === "codex" && e.type === "item.completed") {
      const item = e.item ?? {}
      if (item.type === "command_execution") lines.push(`ran: ${item.command} (exit ${item.exit_code ?? "?"})`)
      else if (item.type === "file_change") lines.push(`edited: ${(item.changes ?? []).map((c: any) => c.path).join(", ")}`)
      else if (item.type === "mcp_tool_call") lines.push(`mcp: ${item.server}/${item.tool}`)
      else if (item.type === "web_search") lines.push(`searched: ${item.query}`)
      else if (item.type === "agent_message" && item.text?.trim()) lines.push(`says: ${item.text}`)
    }
  }
  return lines.slice(-limit).map((line) => clip(oneLine(line), 200))
}

function summarizeInput(input: any): string {
  if (!input || typeof input !== "object") return ""
  const v = input.command ?? input.file_path ?? input.path ?? input.pattern ?? input.url ?? input.query ?? input.description
  return typeof v === "string" ? v : JSON.stringify(input)
}

// ── lifecycle ────────────────────────────────────────────────────────────────

function command(job: Job): string[] {
  const dir = path.join(jobsDir, job.id)
  if (job.worker === "claude") {
    const args = [config.claudeBin, "-p", "--output-format", "stream-json", "--verbose"]
    args.push("--model", job.model, "--effort", job.effort, "--name", `delegate ${job.id}`)
    if (job.access === "write") {
      args.push("--dangerously-skip-permissions", "--permission-mode", "bypassPermissions", "--disallowedTools", "Agent")
    } else {
      // Restrict available tools and settings so inherited Bash/MCP permissions cannot grant writes.
      args.push(
        "--restricted", "--tools", "Read,Glob,Grep", "--allowedTools", "Read,Glob,Grep",
        "--permission-mode", "dontAsk", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
      )
    }
    if (job.resumeFrom) args.push("--resume", job.resumeFrom)
    return args
  }
  // `codex exec resume` takes neither -s nor -C, so the sandbox is set through
  // config for both forms and the working directory through the process cwd.
  const sandbox =
    job.access === "write"
      ? ["-c", 'sandbox_mode="workspace-write"', "-c", "sandbox_workspace_write.network_access=true"]
      : ["-c", 'sandbox_mode="read-only"']
  const common = [
    "--json",
    "-o",
    path.join(dir, "result.md"),
    "-m",
    job.model,
    "-c",
    `model_reasoning_effort="${job.effort}"`,
    "--skip-git-repo-check",
    ...sandbox,
  ]
  if (job.resumeFrom) return [config.codexBin, "exec", "resume", ...common, job.resumeFrom, "-"]
  return [config.codexBin, "exec", ...common, "-"]
}

function workerEnv(job: Job): NodeJS.ProcessEnv {
  const e: NodeJS.ProcessEnv = { ...process.env, DELEGATE_JOB_DIR: path.join(jobsDir, job.id), DELEGATE_JOB_ID: job.id }
  // A worker started from a server that was itself launched inside a Claude
  // session must not be treated as a nested session.
  delete e.CLAUDECODE
  // Workers run with bypassed permissions; they get no credential for the
  // coordinator's own server.
  delete e.OPENCODE_SERVER_PASSWORD
  delete e.OPENCODE_SERVER_USERNAME
  // Same policy as the wg-* fleet sessions: keep claude.ai connector content
  // (mail, Drive) out of agents that run unattended.
  if (job.worker === "claude") e.ENABLE_CLAUDEAI_MCP_SERVERS = "false"
  return e
}

function runningJobs(): Job[] {
  return listJobs().filter((job) => !job.state && inspect(job).state === "running")
}

function resolveCwd(cwd: string): string {
  if (!path.isAbsolute(cwd)) throw new Error(`cwd must be an absolute path, got "${cwd}"`)
  let real: string
  try {
    real = fs.realpathSync(cwd)
  } catch {
    throw new Error(`cwd "${cwd}" does not exist`)
  }
  if (!fs.statSync(real).isDirectory()) throw new Error(`cwd "${cwd}" is not a directory`)
  return real
}

function startJob(input: StartInput, owner: Owner): Job {
  const running = runningJobs()
  if (running.length >= config.maxRunning) {
    throw new Error(
      `${running.length} jobs are already running (limit ${config.maxRunning}): ${running.map((j) => j.id).join(", ")}. ` +
        "Wait for a [delegate] notice or cancel one.",
    )
  }
  const now = new Date()
  const stamp = now.toISOString().replace(/[-:]/g, "").replace("T", "-").slice(0, 15)
  const job: Job = {
    id: `${input.worker}-${stamp}-${randomBytes(2).toString("hex")}`,
    worker: input.worker,
    modelAlias: input.modelAlias,
    model: MODELS[input.worker][input.modelAlias],
    effort: input.effort,
    access: input.access,
    cwd: input.cwd,
    title: input.title,
    owner,
    parent: input.parent,
    resumeFrom: input.resumeFrom,
    startedAt: now.toISOString(),
  }
  const dir = path.join(jobsDir, job.id)
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 })
  fs.writeFileSync(jobFile(job.id, "prompt.md"), input.task, { mode: 0o600 })
  writeJob(job)

  const child = spawn("/bin/sh", ["-c", WRAPPER, "delegate-job", ...command(job)], {
    cwd: job.cwd,
    detached: true,
    stdio: "ignore",
    env: workerEnv(job),
  })
  if (!child.pid) throw new Error(`could not start the ${job.worker} worker for job ${job.id}`)
  child.unref()
  job.pid = child.pid
  writeJob(job)
  return job
}

function finalize(job: Job, outcome: Outcome): void {
  job.state = outcome.state
  job.finishedAt = new Date().toISOString()
  job.exitCode = outcome.exitCode
  job.sessionID = outcome.sessionID ?? job.sessionID
  job.error = outcome.error
  job.costUSD = outcome.costUSD
  job.turns = outcome.turns
  if (job.worker === "claude" && outcome.result !== undefined) {
    fs.writeFileSync(jobFile(job.id, "result.md"), outcome.result, { mode: 0o600 })
  }
  writeJob(job)
}

function cancelJob(job: Job): void {
  fs.writeFileSync(jobFile(job.id, "cancelled"), new Date().toISOString(), { mode: 0o600 })
  // The wrapper was spawned detached, so it leads its own process group and
  // the signal reaches the worker and everything the worker started.
  const pid = job.pid
  if (!pid) return
  signalGroup(pid, "SIGTERM")
  setTimeout(() => signalGroup(pid, "SIGKILL"), 10_000).unref()
}

function signalGroup(pid: number, signal: NodeJS.Signals): void {
  try {
    process.kill(-pid, signal)
  } catch {
    // Already gone.
  }
}

function pruneOldJobs(): void {
  const cutoff = Date.now() - config.retentionDays * 86_400_000
  for (const job of listJobs()) {
    if (job.finishedAt && Date.parse(job.finishedAt) < cutoff) {
      fs.rmSync(path.join(jobsDir, job.id), { recursive: true, force: true })
    }
  }
}

// ── completion notices ───────────────────────────────────────────────────────

// One sweeper per server process. The plugin is instantiated once per project
// instance, so the module-level state keeps a single timer, and the exclusive
// `notified` file keeps any overlap from sending a notice twice.
let client: PluginInput["client"] | undefined
let sweeper: ReturnType<typeof setInterval> | undefined
let sweeping = false

async function sweep(): Promise<void> {
  if (sweeping || !client) return
  sweeping = true
  try {
    for (const job of listJobs()) {
      if (!job.state) {
        const outcome = inspect(job)
        if (outcome.state === "running") continue
        finalize(job, outcome)
      }
      if (job.state !== "cancelled") await notifyOnce(job)
    }
  } finally {
    sweeping = false
  }
}

async function notifyOnce(job: Job): Promise<void> {
  const marker = jobFile(job.id, "notified")
  try {
    fs.closeSync(fs.openSync(marker, "wx"))
  } catch {
    return
  }
  const res = await client!.session.promptAsync({
    path: { id: job.owner.sessionID },
    query: { directory: job.owner.directory },
    body: { agent: job.owner.agent, parts: [{ type: "text", text: notice(job) }] },
  })
  if (!res.error) return
  const status = res.response?.status
  if (status === 404) {
    await log("warn", `owner session ${job.owner.sessionID} of job ${job.id} no longer exists; notice dropped`)
    return
  }
  // Release the claim so the next sweep retries.
  fs.rmSync(marker, { force: true })
  await log("warn", `could not notify session ${job.owner.sessionID} about job ${job.id} (HTTP ${status ?? "?"})`)
}

function notice(job: Job): string {
  const lines = [
    `[delegate] Job ${job.id} finished: ${job.state}. ${job.worker}/${job.modelAlias}, ${job.access} access, "${job.title}".`,
  ]
  if (job.error) lines.push(`Error: ${clip(job.error, 500)}`)
  lines.push(
    "This is an automated notice, not a message from the user.",
    `Call delegate_result with job "${job.id}" to read the outcome before reporting it or planning the next step.`,
  )
  return lines.join("\n")
}

async function log(level: "info" | "warn" | "error", message: string): Promise<void> {
  try {
    await client?.app.log({ body: { service: "delegate", level, message } })
  } catch {
    // Logging must never break a tool call or the sweeper.
  }
}

// ── formatting ───────────────────────────────────────────────────────────────

function positiveInt(value: string | undefined, fallback: number): number {
  const n = Number.parseInt(value ?? "", 10)
  return Number.isFinite(n) && n > 0 ? n : fallback
}

function oneLine(s: string): string {
  return s.replace(/\s+/g, " ").trim()
}

function firstLine(s: string): string {
  return oneLine(s.split("\n").find((l) => l.trim()) ?? "")
}

function clip(s: string, max: number): string {
  return s.length <= max ? s : `${s.slice(0, max - 1)}…`
}

function elapsed(job: Job): string {
  const end = job.finishedAt ? Date.parse(job.finishedAt) : Date.now()
  const secs = Math.max(0, Math.round((end - Date.parse(job.startedAt)) / 1000))
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  return h ? `${h}h${m}m` : m ? `${m}m${s}s` : `${s}s`
}

function summaryLine(job: Job, state: State): string {
  return `${job.id}  ${state.padEnd(9)}  ${job.worker}/${job.modelAlias}  ${job.access}  ${elapsed(job).padStart(6)}  "${job.title}"  ${job.cwd}`
}

function takeoverHint(job: Job, sessionID: string): string {
  return job.worker === "claude"
    ? `cd ${JSON.stringify(job.cwd)} && claude --resume ${sessionID} --remote-control`
    : `cd ${JSON.stringify(job.cwd)} && codex resume ${sessionID}`
}

// ── tools ────────────────────────────────────────────────────────────────────

function ownerOf(context: { sessionID: string; agent: string; directory: string }): Owner {
  return { sessionID: context.sessionID, agent: context.agent, directory: context.directory }
}

// Write access hands an unattended agent the repo, so each directory needs one
// explicit approval; read jobs start without asking.
async function approveWrite(context: any, job: { worker: Worker; modelAlias: string; cwd: string; title: string }) {
  await context.ask({
    permission: "delegate_write",
    patterns: [job.cwd],
    always: [job.cwd],
    metadata: { worker: job.worker, model: job.modelAlias, cwd: job.cwd, title: job.title },
  })
}

export const DelegatePlugin: Plugin = async (input) => {
  client = input.client
  fs.mkdirSync(jobsDir, { recursive: true, mode: 0o700 })
  if (!sweeper) {
    pruneOldJobs()
    sweeper = setInterval(() => {
      sweep().catch((err) => log("error", `sweep failed: ${err}`))
    }, config.pollMs)
    sweeper.unref?.()
  }

  return {
    tool: {
      delegate_start: tool({
        description:
          "Start a Claude Code or Codex (GPT Astra) session as a background job and return its id immediately. " +
          "When the job finishes you receive a [delegate] message; do not poll for it.",
        args: {
          worker: tool.schema
            .enum(["claude", "codex"])
            .describe(
              "claude: Claude Code, for implementation, debugging and infrastructure work. " +
                "codex: Codex running GPT Astra, for independent review, audits and second opinions.",
            ),
          title: tool.schema.string().min(1).describe("Short label for the job list, e.g. 'review auth refactor'."),
          task: tool.schema
            .string()
            .min(1)
            .describe(
              "Complete, self-contained brief. The worker sees nothing of this conversation: state the goal, " +
                "relevant paths, constraints, acceptance criteria, and exactly what to report back.",
            ),
          cwd: tool.schema
            .string()
            .optional()
            .describe("Absolute path of the directory (usually a repository) the worker runs in. Defaults to this session's directory."),
          access: tool.schema
            .enum(["read", "write"])
            .optional()
            .describe("read (default): the worker cannot change files. write: it may edit files and run commands."),
          model: tool.schema
            .enum(MODEL_ALIASES)
            .optional()
            .describe("claude: opus (default), fable (hardest problems), sonnet, haiku. codex: astra (default), sol."),
          effort: tool.schema
            .enum(EFFORTS)
            .optional()
            .describe("Reasoning effort. Defaults: claude xhigh, codex max."),
        },
        async execute(args, context) {
          const worker = args.worker as Worker
          const modelAlias = args.model ?? DEFAULTS[worker].model
          if (!MODELS[worker][modelAlias]) {
            throw new Error(`model "${modelAlias}" is not a ${worker} model; use one of: ${Object.keys(MODELS[worker]).join(", ")}`)
          }
          const access = (args.access ?? "read") as Access
          const cwd = resolveCwd(args.cwd ?? context.directory)
          if (access === "write") await approveWrite(context, { worker, modelAlias, cwd, title: args.title })
          const job = startJob(
            { worker, modelAlias, effort: (args.effort ?? DEFAULTS[worker].effort) as Effort, access, cwd, title: args.title, task: args.task },
            ownerOf(context),
          )
          await log("info", `started ${job.id} (${job.worker}/${job.model}, ${job.access}) in ${job.cwd}`)
          return {
            title: `${job.worker}/${job.modelAlias}: ${job.title}`,
            metadata: { job: job.id },
            output:
              `Started job ${job.id}: ${job.worker}/${job.modelAlias} (${job.model}, effort ${job.effort}), ${job.access} access, in ${job.cwd}.\n` +
              "It runs in the background. Tell the user what is running and end your turn; a [delegate] message arrives when it finishes.",
          }
        },
      }),

      delegate_status: tool({
        description: "List recent delegated jobs, or show one job's state and latest activity.",
        args: {
          job: tool.schema.string().optional().describe("Job id. Omit to list recent jobs."),
        },
        async execute(args) {
          if (!args.job) {
            const jobs = listJobs().slice(-15)
            if (!jobs.length) return "No delegated jobs yet."
            return jobs.map((job) => summaryLine(job, job.state ?? inspect(job).state)).join("\n")
          }
          const job = readJob(args.job)
          const outcome = job.state ? { ...job, state: job.state } : inspect(job)
          const lines = [summaryLine(job, outcome.state)]
          if (outcome.sessionID) lines.push(`Worker session: ${outcome.sessionID}`)
          if (job.parent) lines.push(`Continues job ${job.parent}`)
          if (outcome.error) lines.push(`Error: ${outcome.error}`)
          const recent = activity(job, 8)
          lines.push(recent.length ? `Latest activity:\n  ${recent.join("\n  ")}` : "No activity recorded yet.")
          return lines.join("\n")
        },
      }),

      delegate_result: tool({
        description: "Read a finished job's outcome and the worker's final message.",
        args: {
          job: tool.schema.string().describe("Job id."),
        },
        async execute(args) {
          const job = readJob(args.job)
          const outcome = inspect(job)
          if (outcome.state === "running") {
            return `Job ${job.id} is still running (${elapsed(job)}). A [delegate] message arrives when it finishes.`
          }
          if (!job.state) finalize(job, outcome)
          const stats = [
            `exit ${outcome.exitCode ?? "-"}`,
            elapsed(job),
            outcome.turns !== undefined ? `${outcome.turns} turns` : undefined,
            outcome.costUSD !== undefined ? `$${outcome.costUSD.toFixed(2)}` : undefined,
          ].filter(Boolean)
          const lines = [
            `Job ${job.id}: ${outcome.state} (${stats.join(", ")}). ${job.worker}/${job.modelAlias}, ${job.access} access.`,
            `Title: ${job.title}`,
            `Directory: ${job.cwd}`,
          ]
          if (outcome.sessionID) {
            lines.push(`Worker session: ${outcome.sessionID}. Follow up with delegate_reply; the user can take over with: ${takeoverHint(job, outcome.sessionID)}`)
          }
          if (outcome.error) lines.push(`Error: ${outcome.error}`)
          const text = outcome.result ?? ""
          lines.push("--- final message ---")
          lines.push(text.trim() ? clip(text, config.resultChars) : "(the worker produced no final message)")
          if (text.length > config.resultChars) {
            lines.push(`[truncated to ${config.resultChars} of ${text.length} characters; full text: ${jobFile(job.id, "result.md")}]`)
          }
          return lines.join("\n")
        },
      }),

      delegate_reply: tool({
        description:
          "Send a follow-up to a finished job's worker, continuing its session with its full context. Starts a new background job.",
        args: {
          job: tool.schema.string().describe("Id of the finished job to continue."),
          message: tool.schema.string().min(1).describe("The follow-up instruction or answer."),
          access: tool.schema.enum(["read", "write"]).optional().describe("Defaults to the previous job's access."),
          effort: tool.schema.enum(EFFORTS).optional().describe("Defaults to the previous job's effort."),
        },
        async execute(args, context) {
          const prev = readJob(args.job)
          const outcome = inspect(prev)
          if (outcome.state === "running") throw new Error(`job ${prev.id} is still running; wait for its [delegate] notice`)
          const resumeFrom = prev.sessionID ?? outcome.sessionID
          if (!resumeFrom) throw new Error(`job ${prev.id} recorded no worker session to continue; start a new job instead`)
          const access = (args.access ?? prev.access) as Access
          if (access === "write") await approveWrite(context, prev)
          const job = startJob(
            {
              worker: prev.worker,
              modelAlias: prev.modelAlias,
              effort: (args.effort ?? prev.effort) as Effort,
              access,
              cwd: prev.cwd,
              title: prev.title.endsWith("(follow-up)") ? prev.title : `${prev.title} (follow-up)`,
              task: args.message,
              parent: prev.id,
              resumeFrom,
            },
            ownerOf(context),
          )
          await log("info", `started ${job.id} continuing ${prev.id}`)
          return {
            title: `${job.worker}/${job.modelAlias}: ${job.title}`,
            metadata: { job: job.id },
            output: `Started job ${job.id}, continuing ${prev.id}'s ${prev.worker} session. A [delegate] message arrives when it finishes.`,
          }
        },
      }),

      delegate_cancel: tool({
        description: "Stop a running job.",
        args: {
          job: tool.schema.string().describe("Job id."),
        },
        async execute(args) {
          const job = readJob(args.job)
          const outcome = inspect(job)
          if (outcome.state !== "running") return `Job ${job.id} is not running (${outcome.state}).`
          cancelJob(job)
          finalize(job, { ...outcome, state: "cancelled" })
          await log("info", `cancelled ${job.id}`)
          return `Cancelled job ${job.id}.`
        },
      }),
    },
  }
}
