"""
The `clishe` command when Clishe is installed with pipx or pip. It runs the
bundled clishe.sh with bash, exactly like the git install does.
"""
import os
import shutil
import sys
from pathlib import Path


def main():
    bash = shutil.which("bash")
    if not bash:
        print("Clishe needs bash, which wasn't found on this system.", file=sys.stderr)
        return 1
    script = Path(__file__).resolve().parent / "clishe.sh"
    os.execv(bash, [bash, str(script), *sys.argv[1:]])


if __name__ == "__main__":
    sys.exit(main())
