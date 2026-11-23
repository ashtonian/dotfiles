# GPT launchers (feature agents.codex). They attach to the Codex app-server the
# com.ashtonian.codex-remote-control LaunchAgent runs. A --remote session runs
# in the app-server's directory (~) unless -C names one.
gptmore() {
  codex --remote unix:// -C "$PWD" --model gpt-6.1-sol -c model_reasoning_effort=xhigh --yolo "$@"
}

gptmax() {
  codex --remote unix:// -C "$PWD" --model gpt-6-astra -c model_reasoning_effort=max --yolo "$@"
}
