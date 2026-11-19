# Workers

## Built-in workers

`"worker": "codex"` runs:

```
codex exec -C <project> -m <model> -c model_reasoning_effort="<effort>" -s danger-full-access --skip-git-repo-check -c web_search="live" "<prompt>"
```

`"worker": "claude"` runs:

```
claude -p "<prompt>" --model <model> --effort <effort> --permission-mode bypassPermissions -n <project>-<id>
```

The script finds `codex` on PATH, then the Codex desktop app's bundled `codex.exe` on Windows. Set `"worker_bin"` in plan.json to point at a specific executable.

## Custom worker

Give the full command with placeholders `{prompt}`, `{model}`, `{effort}`, `{root}`, `{id}`, `{project}`:

```json
"worker": {"cmd": ["gemini", "-m", "{model}", "-p", "{prompt}", "--yolo"]}
```

A worker qualifies when it runs headless from a command line, works in the given folder, and can write files.

## Platform notes

- **Codex on Windows**: use `danger-full-access` (the built-in default). The `workspace-write` sandbox can fail to spawn processes there (error 1385). Briefs keep each worker inside `outputs/<id>/`.
- **Computer use**: tag every computer-use task with resource `screen`; they share one mouse and keyboard and run one at a time.
- **DCC apps** (Maya, Blender, Unreal, Houdini): prefer headless or batch mode (`mayapy`, `blender -b`, `UnrealEditor-Cmd`). Those tasks run in parallel. Tag GUI-driven tasks with the app name as a resource.
- **Log windows**: the script opens UTF-8 log viewers on Windows. On macOS/Linux, follow progress with `tail -f <project>/logs/*.log` and `status <project> --watch`.
- **Desktop apps**: CLI runs share the app's config and session store, so the same model, plugins, and computer-use tools are available.
