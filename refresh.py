#!/usr/bin/env python3
"""GitHub Actions 用: 空き取得→LP生成→index.html へ書き出すワンショット。"""
import os
import subprocess
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
env = dict(os.environ, LP_IMAGE_MODE="relative")
subprocess.run([sys.executable, "fetch_availability.py", "availability.json", "30"], check=True)
subprocess.run([sys.executable, "build_lp.py"], check=True, env=env)
os.replace("lp-sample.html", "index.html")
print("index.html updated")
