#!/usr/bin/env bash
# Shared helpers for read-only Codex mirror lookup tools.

mirror_require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  fi
}

mirror_repo_root() {
  local script_dir

  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  cd -- "${script_dir}/.." && pwd
}

mirror_default_out_dir() {
  local repo_root
  local repo_out
  local cwd_out

  repo_root="$(mirror_repo_root)"
  repo_out="${repo_root}/out"
  cwd_out="${PWD}/out"

  if [[ -d "${repo_out}" ]]; then
    printf '%s\n' "${repo_out}"
  elif [[ -d "${cwd_out}" ]]; then
    printf '%s\n' "${cwd_out}"
  else
    printf '%s\n' "${repo_out}"
  fi
}

mirror_index_path() {
  local out_dir="$1"

  printf '%s\n' "${out_dir}/sessions-index.jsonl"
}

mirror_landing_path() {
  local out_dir="$1"

  printf '%s\n' "${out_dir}/README.md"
}

mirror_require_landing() {
  local out_dir="$1"
  local landing_path

  landing_path="$(mirror_landing_path "${out_dir}")"
  if [[ ! -f "${landing_path}" ]]; then
    printf 'Mirror landing not found: %s\n' "${landing_path}" >&2
    printf 'Run scripts/codex-session-mirror first, or pass --out-dir.\n' >&2
    exit 1
  fi

  printf '%s\n' "${landing_path}"
}

mirror_require_index() {
  local out_dir="$1"
  local index_path

  index_path="$(mirror_index_path "${out_dir}")"
  if [[ ! -f "${index_path}" ]]; then
    printf 'Mirror index not found: %s\n' "${index_path}" >&2
    printf 'Run scripts/codex-session-mirror first, or pass --out-dir.\n' >&2
    exit 1
  fi
  if [[ ! -s "${index_path}" ]]; then
    printf 'Mirror index is empty: %s\n' "${index_path}" >&2
    exit 1
  fi

  printf '%s\n' "${index_path}"
}

mirror_pretty_timestamp() {
  local value="${1:-}"

  if [[ -z "${value}" || "${value}" == "null" ]]; then
    printf 'unknown\n'
    return 0
  fi

  value="${value/T/ }"
  value="${value/Z/}"
  value="${value%%.*}"
  printf '%s\n' "${value}"
}

mirror_truncate() {
  local value="$1"
  local max_length="$2"

  if [[ "${#value}" -le "${max_length}" ]]; then
    printf '%s\n' "${value}"
  else
    printf '%s...\n' "${value:0:$((max_length - 3))}"
  fi
}

mirror_print_labeled_line() {
  local label="$1"
  local value="$2"
  local width="${3:-110}"
  local prefix="  ${label}: "
  local indent
  local available_width
  local first_line="true"
  local wrapped_line

  indent="$(printf '%*s' "${#prefix}" '')"
  available_width=$((width - ${#prefix}))
  if ((available_width < 20)); then
    available_width=20
  fi

  if command -v fold >/dev/null 2>&1; then
    while IFS= read -r wrapped_line; do
      if [[ "${first_line}" == "true" ]]; then
        printf '%s%s\n' "${prefix}" "${wrapped_line}"
        first_line="false"
      else
        printf '%s%s\n' "${indent}" "${wrapped_line}"
      fi
    done < <(printf '%s\n' "${value}" | fold -s -w "${available_width}")
    return 0
  fi

  printf '%s%s\n' "${prefix}" "${value}"
}

mirror_entry_title() {
  local entry_json="$1"

  jq -r '.title // ("Session " + .session_id)' <<< "${entry_json}"
}

mirror_entry_path() {
  local out_dir="$1"
  local kind="$2"
  local entry_json="$3"
  local relpath

  case "${kind}" in
    markdown)
      relpath="$(jq -r '.markdown_relpath // ("sessions/" + .session_id + ".md")' <<< "${entry_json}")"
      ;;
    metadata)
      relpath="$(jq -r '.metadata_relpath // ("metadata/" + .session_id + ".json")' <<< "${entry_json}")"
      ;;
    *)
      printf 'Unknown mirror entry kind: %s\n' "${kind}" >&2
      exit 1
      ;;
  esac

  printf '%s\n' "${out_dir}/${relpath}"
}

mirror_latest_entry() {
  local index_path="$1"

  jq -sc '
    sort_by(.updated_at // .session_timestamp // .exported_at // "", .session_id)
    | reverse
    | .[0]
  ' "${index_path}"
}

mirror_resolve_unique_entry() {
  local index_path="$1"
  local selector="$2"
  local exact_matches
  local prefix_matches
  local exact_count
  local prefix_count

  exact_matches="$(jq -sc --arg selector "${selector}" 'map(select(.session_id == $selector))' "${index_path}")"
  exact_count="$(jq 'length' <<< "${exact_matches}")"
  if [[ "${exact_count}" -eq 1 ]]; then
    jq '.[0]' <<< "${exact_matches}"
    return 0
  fi

  prefix_matches="$(jq -sc --arg selector "${selector}" 'map(select(.session_id | startswith($selector)))' "${index_path}")"
  prefix_count="$(jq 'length' <<< "${prefix_matches}")"
  if [[ "${prefix_count}" -eq 1 ]]; then
    jq '.[0]' <<< "${prefix_matches}"
    return 0
  fi

  if [[ "${prefix_count}" -eq 0 ]]; then
    printf 'No exported session matched selector: %s\n' "${selector}" >&2
    exit 1
  fi

  printf 'Ambiguous session selector: %s\n' "${selector}" >&2
  jq -r '.[] | "- " + .session_id + "  " + (.title // ("Session " + .session_id))' <<< "${prefix_matches}" >&2
  exit 1
}

mirror_open_file() {
  local target_path="$1"
  local editor_value=""
  local -a editor_cmd=()

  if [[ -n "${VISUAL:-}" ]]; then
    editor_value="${VISUAL}"
  elif [[ -n "${EDITOR:-}" ]]; then
    editor_value="${EDITOR}"
  fi

  if [[ -n "${editor_value}" ]]; then
    read -r -a editor_cmd <<< "${editor_value}"
    "${editor_cmd[@]}" "${target_path}"
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1 && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    xdg-open "${target_path}" >/dev/null 2>&1 &
    return 0
  fi

  if command -v less >/dev/null 2>&1; then
    less "${target_path}"
    return 0
  fi

  cat "${target_path}"
}
