#!/usr/bin/env bash
#
# Sourced, not executed. Loads the untracked repository-root .env so local
# credentials stay out of git. A value already exported in the environment
# takes precedence over the file.

_env_file="${1:-}"
if [[ -f "$_env_file" ]]; then
  while IFS= read -r _line || [[ -n "$_line" ]]; do
    _line="${_line%$'\r'}"
    [[ "$_line" =~ ^[[:space:]]*(#|$) ]] && continue
    [[ "$_line" == *=* ]] || continue
    _name="${_line%%=*}"
    [[ -n "${!_name:-}" ]] && continue
    export "$_line"
  done < "$_env_file"
fi
unset _env_file _line _name
