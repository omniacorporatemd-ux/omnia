# Omnia · imagen del pod de ComfyUI
# Parte de la imagen oficial de RunPod (ComfyUI, Jupyter, FileBrowser, ComfyUI-Manager)
# y añade el lanzador de Omnia en el puerto 3000.
ARG BASE_IMAGE=runpod/comfyui:cuda12.8
FROM ${BASE_IMAGE}

COPY catalog.json /opt/omnia/app/catalog.json
COPY index.html server.py /opt/omnia/app/launcher/
COPY omnia-entry.sh /omnia-entry.sh
RUN chmod +x /omnia-entry.sh

EXPOSE 3000 8188 8888 8080 22
ENTRYPOINT ["/omnia-entry.sh"]
