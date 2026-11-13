# Omnia · serverless

Worker de RunPod Serverless para ejecutar los flujos de imagen de Omnia
(Krea 2: imagen, edición, carruseles, conjunto de datos y prueba de LoRA)
pagando solo por cada generación.

- Imagen: `ghcr.io/omniacorporatemd-ux/omnia-serverless:latest`
- Necesita el **mismo volumen de red** que el pod de Omnia: los modelos se
  instalan desde el lanzador del pod y el worker los lee de
  `/runpod-volume/runpod-slim/ComfyUI/models`.
- Solo imágenes: el worker oficial devuelve imágenes, no vídeo. El control
  de movimiento se hace en el pod.

Desde ComfyUI Desktop se lanza con el complemento **Omnia Serverless**.
