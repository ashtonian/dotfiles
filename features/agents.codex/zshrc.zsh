# GPT launchers (feature agents.codex). They attach to the Codex app-server the
# com.ashtonian.codex-remote-control LaunchAgent runs, which gives every session
# the delegation policy (bin/codex-app-server). A --remote session runs in the
# app-server's directory (~) unless -C names one.

# _gpt_session MODEL EFFORT ARGS...: a session that skips approvals and the
# sandbox, so ChatGPT connector content (mail, Drive, GitHub) stays out unless
# this launch sets CODEX_CONNECTORS=1. --disable reaches the server as a
# thread setting.
_gpt_session() {
  local model=$1 effort=$2
  shift 2
  local endpoint
  endpoint=$("${DOTFILES:-$HOME/.dotfiles}/bin/codex-app-server" --print-endpoint) || return
  local -a connectors=()
  [[ ${CODEX_CONNECTORS:-0} == 1 ]] || connectors=(--disable apps)
  codex --remote "$endpoint" -C "$PWD" --model "$model" -c model_reasoning_effort="$effort" \
    "${connectors[@]}" --yolo "$@"
}

gptmore() {
  _gpt_session gpt-6.1-sol xhigh "$@"
}

gptmax() {
  _gpt_session gpt-6-astra max "$@"
}
