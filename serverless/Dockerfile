# Omnia · worker serverless para RunPod (flujos de imagen con Krea 2).
# Parte del worker oficial de RunPod para ComfyUI y le añade los nodos
# de los flujos de Omnia, en las mismas versiones que el instalador.
# Los modelos NO van dentro: se leen del volumen de red del pod de Omnia.
FROM runpod/worker-comfyui:5.11.0-base

# Nodos personalizados (commits fijados, igual que Omnia_model_installer)
RUN set -e; cd /comfyui/custom_nodes; \
    add() { git clone --filter=blob:none "$2" "$1" && git -C "$1" checkout --detach "$3"; }; \
    add comfyui-krea2edit             https://github.com/lbouaraba/comfyui-krea2edit.git              86f886dac23013d88996e3a2e99093ba44d322fb; \
    add ComfyUI_Comfyroll_CustomNodes https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git      d78b780ae43fcf8c6b7c6505e6ffb4584281ceca; \
    add ComfyUI-KJNodes               https://github.com/kijai/ComfyUI-KJNodes.git                     8692bc8ef8beaaeee80fd52ba80477dc9e61547b; \
    add ComfyUI-Impact-Subpack        https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git           50c7b71a6a224734cc9b21963c6d1926816a97f1; \
    add ComfyUI-Impact-Pack           https://github.com/ltdrdata/ComfyUI-Impact-Pack.git              429d0159ad429e64d2b3916e6e7be9c22d025c3c; \
    add rgthree-comfy                 https://github.com/rgthree/rgthree-comfy.git                     6b76ee6f2c5a007710b5a16f97c94330d6ecc871; \
    add RES4LYF                       https://github.com/ClownsharkBatwing/RES4LYF.git                 e716cd1cb2c5cff90131bf4914b75b75a0489d48; \
    for r in /comfyui/custom_nodes/*/requirements.txt; do uv pip install --python /opt/venv/bin/python -r "$r"; done

# Comprobación: ComfyUI arranca con todos los nodos (en CPU, sin GPU)
RUN cd /comfyui && timeout 600 python main.py --quick-test-for-ci --cpu

# Los modelos se leen del volumen de red del pod de Omnia.
# En el pod el volumen se monta en /workspace; en serverless, en /runpod-volume.
RUN rm -rf /comfyui/models && ln -s /runpod-volume/runpod-slim/ComfyUI/models /comfyui/models
