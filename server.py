#!/usr/bin/env python3
"""Omnia · lanzador de flujos para ComfyUI en RunPod.

Servidor de una sola página (solo librería estándar) que corre junto a la
imagen oficial runpod/comfyui. Instala, por flujo, los modelos y nodos que
indica catalog.json. Todo se guarda en /workspace, así que si el pod usa un
volumen de red, nada se pierde al apagarlo.
"""
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("OMNIA_PORT", "3000"))
WORKSPACE = os.environ.get("OMNIA_WORKSPACE", "/workspace")
COMFY_DIR = os.environ.get("COMFYUI_DIR", os.path.join(WORKSPACE, "runpod-slim", "ComfyUI"))
MODELS_DIR = os.path.join(COMFY_DIR, "models")
NODES_DIR = os.path.join(COMFY_DIR, "custom_nodes")
VENV_PY = os.path.join(COMFY_DIR, ".venv-cu128", "bin", "python")
PIP_CONSTRAINT = "/opt/comfyui-runtime-constraints.txt"
CATALOG_PATH = os.environ.get("OMNIA_CATALOG", os.path.join(HERE, "..", "catalog.json"))
STATE_PATH = os.path.join(WORKSPACE, "omnia", "estado.json")
COMFY_LOCAL = os.environ.get("COMFY_LOCAL_URL", "http://127.0.0.1:8188")
CHUNK = 4 * 1024 * 1024

lock = threading.Lock()
jobs = {}  # id -> {"state", "done", "total", "file", "log": [...], "error"}


def load_catalog():
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"installed": {}, "needs_restart": False}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def file_path(entry):
    return os.path.join(MODELS_DIR, entry["dir"], entry["name"])


def wf_installed(wf):
    files_ok = all(os.path.isfile(file_path(f)) for f in wf.get("files", []))
    nodes_ok = all(os.path.isdir(os.path.join(NODES_DIR, n["name"])) for n in wf.get("nodes", []))
    return files_ok and nodes_ok


def log(job, msg):
    job["log"].append(time.strftime("%H:%M:%S ") + msg)
    del job["log"][:-60]


