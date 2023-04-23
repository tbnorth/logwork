#!/usr/bin/env python3
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

INTERVAL = 15  # Minutes between work log entries
WORKLOG = "~/.worklog"
WORKLOG = Path(WORKLOG).expanduser()
if not WORKLOG.exists():
    WORKLOG.touch()
TIME_REGEX = re.compile(r"^\d{8}-\d{4} ")
GIT_REGEX = re.compile(r"\[.*]$")
HTTP_REGEX = re.compile(r"https?://")
CREDS_REGEX = re.compile(r"[^/]*@")
ORIGIN_REGEX = re.compile(r"Your branch is .*'(.+)'")

# h history command in logwork.sh because that's where the shell history is available
SCREEN = 'screen' if os.environ.get("STY") else ""
COMMANDS = {
    "e": {
        "name": "Edit",
        "command": rf'{SCREEN} vim {WORKLOG} -c "normal G" -c "s/$/\r\r/" '
        '-c "normal G"',
    },
    "t": {
        "name": "Tags",
        "function": "tags",
    },
    "s": {
        "name": "Log screen",
        "command": "screen -X hardcopy -h /tmp/tmpwl; "
        f"tail -n 100 /tmp/tmpwl >> {WORKLOG}; "
        f'{SCREEN} vim {WORKLOG} -c "normal G" ' r'-c "?^\d\{8\}-\d\{4\}" '
        '-c "normal zz"',
    },
}


@dataclass
class GitInfo:
    branch: str = ""
    commit: str = ""
    origin: str = ""
    flags: str = ""  # !?*+>x - modified, untracked, ahead, new, renamed, deleted

    def __str__(self):
        return (
            f"[{self.branch}{self.flags} {self.origin} {self.commit}]"
            if self.branch
            else ""
        )

    def prompt(self):
        return f"[{self.branch}{self.flags}]" if self.branch else ""


@dataclass
class WorkState:
    time: datetime = None  # Time of the last work log entry
    cwd: Path = None  # Working directory
    git_info: str = None  # Git commit hash etc., textual representation
    from_end: int = None  # Lines from end of log on which timestamp was found
    has_tags: bool = None  # Whether the last log entry has any tags


def git_info() -> str:
    status = subprocess.run(
        "git status", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    status = status.stdout.decode("utf8") + "\n" + status.stderr.decode("utf8")
    if "fatal: " in status:
        return GitInfo()
    flags = []
    if "modified:" in status:
        flags.append("!")
    if "Untracked files" in status:
        flags.append("?")
    if "Your branch is ahead of" in status:
        flags.append("*")
    if "new file:" in status:
        flags.append("+")
    if "renamed:" in status:
        flags.append(">")
    if "deleted:" in status:
        flags.append("x")
    if flags:
        flags = " " + "".join(flags).strip()
    else:
        flags = ""

    status = status.splitlines()
    branch = status[0].split()[-1]
    origin = next((i for i in status if i.startswith("Your branch")), "")
    origin = ORIGIN_REGEX.search(origin).group(1) if origin else ""
    if origin:
        origin = origin.split()[-1].strip("'.").split("/")[0]
    if origin:
        origin = subprocess.run(
            "git remote get-url " + origin,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        origin = origin.stdout.decode("utf8").strip()
        if HTTP_REGEX.search(origin):
            # Remove the username and password from the URL
            origin = CREDS_REGEX.sub("", origin)
        origin = origin.replace("git@", "")
        origin = HTTP_REGEX.sub("", origin)
    commit = subprocess.run(
        "git rev-parse --short HEAD",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Get remote url
    commit = commit.stdout.decode("utf8").strip()
    return GitInfo(branch=branch, commit=commit, origin=origin, flags=flags)


def last_state() -> WorkState:
    """Return the last work state from the work log."""
    length = WORKLOG.stat().st_size
    # Rather than the deque approach, which reads the whole file, seek plus list caps
    # the amount of data read to 10,000 bytes.  Seeking only skips data in binary mode,
    # in text mode it needs to read the whole file to account for multi-byte characters.
    has_tags = False
    with WORKLOG.open("rb") as in_file:
        in_file.seek(max(0, length - 10_000))
        lines = list(in_file)
        last_time = None
        for from_end, line in enumerate(reversed(lines)):
            try:
                line = line.decode("utf8")
            except UnicodeDecodeError:
                continue  # 10,000 bytes may have split a multi-byte character.
            if line.startswith("tags:"):
                has_tags = True
            last_time = TIME_REGEX.match(line)
            if last_time:
                break

    if last_time:
        time_str = last_time.group(0)
        last = datetime.strptime(time_str.strip(), "%Y%m%d-%H%M")
        git_str = GIT_REGEX.search(line)
        git_str = git_str.group(0) if git_str else ""
        cwd = line[len(time_str) : -len(git_str) - 1].strip()
        return WorkState(
            time=last, cwd=cwd, git_info=git_str, from_end=from_end, has_tags=has_tags
        )

    return WorkState()


def tags():
    """Open the work log in vim, with the cursor at the end of the tags line."""
    # See if the last entry has tags, add tags: line if not
    last = last_state()
    if not last.time:
        print("No previous work log entry found.")
        return
    cmd = ["vim -c 'normal G'"]
    if last.from_end:  # 0k and 1k are the same, both go up one line
        cmd.append(f"-c 'normal {last.from_end}k'")
    if not last.has_tags:
        cmd.append("-c 'normal otags: '")
    else:
        cmd.append("-c 'normal j'")
    cmd.append("-c 'normal $zz'")
    cmd.append(str(WORKLOG))

    subprocess.run(" ".join(cmd), shell=True)

    # Tell the user about any new (previously unused) tags
    tags = set()
    last_tags = set()
    with WORKLOG.open() as log_file:
        for line in log_file:
            if line.startswith("tags:"):
                if last_tags:
                    tags.update(last_tags)
                    last_tags.clear()
                last_tags = set(line[5:].strip().split())
    new_tags = last_tags - tags
    if new_tags:
        print("Previous tags: ", ", ".join(tags))
        print("New tags: ", ", ".join(new_tags))


def handle_command():
    args = sys.argv[1:]
    if not args or args[0] not in COMMANDS:
        return
    command = COMMANDS[args[0]]

    if "command" in command:
        subprocess.run(command["command"], shell=True)
    else:
        globals()[command["function"]]()

    sys.exit()


if __name__ == "__main__":

    # Update log *before* handling command
    last = last_state()
    # print(last)
    if last.time:
        seconds = (datetime.now() - last.time).total_seconds()
    git_parts = git_info()
    if (
        not last.time
        or seconds >= INTERVAL * 60
        or last.cwd != os.getcwd()
        or last.git_info != str(git_parts)
    ):
        with WORKLOG.open("a") as log_file:
            log_file.write(datetime.now().strftime("%Y%m%d-%H%M"))
            log_file.write(f" {os.getcwd()} {git_parts}\n")
        if seconds >= INTERVAL * 60:
            print(f"\n\n{INTERVAL}+ minutes since last work log entry ", end="")
        # So prompt isn't out of date, but not zero so prompt isn't INTERVAL+1
        seconds = 1

    handle_command()  # may exit

    # Integer minutes plus git status to embed in prompt
    print(int((60 * INTERVAL - seconds) // 60 + 1), git_parts.prompt(), sep="", end="")
