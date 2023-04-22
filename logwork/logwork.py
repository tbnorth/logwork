import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

WORKLOG = "~/.worklog"
WORKLOG = Path(WORKLOG).expanduser()
if not WORKLOG.exists():
    WORKLOG.touch()
TIME_REGEX = re.compile(r"^\d{8}-\d{4} ")
GIT_REGEX = re.compile(r"\[.*]$")


@dataclass
class WorkState:
    time: datetime = None  # Time of the last work log entry
    cwd: Path = None  # Working directory
    git_info: str = None  # Git commit hash etc.


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
        last = time.strptime(time_str.strip(), "%Y%m%d-%H%M")
        git_str = GIT_REGEX.search(line)
        git_str = git_str.group(0) if git_str else ""
        cwd = line[len(time_str) : -len(git_str) - 1].strip()
        return WorkState(time=last, cwd=cwd, git_info=git_str)

    return WorkState()


last = last_state()
print(last)
with WORKLOG.open("a") as log_file:
    log_file.write(time.strftime("%Y%m%d-%H%M"))
    log_file.write(f" {last.cwd} {last.git_info}\n")
