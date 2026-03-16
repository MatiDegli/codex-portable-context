#!/usr/bin/env bash
# Shared helpers for Bash compatibility wrappers that delegate to the Python CLIs.

set -euo pipefail

codex_repo_root() {
  local script_dir

  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  cd -- "${script_dir}/.." && pwd
}

codex_find_python() {
  local repo_root

  repo_root="$(codex_repo_root)"
  if [[ -x "${repo_root}/.venv/bin/python" ]]; then
    printf '%s\n' "${repo_root}/.venv/bin/python"
    return 0
  fi

  if command -v python3.13 >/dev/null 2>&1; then
    printf 'python3.13\n'
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    printf 'python3\n'
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    printf 'python\n'
    return 0
  fi

  printf 'Python is now the primary implementation path, but no usable interpreter was found.\n' >&2
  printf 'Run ./scripts/bootstrap-python-v2 or invoke the Python CLI directly once Python is available.\n' >&2
  exit 1
}

codex_exec_python_cli() {
  local module="$1"
  shift

  local repo_root
  local python_bin
  local pythonpath

  repo_root="$(codex_repo_root)"
  python_bin="$(codex_find_python)"
  pythonpath="${repo_root}/src"
  if [[ -n "${PYTHONPATH:-}" ]]; then
    pythonpath="${pythonpath}:${PYTHONPATH}"
  fi

  if ! PYTHONPATH="${pythonpath}" "${python_bin}" -c 'import codex_portable_context' >/dev/null 2>&1; then
    printf 'Python is now the primary implementation path, but the project module is not available.\n' >&2
    printf 'Run ./scripts/bootstrap-python-v2 or use an environment where codex_portable_context can be imported.\n' >&2
    exit 1
  fi

  exec env PYTHONPATH="${pythonpath}" "${python_bin}" -m "${module}" "$@"
}
