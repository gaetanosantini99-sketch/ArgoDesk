#compdef argodesk argodesk-backup argodesk-calendar argodesk-contacts argodesk-cookbook argodesk-docs argodesk-gallery argodesk-mail argodesk-mcp argodesk-memory argodesk-notes argodesk-personal argodesk-preset argodesk-research argodesk-sessions argodesk-signature argodesk-skills argodesk-tasks argodesk-theme argodesk-webhook
# Zsh tab-completion for the argodesk umbrella + sub-CLIs.
#
# Drop in any directory on $fpath, e.g.:
#     fpath=(/path/to/argodesk-ui/scripts/_completion $fpath)
#     autoload -U compinit; compinit
#
# Then `argodesk <tab>` completes subcommands; `argodesk mail <tab>`
# completes mail subcommands; `argodesk-mail <tab>` works the same.

_argodesk_scripts_dir() {
    local self="${(%):-%x}"
    while [[ -L "$self" ]]; do self="$(readlink "$self")"; done
    cd "${self:h}/.." && pwd
}

typeset -gA _argodesk_subs

_argodesk_refresh() {
    _argodesk_subs=()
    local dir="$(_argodesk_scripts_dir)"
    local py="$dir/../venv/bin/python"
    [[ -x "$py" ]] || py="$(command -v python3)"
    local f sub help_out commands
    for f in "$dir"/argodesk-*; do
        [[ -x "$f" ]] || continue
        case "$f" in
            *.bak|*.pyc|*.pre-*) continue ;;
        esac
        sub="${${f:t}#argodesk-}"
        help_out=$("$py" "$f" --help 2>/dev/null) || continue
        commands=$(echo "$help_out" | grep -oE '\{[a-z0-9_,-]+\}' | head -1 \
            | tr -d '{}' | tr ',' ' ')
        _argodesk_subs[$sub]="$commands"
    done
}

_argodesk() {
    [[ ${#_argodesk_subs} -eq 0 ]] && _argodesk_refresh

    local cmd="${words[1]}"

    if [[ "$cmd" == "argodesk" ]]; then
        if (( CURRENT == 2 )); then
            local -a subs=(${(k)_argodesk_subs} help)
            _describe 'subcommand' subs
            return
        fi
        local sub="${words[2]}"
        if [[ "$sub" == "help" ]] && (( CURRENT == 3 )); then
            local -a subs=(${(k)_argodesk_subs})
            _describe 'subcommand' subs
            return
        fi
        if (( CURRENT == 3 )); then
            local -a sc=(${(s/ /)_argodesk_subs[$sub]})
            _describe 'command' sc
            return
        fi
        return
    fi

    # argodesk-foo <tab>
    local sub="${cmd#argodesk-}"
    if (( CURRENT == 2 )); then
        local -a sc=(${(s/ /)_argodesk_subs[$sub]})
        _describe 'command' sc
        return
    fi
}

_argodesk "$@"
