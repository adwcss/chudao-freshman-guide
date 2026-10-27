"""Run anywhere: python run.py [--port 8765]. No dependencies or API key needed."""
import argparse
import sys

if sys.version_info < (3, 10):
    raise SystemExit("需要 Python 3.10 或更新版本。请更新 Python 后重新启动。")

from backend.main import serve

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    serve(args.port)
