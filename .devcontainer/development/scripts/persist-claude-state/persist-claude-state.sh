#!/usr/bin/env bash
# Persist the durable, NON-credential parts of Claude Code state across container
# rebuilds. The container home is an ephemeral overlay ("Rebuild Container" wipes
# it); /workspaces is the Codespace's persistent disk, alive as long as the
# Codespace itself. /workspaces/.claude sits OUTSIDE every repo working tree, so
# nothing in it can ever be committed or pushed.
#
# Adopted from the claude-state piece of the initialize-repository skill
# (issue #141). Changes from that source: the system Python is Debian's
# /usr/bin/python3 (3.11 in this image) rather than python3.14, and references
# to the skill's seed-claude-settings and tighten-workspace pieces, which this
# repository does not use, are dropped from the comments.
#
# Allowlist (anything not listed stays ephemeral):
#   projects/            conversation transcripts, tool results, subagent logs,
#                        and agent memory — what /resume and --continue restore from
#   file-history/        checkpoints backing /rewind (persist across sessions)
#   settings.json        user-level settings (model, effort, includeCoAuthoredBy, ...)
#   settings.local.json  user-level local overrides. CAUTION: the docs designate
#                        this file for credential-helper config (apiKeyHelper,
#                        awsCredentialExport, env-block keys) — if you ever add
#                        such config, reconsider persisting it (see the note
#                        at the credential backstop below).
#
# Deliberately excluded — credentials and account identity are wiped WITH the
# container, so a rebuild forces re-authentication instead of parking tokens on
# the long-lived disk:
#   .credentials.json (OAuth tokens), ~/.claude.json + backups/ (oauthAccount /
#   userID / machineID), ide/ (live lock incl. an authToken), sessions/,
#   session-env/, shell-snapshots/, downloads/, .last-cleanup (runtime or
#   regenerable).
#
# Modes:
#   link      (default) fold existing state into the persistent dir, then replace
#             the allowlisted paths with symlinks into it. Idempotent and
#             self-healing: if an update ever replaces a symlink with a regular
#             file (atomic rename-over), the next run folds it back and re-links.
#             Safe live: verified no process holds open fds under ~/.claude.
#             ~/.claude itself, which holds .credentials.json, is made 0700,
#             and narrowed to exactly 0700 at every run; a mode that
#             cannot be changed is named, and the run goes on.
#   snapshot  one-way copy into the persistent dir; touches nothing in $HOME.
#   export    snapshot, then one archive of the persistent dir (see below).
#
# Both modes end by tightening what they leave on the disk: new
# entries under /workspaces come out 0666 / 0777 unless a mode is set, so each
# allowlisted file is made 0600 and each directory 0700, a second layer under
# the persistent dir's own 0700 for the day that directory is recreated or
# loosened. Idempotent, and self-healing from postStartCommand like the links.
# No mode is changed through a link.  An allowlisted entry that is one
# is left out before any narrowing (below), so only a link swapped in
# after that check reaches the narrowing: it is resolved once, and what it
# leads to narrowed only when it is a file or a directory, as the entry is to
# be, of this user's own, inside the persistent dir or ~/.claude; else it is
# named and left as it is, and one leading outside those two fails the run.
# A link at the persistent dir or at ~/.claude itself is refused, and the run
# stops before anything is made or linked in either: links are made only at
# the allowlisted names inside ~/.claude.
#
# No operation follows a link inside the persistent dir:
#   - an allowlisted entry that is or holds, at any depth, a link or a
#     special file (anything but a file, a directory or a link, or a file
#     with a hard link to a name outside its tree), or a real ~/.claude
#     directory about to be copied in, or a ~/.claude/<name>.migrating an
#     earlier start left, that holds one, is left out:
#     nothing is copied, linked or narrowed through it, an earlier start's
#     link at ~/.claude/<name> goes, export leaves it out of the archive, and
#     the run ends with 1 and a line naming the entry, once every other entry
#     is persisted and linked as usual;
#   - a ~/.claude/<name>.migrating with no link in it, left by a start that
#     stopped part-way, is swept into the persistent dir, then removed;
#   - the check runs again after each copy, before anything is linked to or
#     removed, so a link swapped in at a source and copied as a link leaves
#     the entry out as well;
#   - the copies replace a link swapped in after that check, or stop at one
#     at a directory, and the move and links in ~/.claude stop at a link or
#     directory found at their name, never landing inside it;
#   - a link's target is narrowed only inside the persistent dir or ~/.claude;
#   - export renames a new owner-only archive over its path, replacing a
#     link there rather than writing through it.
# The run is refused as root, where every entry counts as its own, and stops
# with a line of its own when the system Python does not start, both before
# anything is made.
set -euo pipefail
# Programs from /usr/bin alone, by name below: the
# PATH a start runs with may put ~/.local/bin, which the user can write,
# ahead of the system directories.
export PATH=/usr/bin
# The directory this script is in: in the image, the root-owned, read-only tree
# that also holds the Python helpers it runs (read_persist.py, narrow.py).
HERE="$(dirname -- "${BASH_SOURCE[0]}")"

