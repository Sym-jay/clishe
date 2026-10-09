#!/bin/bash
# Helper for tests/test_shell_functions.sh: start `clishe practice`, stop it
# the way a terminal would (a signal to the whole process group), and print
# "<folders left> <progress saved>".
#   bash tests/stop_practice.sh <path to clishe.sh> <INT|TERM|HUP>
set -m  # the practice gets its own process group, like a job in a terminal
clishe="$1" sig="$2"
work="$(mktemp -d)" home="$(mktemp -d)"
mkfifo "$work/in"
HOME="$home" TMPDIR="$work/" NO_COLOR=1 "$clishe" practice basics < "$work/in" > /dev/null 2>&1 &
pid=$!
exec 7>"$work/in"
for _ in $(seq 1 100); do
    compgen -G "$work/clishe-practice.*" > /dev/null && break
    sleep 0.1
done
kill -"$sig" -- "-$pid" 2>/dev/null
for _ in $(seq 1 50); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.1
done
kill -9 "$pid" 2>/dev/null
exec 7>&-
wait "$pid" 2>/dev/null
left=$(compgen -G "$work/clishe-practice.*" | wc -l | tr -d ' ')
saved=$(cat "$home/.local/share/clishe/practice_done_basics" 2>/dev/null || echo none)
echo "$left $saved"
rm -rf "$work" "$home"
