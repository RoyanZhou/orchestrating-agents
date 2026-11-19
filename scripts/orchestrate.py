#!/usr/bin/env python3
"""Dispatch tasks to worker agents, schedule shared resources, and report events.

Commands (run from anywhere; <project> is the project folder):
  start  <project>            launch the background supervisor, print the roster
  wait   <project> [--timeout SEC]   block until new events arrive, print them, exit
  status <project> [--watch]  print the roster (--watch refreshes every 10 s)
  retry  <project> <task_id>  re-run a task after review (reads outputs/<id>/REVIEW.md)
  stop   <project>            stop the supervisor and all running workers

The supervisor re-reads plan.json every loop, so tasks appended to plan.json are picked up.
"""
import glob, json, os, shutil, subprocess, sys, time
from pathlib import Path

POLL_SECONDS = 5          # supervisor loop; local file checks are cheap
WAIT_POLL_SECONDS = 2     # how often `wait` checks events.log
DEFAULT_STALL_MINUTES = 20  # research threads normally write files well within this
IS_WIN = os.name == "nt"

# ---------------------------------------------------------------- helpers
def odir(p): return Path(p) / ".orch"

def load_plan(p):
    return json.loads((Path(p) / "plan.json").read_text(encoding="utf-8-sig"))

def load_state(p):
    f = odir(p) / "state.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"tasks": {}}

def save_state(p, st):
    f = odir(p) / "state.json"; tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1), encoding="utf-8"); os.replace(tmp, f)

def emit(p, msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    with open(odir(p) / "events.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")

def read_status(p, tid):
    f = Path(p) / "outputs" / tid / "STATUS"
    if not f.exists(): return ""
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig", errors="replace").splitlines() if l.strip()]
    return lines[-1] if lines else ""

def newest_mtime(p, tid):
    paths = list((Path(p) / "outputs" / tid).rglob("*")) + [Path(p) / "logs" / f"{tid}.log"]
    return max([x.stat().st_mtime for x in paths if x.is_file()] or [0])

def pid_alive(pid):
    if not pid: return False
    if IS_WIN:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try: os.kill(pid, 0); return True
    except OSError: return False

def kill_tree(pid):
    if not pid: return
    if IS_WIN: subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        try: os.killpg(pid, 15)
        except OSError: pass

# ---------------------------------------------------------------- workers
def find_codex():
    exe = shutil.which("codex")
    if exe: return exe
    hits = sorted(glob.glob("C:/Program Files/WindowsApps/OpenAI.Codex_*/app/resources/codex.exe"))
    if hits: return hits[-1]
    if IS_WIN:  # WindowsApps is not listable by normal users; ask the package manager instead
        loc = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                              "(Get-AppxPackage -Name 'OpenAI.Codex*' | Select -Last 1).InstallLocation"],
                             capture_output=True, text=True).stdout.strip()
        exe = Path(loc) / "app" / "resources" / "codex.exe" if loc else None
        if exe and exe.exists(): return str(exe)
    return "codex"

def worker_cmd(plan, task, root, prompt):
    w = plan.get("worker", "codex"); model = plan["model"]; effort = plan["effort"]
    if isinstance(w, dict):  # custom: {"cmd": [... "{prompt}" ...]}
        fmt = dict(prompt=prompt, model=model, effort=effort, root=str(root), id=task["id"], project=plan["project"])
        return [str(a).format(**fmt) for a in w["cmd"]]
    if w == "codex":
        return [plan.get("worker_bin") or find_codex(), "exec", "-C", str(root), "-m", model,
                "-c", f'model_reasoning_effort="{effort}"', "-s", "danger-full-access",
                "--skip-git-repo-check", "-c", 'web_search="live"', prompt]
    if w == "claude":
        return [plan.get("worker_bin") or shutil.which("claude") or "claude", "-p", prompt,
                "--model", model, "--effort", effort, "--permission-mode", "bypassPermissions",
                "-n", f"{plan['project']}-{task['id']}"]
    raise SystemExit(f"unknown worker '{w}' (use codex, claude, or {{\"cmd\": [...]}})")

