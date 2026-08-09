"""
SCSS Compiler Utility for WordPress Auth Service
Compiles static/scss/style.scss into compressed production CSS at static/css/style.css using Dart Sass.
"""

import os
import subprocess
import sys

def build_scss():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scss_file = os.path.join(base_dir, "static", "scss", "style.scss")
    css_dir = os.path.join(base_dir, "static", "css")
    css_file = os.path.join(css_dir, "style.css")

    if not os.path.exists(scss_file):
        print(f"Error: SCSS file not found at {scss_file}")
        sys.exit(1)

    os.makedirs(css_dir, exist_ok=True)

    cmd = [
        "npx", "--yes", "sass",
        "--style=compressed",
        "--no-source-map",
        scss_file,
        css_file
    ]

    print(f"Compiling SCSS: {scss_file} -> {css_file}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        file_size = os.path.getsize(css_file)
        print(f"[OK] SCSS compiled successfully! ({file_size} bytes)")
    else:
        print(f"[ERROR] SCSS compilation failed:")
        print(result.stderr)
        sys.exit(1)

if __name__ == "__main__":
    build_scss()