# The system Python, which every narrowing below runs on, started once before
# anything is made: one that is missing or
# does not start stops the run here, with a line of this script's own, rather
# than with bash's 127 under set -e, or not at all behind link's "|| true".
# Its own error lines, which open with a path, are not passed on.  Its status
# also says whether the run is root's, which is refused: as root every
# entry is the run's own, so no owner check below holds, and a link could
# lead a narrowing to any file of the system.  From the kernel's effective
# uid, never from bash's EUID, which the environment can set.  Nothing runs
# this script as root: the create and start commands run it as the
# container's user.
started=0
/usr/bin/python3 -I -S -B -c 'import os, sys; sys.exit(3 if os.geteuid() == 0 else 0)' 2> /dev/null || started=$?
if [ "$started" -eq 3 ]; then
  echo "persist-claude-state: refusing to run as root, where every entry counts as the run's own, so nothing was persisted." >&2
  exit 1
elif [ "$started" -ne 0 ]; then
  echo "persist-claude-state: the system Python, /usr/bin/python3, did not start, so nothing was persisted." >&2
  exit 1
fi

# The persistent directory, from persist-directory beside this script: by a
# path built from where this script is, in the image's root-owned, read-only
# tree, never from the environment.  read_persist.py, beside it too, accepts
# exactly one line holding an absolute, normalized path; anything else, a
# missing or linked file included, stops the run here, before anything is made.
read_persist=0
PERSIST="$(/usr/bin/python3 -I -S -B "$HERE/read_persist.py" "$HERE/persist-directory")" || read_persist=$?
if [ "$read_persist" -ne 0 ]; then
  echo "persist-claude-state: its persist-directory file is missing or holds no one absolute, normalized path, so nothing was persisted." >&2
  exit 1
fi
CLAUDE_HOME="$HOME/.claude"

DIRS=(projects file-history)
FILES=(settings.json settings.local.json)

# narrow_no_follow KIND PATH [KIND PATH ...]: each PATH, a KIND ("file" or
# "directory"), set to its owner-only mode (0600 or 0700), changing no mode
# through a link and nothing outside the persistent directory and ~/.claude;
# returns 1 when a mode could not be changed or a link led elsewhere.  The
# rules and their reasons are in narrow.py, beside this script.
narrow_no_follow() {
  /usr/bin/python3 -I -S -B "$HERE/narrow.py" "$PERSIST" "$CLAUDE_HOME" "$@"
}

# Each of the two directories must be one of this user's own, never a link:
# what a link leads to, another user's directory say, is no place to persist
# into or link from, so the run stops before anything is made in either
#.  narrow_no_follow below then finds no link there, but for one
# swapped in since, which it changes nothing through.
for top in "$PERSIST" "$CLAUDE_HOME"; do
  if [ -L "$top" ]; then
    echo "persist-claude-state: $top is a link; it must be a directory of this user's own, so nothing was persisted." >&2
    exit 1
  fi
done

