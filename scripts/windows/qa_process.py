"""Bound QA subprocess lifetime, including the onefile bootloader's child."""
import subprocess


def run_executable(command,*,cwd,env,timeout):
    process=subprocess.Popen(command,cwd=cwd,env=env)
    try:return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,check=False)
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill()
        return -1
