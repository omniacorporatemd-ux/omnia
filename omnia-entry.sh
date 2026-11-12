#!/bin/bash
# Omnia · arranque del pod.
# 1. Arranca el lanzador de Omnia (puerto 3000) en segundo plano.
#    Si OMNIA_CATALOG_URL está definida, descarga el catálogo más reciente
#    (así se añaden flujos nuevos sin reconstruir la imagen).
# 2. Cede el control al /start.sh de la imagen oficial (ComfyUI, Jupyter, FileBrowser).
APP=/opt/omnia/app
mkdir -p /workspace/omnia

if [ -n "$OMNIA_CATALOG_URL" ]; then
    if curl -fsSL --max-time 30 "$OMNIA_CATALOG_URL" -o /tmp/omnia-catalog.json \
       && python3 -c "import json;json.load(open('/tmp/omnia-catalog.json'))"; then
        cp /tmp/omnia-catalog.json "$APP/catalog.json"
        echo "[Omnia] Catálogo actualizado"
    else
        echo "[Omnia] No se pudo actualizar el catálogo; uso el de la imagen"
    fi
fi

nohup python3 "$APP/launcher/server.py" > /workspace/omnia/launcher.log 2>&1 &
echo "[Omnia] Lanzador en el puerto 3000"

exec /start.sh "$@"