def build_prompt(task, revision):
    tid = task["id"]
    s = (f"You are worker {tid} in this project. Read {task['brief']} in full and follow it. "
         f"Write all output to outputs/{tid}/. Append one line per stage to outputs/{tid}/STATUS "
         f"(e.g. PROGRESS researching), and finish with a final line DONE, or BLOCKED <reason> if you cannot continue.")
    if revision:
        s += f" This is revision {revision}: read outputs/{tid}/REVIEW.md first and address every point."
    return s

def open_viewer(root, title, log_path):
    if not IS_WIN: return
    ps = (f"$Host.UI.RawUI.WindowTitle='{title}'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
          f"while(-not (Test-Path '{log_path}')){{Start-Sleep 1}}; Get-Content -LiteralPath '{log_path}' -Encoding UTF8 -Tail 60 -Wait")
    subprocess.Popen(["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", ps],
                     creationflags=subprocess.CREATE_NEW_CONSOLE)

def open_roster_viewer(root):
    if not IS_WIN: return
    subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), "status", str(root), "--watch"],
                     creationflags=subprocess.CREATE_NEW_CONSOLE)

def launch(root, plan, task, ts):
    tid = task["id"]
    (root / "outputs" / tid).mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    log = root / "logs" / f"{tid}.log"
    cmd = worker_cmd(plan, task, root, build_prompt(task, ts.get("revision", 0)))
    fh = open(log, "a", encoding="utf-8")
    kw = dict(cwd=root, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
              env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    kw["creationflags" if IS_WIN else "start_new_session"] = (subprocess.CREATE_NO_WINDOW if IS_WIN else True)
    proc = subprocess.Popen(cmd, **kw)
    ts.update(state="running", pid=proc.pid, started=time.time(), last_change=time.time(), last_status="", stall=False)
    emit(root, f"{tid} STARTED pid={proc.pid}" + (f" revision={ts['revision']}" if ts.get("revision") else ""))
    if plan.get("show_windows", True) and not ts.get("viewer"):
        open_viewer(root, f"{plan['project']} {tid}", str(log)); ts["viewer"] = True

def check_deliverables(root, task):
    probs = []
    for name in task.get("deliverables", []):
        f = root / "outputs" / task["id"] / name
        if not f.exists() or f.stat().st_size == 0: probs.append(f"missing {name}")
    need = task.get("min_links", 0)
    if need:
        text = "".join((root / "outputs" / task["id"] / n).read_text(encoding="utf-8", errors="ignore")
                       for n in task.get("deliverables", []) if (root / "outputs" / task["id"] / n).exists())
        n = text.count("http://") + text.count("https://")
        if n < need: probs.append(f"links {n}<{need}")
    need_img = task.get("min_images", 0)
    if need_img:
        out = root / "outputs" / task["id"]
        imgs = [p for p in out.rglob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif")]
        md = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in out.glob("*.md"))
        embedded = sum(1 for p in imgs if p.name in md)
        if len(imgs) < need_img: probs.append(f"images {len(imgs)}<{need_img}")
        elif embedded < need_img: probs.append(f"images referenced in .md {embedded}<{need_img}")
    return probs

# ---------------------------------------------------------------- supervisor
def supervise(root):
    root = Path(root).resolve()
    while True:
        plan = load_plan(root); st = load_state(root)
        tasks = {t["id"]: t for t in plan["tasks"]}
        for tid in tasks: st["tasks"].setdefault(tid, {"state": "queued"})
        # retry requests
        rq = odir(root) / "requeue"
        for f in rq.glob("*") if rq.exists() else []:
            ts = st["tasks"].get(f.name)
            if ts is not None:
                kill_tree(ts.get("pid")); ts.update(state="queued", revision=ts.get("revision", 0) + 1)
                for other in st["tasks"].values():  # give skipped dependents another chance
                    if other["state"] == "skipped": other["state"] = "queued"
                emit(root, f"{f.name} REQUEUED revision={ts['revision']}")
            f.unlink()
        # update running tasks
        for tid, ts in st["tasks"].items():
            if ts["state"] != "running" or tid not in tasks: continue
            cur = read_status(root, tid)
            if cur != ts.get("last_status"):
                ts["last_status"] = cur; ts["last_change"] = time.time(); ts["stall"] = False
                if cur == "DONE":
                    probs = check_deliverables(root, tasks[tid])
                    ts["state"] = "check_failed" if probs else "done"
                    emit(root, f"{tid} CHECK_FAILED {'; '.join(probs)}" if probs else f"{tid} DONE")
                    continue
                if cur.startswith("BLOCKED"):
                    ts["state"] = "blocked"; emit(root, f"{tid} {cur}"); continue
                emit(root, f"{tid} {cur}")
            ts["last_change"] = max(ts["last_change"], newest_mtime(root, tid))
            if not pid_alive(ts.get("pid")):
                ts["state"] = "failed"; emit(root, f"{tid} FAILED worker exited without DONE (see logs/{tid}.log)"); continue
            stall = plan.get("stall_minutes", DEFAULT_STALL_MINUTES)
            if not ts["stall"] and time.time() - ts["last_change"] > stall * 60:
                ts["stall"] = True; emit(root, f"{tid} STALL no file change for {stall} min")
        # schedule queued tasks
        busy = {r for tid, ts in st["tasks"].items() if ts["state"] == "running" for r in tasks.get(tid, {}).get("resources", [])}
        running = sum(ts["state"] == "running" for ts in st["tasks"].values())
        limit = plan.get("max_parallel", 4)
        for tid, task in tasks.items():
            ts = st["tasks"][tid]
            if ts["state"] != "queued": continue
            dep_states = [st["tasks"].get(d, {}).get("state") for d in task.get("depends_on", [])]
            bad = [d for d, s in zip(task.get("depends_on", []), dep_states) if s in ("failed", "blocked", "check_failed", "skipped", "stopped")]
            if bad:
                ts["state"] = "skipped"; emit(root, f"{tid} SKIPPED dependency not done: {', '.join(bad)}"); continue
            if running >= limit or any(s != "done" for s in dep_states): continue
            if busy & set(task.get("resources", [])): continue
            try:
                launch(root, plan, task, ts)
            except OSError as e:
                ts["state"] = "failed"; emit(root, f"{tid} FAILED could not start worker: {e} (set worker_bin in plan.json)"); continue
            running += 1; busy |= set(task.get("resources", []))
        save_state(root, st); write_roster(root, plan, st)
        states = [st["tasks"][t]["state"] for t in tasks]
        if states and all(s in ("done", "blocked", "failed", "check_failed", "skipped") for s in states):
            if not st.get("all_done_emitted"):
                st["all_done_emitted"] = True; save_state(root, st)
                emit(root, "ALL_DONE " + ", ".join(f"{t}={st['tasks'][t]['state']}" for t in tasks))
        else:
            st["all_done_emitted"] = False; save_state(root, st)
        time.sleep(POLL_SECONDS)

def roster_text(root, plan, st):
    rows = [f"Project: {plan['project']}   worker: {plan.get('worker','codex') if not isinstance(plan.get('worker'), dict) else 'custom'}"
            f"   model: {plan['model']} / {plan['effort']}", "",
            f"{'task':<22}{'state':<14}{'last status':<28}{'resources':<14}output"]
    for t in plan["tasks"]:
        ts = st["tasks"].get(t["id"], {"state": "queued"})
        rows.append(f"{t['id']:<22}{ts['state']:<14}{ts.get('last_status','')[:26]:<28}"
                    f"{','.join(t.get('resources', [])) or '-':<14}outputs/{t['id']}/")
    return "\n".join(rows)

def write_roster(root, plan, st):
    (odir(root) / "roster.txt").write_text(roster_text(root, plan, st) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- commands
def cmd_start(root):
    root = Path(root).resolve(); odir(root).mkdir(exist_ok=True)
    plan = load_plan(root)
    for k in ("project", "model", "effort", "tasks"):
        if k not in plan: raise SystemExit(f"plan.json is missing '{k}'")
    for t in plan["tasks"]:
        if not (root / t["brief"]).exists(): raise SystemExit(f"brief not found: {t['brief']}")
    pidf = odir(root) / "supervisor.pid"
    if pidf.exists() and pid_alive(int(pidf.read_text())):
        print("supervisor already running"); print((odir(root) / "roster.txt").read_text(encoding="utf-8")); return
    (odir(root) / "events.log").touch()
    kw = dict(cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=open(odir(root) / "supervisor.err", "a"))
    if IS_WIN: kw["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else: kw["start_new_session"] = True
    sup = subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), "_supervise", str(root)], **kw)
    pidf.write_text(str(sup.pid))
    if plan.get("show_windows", True): open_roster_viewer(root)
    time.sleep(POLL_SECONDS + 2)
    print((odir(root) / "roster.txt").read_text(encoding="utf-8") if (odir(root) / "roster.txt").exists() else "starting...")

