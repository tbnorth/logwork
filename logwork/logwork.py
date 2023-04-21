import re
import time
from collections import deque
from pathlib import Path

WORKLOG = Path("~/.worklog").expanduser()

REGEX = re.compile(r"^\d{8}-\d{4} ")
if not WORKLOG.exists():
    WORKLOG.touch()

length = WORKLOG.stat().st_size
with WORKLOG.open() as in_file:
    in_file.seek(max(0, length - 1000))
    lines = deque(in_file)
    while lines and not REGEX.match(lines[-1]):
        lines.pop()
if lines:
    last = time.strptime(lines[-1][:13], "%Y%m%d-%H%M")
    print(last)

with WORKLOG.open("a") as log_file:
    log_file.write(time.strftime("%Y%m%d-%H%M \n"))