def auth_headers(url):
    headers = {"User-Agent": "omnia-launcher/1.0"}
    if "huggingface.co" in url and os.environ.get("HF_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["HF_TOKEN"]
    if "civitai.com" in url and os.environ.get("CIVITAI_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["CIVITAI_TOKEN"]
    return headers


def download(job, entry):
    """Descarga reanudable: escribe en .part y continúa con Range si ya existe."""
    dest = file_path(entry)
    if os.path.isfile(dest):
        log(job, "Ya estaba: " + entry["name"])
        job["done"] += int(entry.get("size_gb", 0) * 1e9)
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    base = job["done"]
    for attempt in range(1, 6):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        headers = auth_headers(entry["url"])
        if have:
            headers["Range"] = "bytes=%d-" % have
        req = urllib.request.Request(entry["url"], headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if have and r.status != 206:  # el servidor no admite reanudar: empezar de cero
                    have = 0
                mode = "ab" if have else "wb"
                job["file"] = entry["name"]
                log(job, ("Reanudando " if have else "Descargando ") + entry["name"])
                job["done"] = base + have
                with open(part, mode) as out:
                    while True:
                        buf = r.read(CHUNK)
                        if not buf:
                            break
                        out.write(buf)
                        job["done"] += len(buf)
            os.replace(part, dest)
            log(job, "Listo: " + entry["name"])
            return
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            log(job, "Corte en %s (%s). Reintento %d/5…" % (entry["name"], e, attempt))
            time.sleep(min(30, 3 * attempt))
    raise RuntimeError("No se pudo descargar " + entry["name"])


def install_node(job, node):
    target = os.path.join(NODES_DIR, node["name"])
    if os.path.isdir(target):
        log(job, "Nodo ya instalado: " + node["name"])
        return False
    os.makedirs(NODES_DIR, exist_ok=True)
    log(job, "Instalando nodo " + node["name"])
    subprocess.run(["git", "clone", "--depth", "1", node["repo"], target], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    req = os.path.join(target, "requirements.txt")
    py = VENV_PY if os.path.exists(VENV_PY) else "python3"
    if os.path.isfile(req):
        env = dict(os.environ)
        if os.path.isfile(PIP_CONSTRAINT):
            env["PIP_CONSTRAINT"] = PIP_CONSTRAINT  # no tocar torch de la imagen
        cmd = [py, "-m", "pip", "install", "-q", "-r", req]
        if node.get("extra_index"):
            cmd += ["--extra-index-url", node["extra_index"]]
        r = subprocess.run(cmd, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if r.returncode != 0:
            log(job, "Aviso: dependencias de %s con errores: %s" % (node["name"], r.stdout[-300:]))
    return True


def run_install(wf):
    job = jobs[wf["id"]]
    try:
        total = int(sum(f.get("size_gb", 0) for f in wf.get("files", [])) * 1e9)
        job.update(state="running", done=0, total=total, error=None)
        free = shutil.disk_usage(WORKSPACE).free
        missing = sum(int(f.get("size_gb", 0) * 1e9) for f in wf.get("files", []) if not os.path.isfile(file_path(f)))
        if missing > free:
            raise RuntimeError("Falta espacio: se necesitan %.1f GB y quedan %.1f GB libres en el volumen."
                               % (missing / 1e9, free / 1e9))
        new_nodes = False
        for node in wf.get("nodes", []):
            new_nodes = install_node(job, node) or new_nodes
        for entry in wf.get("files", []):
            download(job, entry)
        with lock:
            st = load_state()
            st["installed"][wf["id"]] = time.strftime("%Y-%m-%d %H:%M")
            st["needs_restart"] = st.get("needs_restart", False) or new_nodes
            save_state(st)
        job.update(state="done", file=None, done=total)
        log(job, "Flujo instalado." + (" Reinicia ComfyUI para cargar los nodos nuevos." if new_nodes else ""))
    except Exception as e:  # el error se enseña en la página
        job.update(state="error", error=str(e))
        log(job, "Error: " + str(e))


def comfy_ready():
    try:
        with urllib.request.urlopen(COMFY_LOCAL + "/system_stats", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def restart_comfy():
    """Usa el reinicio de ComfyUI-Manager (ya viene en la imagen oficial)."""
    for path in ("/api/manager/reboot", "/manager/reboot", "/v2/manager/reboot"):
        try:
            urllib.request.urlopen(COMFY_LOCAL + path, timeout=5)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            break
        except Exception:
            break  # la conexión se corta cuando se reinicia: es lo esperado
    with lock:
        st = load_state()
        st["needs_restart"] = False
        save_state(st)


def status_payload():
    cat = load_catalog()
    st = load_state()
    usage = shutil.disk_usage(WORKSPACE if os.path.isdir(WORKSPACE) else "/")
    pod = os.environ.get("RUNPOD_POD_ID")
    out = []
    for wf in cat["workflows"]:
        j = jobs.get(wf["id"], {})
        out.append({
            "id": wf["id"], "n": wf.get("n"), "name": wf["name"], "module": wf.get("module", ""),
            "description": wf.get("description", ""),
            "size_gb": round(sum(f.get("size_gb", 0) for f in wf.get("files", [])), 1),
            "files": [{"name": f["name"], "dir": f["dir"], "ok": os.path.isfile(file_path(f))} for f in wf.get("files", [])],
            "nodes": [n["name"] for n in wf.get("nodes", [])],
            "installed": wf_installed(wf),
            "job": {k: j.get(k) for k in ("state", "done", "total", "file", "error")} if j else None,
            "log": j.get("log", [])[-8:] if j else [],
        })
    return {
        "workflows": out,
        "comfy_ready": comfy_ready(),
        "comfy_url": ("https://%s-8188.proxy.runpod.net" % pod) if pod else "http://localhost:8188",
        "needs_restart": st.get("needs_restart", False),
        "disk": {"free_gb": round(usage.free / 1e9, 1), "total_gb": round(usage.total / 1e9, 1)},
        "workspace": WORKSPACE,
        "persistent": os.path.ismount(WORKSPACE),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self.send(200, f.read(), "text/html; charset=utf-8")
        if self.path == "/api/status":
            return self.send(200, status_payload())
        self.send(404, {"error": "No encontrado"})

    def do_POST(self):
        if self.path.startswith("/api/install/"):
            wid = self.path.rsplit("/", 1)[-1]
            wf = next((w for w in load_catalog()["workflows"] if w["id"] == wid), None)
            if not wf:
                return self.send(404, {"error": "Flujo desconocido"})
            with lock:
                if jobs.get(wid, {}).get("state") == "running":
                    return self.send(409, {"error": "Ya se está instalando"})
                jobs[wid] = {"state": "running", "done": 0, "total": 0, "file": None, "log": [], "error": None}
            threading.Thread(target=run_install, args=(wf,), daemon=True).start()
            return self.send(202, {"ok": True})
        if self.path == "/api/restart-comfy":
            threading.Thread(target=restart_comfy, daemon=True).start()
            return self.send(202, {"ok": True})
        self.send(404, {"error": "No encontrado"})


if __name__ == "__main__":
    os.makedirs(os.path.join(WORKSPACE, "omnia"), exist_ok=True)
    print("Omnia · lanzador en el puerto %d (ComfyUI en %s)" % (PORT, COMFY_DIR), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
