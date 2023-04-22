#!/usr/bin/env python3
import os
import re
import subprocess
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


def git_info() -> str:
    status = subprocess.run("git status", shell=True, capture_output=True)
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
            "git remote get-url " + origin, shell=True, capture_output=True
        )
        origin = origin.stdout.decode("utf8").strip()
        if HTTP_REGEX.search(origin):
            # Remove the username and password from the URL
            origin = CREDS_REGEX.sub("", origin)
        origin = origin.replace("git@", "")
        HTTP_REGEX.sub("", origin)
    commit = subprocess.run(
        "git rev-parse --short HEAD", shell=True, capture_output=True
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
    with WORKLOG.open("rb") as in_file:
        in_file.seek(max(0, length - 10_000))
        lines = list(in_file)
        last_time = None
        for line in reversed(lines):
            try:
                line = line.decode("utf8")
            except UnicodeDecodeError:
                continue  # 10,000 bytes may have split a multi-byte character.
            last_time = TIME_REGEX.match(line)
            if last_time:
                break

    if last_time:
        time_str = last_time.group(0)
        last = datetime.strptime(time_str.strip(), "%Y%m%d-%H%M")
        git_str = GIT_REGEX.search(line)
        git_str = git_str.group(0) if git_str else ""
        cwd = line[len(time_str) : -len(git_str) - 1].strip()
        return WorkState(time=last, cwd=cwd, git_info=git_str)

    return WorkState()


if __name__ == "__main__":
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
        # So prompt isn't out of date, but not zero so prompt isn't INTERVAL+1
        seconds = 1

    print(int((60 * INTERVAL - seconds) // 60 + 1), git_parts.prompt(), sep="", end="")