mkdir -p "$PERSIST"
narrow_no_follow directory "$PERSIST"
# Backstop: no credential-shaped file survives on the persistent disk, no matter
# what put it there.
rm -f "$PERSIST/.credentials.json" "$PERSIST/.claude.json"
# settings.local.json is persisted on purpose. The docs designate it for
# credential-helper config (apiKeyHelper, awsCredentialExport, env-block keys);
# none is used here, but if such config is ever added, stop persisting it by
# taking it out of FILES below and removing it here (see issue #141).
rm -rf "$PERSIST/backups"

# The allowlisted names this run left out, each for a link refuse_links found
# in it; the run ends with 1 when there is one, once every other entry is done.
SKIPPED=()

# stopped STATUS WHAT TODO: after a cp, mv, ln or find that failed, a line of
# the script's own saying what it could not do, to what, and what to do,
# below the tool's own line, and the run stops with the tool's status, as it
# did under set -e.  WHAT and TODO are built from the
# script's own paths and the allowlisted names alone.
stopped() {
  echo "persist-claude-state: cannot $2, so the run stopped there; $3, then run it again (each Codespace start runs link anew)." >&2
  exit "$1"
}

# one_of NAME WORD...: 0 when NAME is exactly one of the WORDs, a name with
# spaces matching none of them.
one_of() {
  local word
  for word in "${@:2}"; do
    if [ "$word" = "$1" ]; then return 0; fi
  done
  return 1
}

# refuse_links NAME: 0 when neither $PERSIST/NAME nor, when NAME is
# allowlisted and a real directory to be copied in, ~/.claude/NAME, nor, for
# an allowlisted directory, the ~/.claude/NAME.migrating an earlier start may
# have left, is a link or holds one at any depth, or
# is or holds a special file: anything but a file, a directory or a link, or
# a file with a hard link to a name outside that entry's tree, through which a
# write would reach whatever else holds it.  Hard links between two names in
# the same tree reach nothing else and are kept.
# Otherwise the first of them that does is named, NAME joins SKIPPED, and 1:
# the caller leaves NAME out, so nothing is copied, linked, moved or narrowed
# through what was found, and every other entry goes on as usual.
# A link at ~/.claude/NAME itself is the one link() makes, never refused.  A
# tree find cannot read all of stops the run rather than pass as clean, as
# the copy into it would have.  Only the path the script built is named,
# never the link or special file found; one built from a name export found
# in the persistent dir, outside the allowlist, is named quoted, so no
# control character in it reaches the terminal.
refuse_links() {
  local entry found named
  local -a entries=("$PERSIST/$1")
  if one_of "$1" "${DIRS[@]}" "${FILES[@]}"; then
    entries+=("$CLAUDE_HOME/$1")
  fi
  if one_of "$1" "${DIRS[@]}"; then
    entries+=("$CLAUDE_HOME/$1.migrating")
  fi
  for entry in "${entries[@]}"; do
    if [ "$entry" = "$CLAUDE_HOME/$1" ] && { [ -L "$entry" ] || [ ! -d "$entry" ]; }; then
      continue
    fi
    if [ ! -e "$entry" ] && [ ! -L "$entry" ]; then
      continue
    fi
    # Called as a condition, where set -e does not hold: a failure exits here.
    found="$(find -P "$entry" \( -type l -o ! \( -type f -o -type d \) \) -print -quit)" \
      || stopped "$?" "look through $entry for links and special files" "make every directory in it readable"
    # A file with more names (its link count) than the tree holds for it has
    # a name outside the tree.  Each file with a hard link is printed as
    # device:inode and link count, never by name, and counted.
    if [ -z "$found" ]; then
      found="$(find -P "$entry" -type f -links +1 -printf '%D:%i %n\n' \
        | awk '{ names[$1]++; links[$1] = $2 } END { for (file in names) if (links[file] + 0 > names[file]) { print file; exit } }')" \
        || stopped "$?" "look through $entry for hard links" "make every directory in it readable"
    fi
    if [ -n "$found" ]; then
      named="$entry"
      if ! one_of "$1" "${DIRS[@]}" "${FILES[@]}"; then
        named="${entry@Q}"
      fi
      echo "persist-claude-state: $named is or holds a link or a special file, so it was left out and nothing was written through it; remove the link or special file, then restart the Codespace." >&2
      SKIPPED+=("$1")
      return 1
    fi
  done
}

