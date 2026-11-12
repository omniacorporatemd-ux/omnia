# Omnia · Pod de ComfyUI para RunPod

Imagen propia basada en la oficial `runpod/comfyui` + lanzador de Omnia (puerto 3000) que instala,
por flujo del curso, los modelos y nodos necesarios. Todo se guarda en `/workspace`.

## Cómo se publica la imagen

Cada vez que se sube un cambio a `main`, GitHub Actions construye y publica:

- `ghcr.io/<usuario>/omnia:cuda12.8` → RTX 4090, L40S, A100, H100…
- `ghcr.io/<usuario>/omnia:cuda13.0` → Blackwell: RTX 5090, RTX PRO 6000, B200

Después de la primera publicación: GitHub → tu perfil → Packages → `omnia` → Package settings →
Change visibility → **Public** (para que RunPod pueda descargarla sin contraseña).

## Plantilla de RunPod "Omnia"

| Campo | Valor |
|---|---|
| Nombre | Omnia |
| Imagen | `ghcr.io/<usuario>/omnia:cuda12.8` (y una segunda plantilla "Omnia · Blackwell" con `:cuda13.0`) |
| Puertos HTTP | 3000, 8188, 8888, 8080 · TCP 22 |
| Disco del contenedor | 50 GB |
| Volumen | montado en `/workspace` — recomendado: volumen de red de 100 GB |
| Variable opcional | `OMNIA_CATALOG_URL` = `https://raw.githubusercontent.com/<usuario>/omnia-pod/main/catalog.json` (añade flujos nuevos sin reconstruir la imagen) |
| Visibilidad | Pública |

## Añadir un flujo

Añade una entrada a `catalog.json` (modelos: nombre, carpeta dentro de `models/`, tamaño en GB, URL;
nodos: carpeta y repositorio). Los .json de los flujos del curso **no** van aquí: el repositorio es público.

## Plantilla en Vast.ai (misma imagen)

| Campo | Valor |
|---|---|
| Image Path:Tag | `ghcr.io/<usuario>/omnia:cuda12.8` (o `:cuda13.0` para RTX 50xx / B200) |
| Launch Mode | Docker ENTRYPOINT |
| Docker Options | `-p 3000:3000 -p 8188:8188 -p 8888:8888 -e OPEN_BUTTON_PORT=3000` |
| Disk Space | 80 GB solo imagen · 150 GB con vídeo |
| Volumen (opcional) | montar en `/workspace` para que modelos y creaciones sobrevivan al borrar la máquina (ligado a esa máquina) |
| Visibilidad | Public (el enlace de la plantilla lleva tu `ref_id` de referido) |

Notas para el alumno en Vast:
- Antes de alquilar, mirar el precio de descarga por TB de la máquina: los modelos de vídeo pesan 40–60 GB.
- "Stop" conserva los datos pero sigue cobrando el disco; "Destroy" lo borra todo.
- Si la máquina está ocupada al volver, hay que esperar o copiar los datos a otra.
