import type { Plugin } from "@opencode-ai/plugin"
import { readFile } from "node:fs/promises"
import { homedir } from "node:os"
import { join } from "node:path"

async function setting(name: string) {
  try {
    return (await readFile(join(homedir(), ".local/share/opencode/homelab", name), "utf8")).trim()
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined
    throw error
  }
}

export const Homelab: Plugin = async () => ({
  async config(config) {
    const providers = config.provider
    const provider = providers?.homelab
    if (!providers || !provider) return
    const options = provider.options ?? {}
    if (options.baseURL && options.apiKey) return

    // Keep the provider unavailable until its credentials are complete. Other
    // clients of the global config, including MCP discovery, work without it.
    delete providers.homelab
    const baseURL = await setting("base-url")
    if (!baseURL || (options.baseURL && options.baseURL !== baseURL)) return
    // The local key belongs only to the gateway named by the local base-url.
    const apiKey = options.apiKey || (await setting("litellm.key"))
    if (apiKey) providers.homelab = { ...provider, options: { ...options, baseURL, apiKey } }
  },
})