# Owner-only modes on everything allowlisted that exists (see the header),
# but an entry left out.  Entries Claude later writes inside the directories
# inherit the disk's default, but under 0700 directories, which is the layer
# that counts.  One system-Python start for them all; a mode that cannot be
# changed ends the run with 1, as a failed chmod did.
tighten() {
  local -a entries=()
  local d f
  for d in "${DIRS[@]}"; do
    [[ " ${SKIPPED[*]} " == *" $d "* ]] || entries+=(directory "$PERSIST/$d")
  done
  for f in "${FILES[@]}"; do
    [[ " ${SKIPPED[*]} " == *" $f "* ]] || entries+=(file "$PERSIST/$f")
  done
  narrow_no_follow "${entries[@]}"
}

# Each copy below is followed by refuse_links again, before anything links
# to, removes or narrows what it copied: cp -a
# copies a link as a link, so one swapped in at the source after the check
# lands in the persistent dir.  A hit leaves the entry out, as above, and
# in link takes away a link at ~/.claude/<name>, as for an entry left out
# at the first check.
snapshot() {
  for d in "${DIRS[@]}"; do
    refuse_links "$d" || continue
    if [ -d "$CLAUDE_HOME/$d" ] && [ ! -L "$CLAUDE_HOME/$d" ]; then
      mkdir -p "$PERSIST/$d"
      # -u: newest wins, reruns never regress.  -T and --remove-destination:
      # a link swapped in at the entry since refuse_links looked stops the
      # copy, and one at a file below it is replaced, never written through.
      cp -auT --remove-destination "$CLAUDE_HOME/$d" "$PERSIST/$d" \
        || stopped "$?" "copy $CLAUDE_HOME/$d into $PERSIST/$d" "free space on the disk, or remove any link at $PERSIST/$d"
      refuse_links "$d" || continue
    fi
  done
  for f in "${FILES[@]}"; do
    refuse_links "$f" || continue
    if [ -f "$CLAUDE_HOME/$f" ] && [ ! -L "$CLAUDE_HOME/$f" ]; then
      cp -auT --remove-destination "$CLAUDE_HOME/$f" "$PERSIST/$f" \
        || stopped "$?" "copy $CLAUDE_HOME/$f into $PERSIST/$f" "free space on the disk, or remove whatever is at $PERSIST/$f"
      refuse_links "$f" || continue
    fi
  done
  tighten
}