def cmd_wait(root, timeout):
    root = Path(root).resolve(); ev = odir(root) / "events.log"; cur = odir(root) / "cursor"
    pos = int(cur.read_text()) if cur.exists() else 0
    deadline = time.time() + timeout if timeout else None
    while True:
        data = ev.read_bytes() if ev.exists() else b""
        if len(data) > pos:
            time.sleep(1); data = ev.read_bytes()  # let simultaneous events batch together
            sys.stdout.write(data[pos:].decode("utf-8", errors="replace")); cur.write_text(str(len(data)))
            return
        if deadline and time.time() > deadline:
            print("TIMEOUT no new events"); return
        time.sleep(WAIT_POLL_SECONDS)

def cmd_status(root, watch):
    root = Path(root).resolve()
    if watch and IS_WIN: os.system(f"title {load_plan(root)['project']} roster")
    while True:
        text = roster_text(root, load_plan(root), load_state(root))
        if not watch: print(text); return
        os.system("cls" if IS_WIN else "clear"); print(time.strftime("%H:%M:%S")); print(text)
        ev = odir(root) / "events.log"
        if ev.exists(): print("\nrecent events:\n" + "".join(ev.read_text(encoding="utf-8").splitlines(True)[-8:]))
        time.sleep(10)

def cmd_retry(root, tid):
    d = odir(Path(root).resolve()) / "requeue"; d.mkdir(parents=True, exist_ok=True); (d / tid).touch()
    print(f"{tid} queued for retry")

def cmd_stop(root):
    root = Path(root).resolve(); st = load_state(root)
    pidf = odir(root) / "supervisor.pid"
    if pidf.exists(): kill_tree(int(pidf.read_text())); pidf.unlink()
    for tid, ts in st["tasks"].items():
        if ts.get("state") == "running": kill_tree(ts.get("pid")); ts["state"] = "stopped"
    save_state(root, st); emit(root, "STOPPED by orchestrator"); print("stopped")

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = a[0]
    if c == "start": cmd_start(a[1])
    elif c == "_supervise": supervise(a[1])
    elif c == "wait": cmd_wait(a[1], float(a[a.index("--timeout") + 1]) if "--timeout" in a else 0)
    elif c == "status": cmd_status(a[1], "--watch" in a)
    elif c == "retry": cmd_retry(a[1], a[2])
    elif c == "stop": cmd_stop(a[1])
    else: print(__doc__); sys.exit(1)
