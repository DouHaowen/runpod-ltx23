import json
import sys
import traceback
from pathlib import Path

from core import run_generation, update_status


def main():
    req_path = Path(sys.argv[1])
    req = json.loads(req_path.read_text())
    job_dir = req_path.parent
    run_generation(req, job_dir)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        req_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
        if req_path is not None:
            job_dir = req_path.parent
            update_status(
                job_dir,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                traceback=traceback.format_exc(),
            )
        raise