link() {
  mkdir -p -m 700 "$CLAUDE_HOME"
  # Owner-only, as it holds .credentials.json: the image's installer made it
  # under the umask (0755).  Named on failure, and the run goes on, so the
  # links below are still made.
  narrow_no_follow directory "$CLAUDE_HOME" || true
  for d in "${DIRS[@]}"; do
    if ! refuse_links "$d"; then
      # Left out, and ~/.claude/$d not left leading through what was found:
      # an earlier start's link goes (a link holds no data), and Claude Code
      # makes its directory anew, which a later start folds back in.
      if [ -L "$CLAUDE_HOME/$d" ]; then rm -f "$CLAUDE_HOME/$d"; fi
      continue
    fi
    mkdir -p "$PERSIST/$d"
    # A start stopped between the move and the sweep below leaves
    # ~/.claude/$d.migrating behind, which the move's -T cannot replace once
    # it holds anything.  refuse_links found no
    # link in it, so what it holds is swept in, newest winning, and it goes,
    # before the move, whether or not ~/.claude/$d is a link by now.
    if [ -d "$CLAUDE_HOME/$d.migrating" ] && [ ! -L "$CLAUDE_HOME/$d.migrating" ]; then
      cp -auT --remove-destination "$CLAUDE_HOME/$d.migrating" "$PERSIST/$d" \
        || stopped "$?" "copy $CLAUDE_HOME/$d.migrating into $PERSIST/$d" "free space on the disk, or remove any link at $PERSIST/$d"
      if ! refuse_links "$d"; then
        if [ -L "$CLAUDE_HOME/$d" ]; then rm -f "$CLAUDE_HOME/$d"; fi
        continue
      fi
      rm -rf "$CLAUDE_HOME/$d.migrating"
    fi
    if [ -d "$CLAUDE_HOME/$d" ] && [ ! -L "$CLAUDE_HOME/$d" ]; then
      # Live-swap: copy, atomically move the real dir aside, link, then sweep up
      # anything written during the copy. Writers open-append-close, so the only
      # exposure is the instant between mv and ln.  -T on both: a link or a
      # directory found at the name stops the run (set -e) rather than take
      # the move or the link inside what it leads to.
      cp -auT --remove-destination "$CLAUDE_HOME/$d" "$PERSIST/$d" \
        || stopped "$?" "copy $CLAUDE_HOME/$d into $PERSIST/$d" "free space on the disk, or remove any link at $PERSIST/$d"
      refuse_links "$d" || continue
      mv -T "$CLAUDE_HOME/$d" "$CLAUDE_HOME/$d.migrating" \
        || stopped "$?" "move $CLAUDE_HOME/$d aside to $CLAUDE_HOME/$d.migrating" \
                   "move whatever is at $CLAUDE_HOME/$d.migrating out of ~/.claude"
      ln -sfnT "$PERSIST/$d" "$CLAUDE_HOME/$d" \
        || stopped "$?" "link $CLAUDE_HOME/$d to $PERSIST/$d" "move whatever is at $CLAUDE_HOME/$d out of ~/.claude"
      cp -auT --remove-destination "$CLAUDE_HOME/$d.migrating" "$PERSIST/$d" \
        || stopped "$?" "copy $CLAUDE_HOME/$d.migrating into $PERSIST/$d" "free space on the disk, or remove any link at $PERSIST/$d"
      # A hit here takes the link just made away again, and the moved
      # directory stays, for a later start to sweep in.
      if ! refuse_links "$d"; then
        if [ -L "$CLAUDE_HOME/$d" ]; then rm -f "$CLAUDE_HOME/$d"; fi
        continue
      fi
      rm -rf "$CLAUDE_HOME/$d.migrating"
    else
      ln -sfnT "$PERSIST/$d" "$CLAUDE_HOME/$d" \
        || stopped "$?" "link $CLAUDE_HOME/$d to $PERSIST/$d" "move whatever is at $CLAUDE_HOME/$d out of ~/.claude"
    fi
  done
  for f in "${FILES[@]}"; do
    if ! refuse_links "$f"; then
      if [ -L "$CLAUDE_HOME/$f" ]; then rm -f "$CLAUDE_HOME/$f"; fi
      continue
    fi
    if [ -f "$CLAUDE_HOME/$f" ] && [ ! -L "$CLAUDE_HOME/$f" ]; then
      cp -auT --remove-destination "$CLAUDE_HOME/$f" "$PERSIST/$f" \
        || stopped "$?" "copy $CLAUDE_HOME/$f into $PERSIST/$f" "free space on the disk, or remove whatever is at $PERSIST/$f"
      if ! refuse_links "$f"; then
        if [ -L "$CLAUDE_HOME/$f" ]; then rm -f "$CLAUDE_HOME/$f"; fi
        continue
      fi
      rm -f "$CLAUDE_HOME/$f"
    fi
    # A dangling link is fine before first write — writing through it creates
    # the target on the persistent disk.  A directory at the name stops the
    # run (-T), rather than take the link inside it.
    ln -sfnT "$PERSIST/$f" "$CLAUDE_HOME/$f" \
      || stopped "$?" "link $CLAUDE_HOME/$f to $PERSIST/$f" "move whatever is at $CLAUDE_HOME/$f out of ~/.claude"
  done
  tighten
  # Each entry not left out must now be a link to exactly its persistent
  # name, as made above; one that is not, replaced since
  # or never made, is named, and the run ends with 1, once every name is
  # looked at.  The link's text is read by find, which the script already
  # runs, with a "." after it, so a trailing newline in it is kept.
  local name target mislinked=0
  for name in "${DIRS[@]}" "${FILES[@]}"; do
    if one_of "$name" "${SKIPPED[@]}"; then
      continue
    fi
    target=""
    if [ -L "$CLAUDE_HOME/$name" ]; then
      target="$(find -P "$CLAUDE_HOME/$name" -maxdepth 0 -printf '%l.')" \
        || stopped "$?" "read the link at $CLAUDE_HOME/$name" "check that ~/.claude is readable"
      target="${target%.}"
    fi
    if [ "$target" != "$PERSIST/$name" ]; then
      echo "persist-claude-state: $CLAUDE_HOME/$name is not a link to $PERSIST/$name after linking, so what is written there may not persist; restart the Codespace to link it again." >&2
      mislinked=1
    fi
  done
  if [ "$mislinked" -ne 0 ]; then
    exit 1
  fi
}

# One downloadable file of everything persisted (projects incl. memory,
# file-history, settings) and nothing else: credentials never enter $PERSIST
# (removed above), so a plain archive of it is safe to carry to a new
# Codespace, where "link" restores it once it is unpacked to /workspaces/.claude.
# An entry snapshot left out stays out of the archive too, so no link found
# there is carried on.  The archive is written to a new file beside the path,
# then renamed over it: a link at the path is replaced, never written
# through or changed, and an archive already there is still overwritten.  On
# any failure the temporary file goes.  Owner-only from its first byte: made
# under umask 077, and narrowed through no link before the rename, which also
# holds where a default ACL on the directory widens what the umask leaves.
# The excludes stay, and every top-level entry outside the allowlist goes
# through refuse_links too, so one that is or holds
# a link or a special file is left out of the archive the same way, with the
# same line; tar takes the names literally, never as patterns.
# tar's status 1, a file that changed as it was read (Claude Code writing
# live), keeps the archive with a line saying so, and the run goes on; 2 and
# above, a fatal error, fail the run, the temporary file going.
export_archive() {
  local out="${1:-/workspaces/claude-state-$(date -u +%Y%m%d-%H%M%S).tgz}"
  # The path as the tools below take it: a relative one ./-prefixed, so a
  # name that opens with "-" is never read as an option, and relative paths
  # still work.
  local destination="$out"
  if [[ "$destination" != /* ]]; then
    destination="./$destination"
  fi
  local temporary
  local archived=0
  local entry name
  local -a present
  snapshot
  shopt -s nullglob dotglob
  present=("$PERSIST"/*)
  shopt -u nullglob dotglob
  for entry in "${present[@]}"; do
    name="${entry##*/}"
    if ! one_of "$name" "${DIRS[@]}" "${FILES[@]}" .credentials.json .claude.json backups; then
      refuse_links "$name" || true
    fi
  done
  umask 077
  temporary="$(mktemp -- "$destination.XXXXXX")"
  trap "rm -f -- ${temporary@Q}" EXIT
  # To tar's output, which the shell opens on the temporary file, never by
  # its name: tar's compressor child can outlive a tar that failed, and one
  # that opened the name itself made the file again after the trap removed
  # it.  Writing to the descriptor it was handed, it reaches only the
  # inode the trap unlinked.
  tar -C "$(dirname "$PERSIST")" -czf - --no-wildcards \
      --exclude='.credentials.json' --exclude='.claude.json' --exclude='backups' \
      "${SKIPPED[@]/#/--exclude=$(basename "$PERSIST")/}" "$(basename "$PERSIST")" > "$temporary" || archived=$?
  if [ "$archived" -gt 1 ]; then
    exit "$archived"
  elif [ "$archived" -eq 1 ]; then
    echo "persist-claude-state: some files changed while they were archived, so the archive may hold them part-written; it was kept all the same." >&2
  fi
  narrow_no_follow file "$temporary"
  mv -T -- "$temporary" "$destination" \
    || stopped "$?" "rename the new archive over its path" "check that its directory is writable and holds no directory at that name"
  trap - EXIT
  echo "exported $out"
}
case "${1:-link}" in
  snapshot) snapshot ;;
  link)     link ;;
  export)   export_archive "${2:-}" ;;
  *) echo "usage: $0 [link|snapshot|export [archive.tgz]]" >&2; exit 2 ;;
esac
# An entry left out ends the run with 1, once every other one is done, so the
# start that left it out is reported as failed.
if [ "${#SKIPPED[@]}" -ne 0 ]; then
  exit 1
fi
