# SIRIUS · Dashboard con FLAIR integrado

Esta versión procesa imágenes RGB con el modelo **FLAIR DeepLabV3 + ResNet34** y muestra:

- imagen original;
- overlay de segmentación;
- porcentaje de área verde;
- porcentaje de área urbana;
- porcentaje interno de otros;
- historial de capturas procesadas.

## Ubicación recomendada

Coloca la carpeta así:

```text
SIRIUS_ML/
├── FLAIR-1/
├── models/
│   └── FLAIR-INC_rgb_15cl_resnet34-deeplabv3_weights.pth
└── sirius_dashboard_ml_integrado/
```

Copia también el archivo de pesos dentro de esta carpeta si deseas un proyecto autocontenido:

```text
sirius_dashboard_ml_integrado/models/FLAIR-INC_rgb_15cl_resnet34-deeplabv3_weights.pth
```

Otra opción es definir la variable `SIRIUS_MODEL_PATH` con la ruta absoluta del `.pth`.

## Ejecución recomendada con el entorno FLAIR

Desde PowerShell:

```powershell
cd C:\Users\TuUSUARIO\Downloads\SIRIUS_ML\sirius_dashboard_ml_integrado
..\FLAIR-1\.venv\Scripts\python.exe -m pip install Flask==3.1.1
..\FLAIR-1\.venv\Scripts\python.exe app.py
```

Luego abre:

```text
http://127.0.0.1:5000
```

## Modelo fuera de la carpeta

Si deseas mantener los pesos en `SIRIUS_ML/models`, ejecuta:

```powershell
$env:SIRIUS_MODEL_PATH="C:\Users\Nela\Downloads\SIRIUS_ML\models\FLAIR-INC_rgb_15cl_resnet34-deeplabv3_weights.pth"
..\FLAIR-1\.venv\Scripts\python.exe app.py
```

## Uso

1. Pulsa **Seleccionar imagen**.
2. Escoge un JPG o PNG cenital.
3. Pulsa **Analizar con FLAIR**.
4. Espera la inferencia en CPU.
5. Alterna entre **original** y **segmentación**.

Las imágenes se guardan localmente en `static/uploads` y los resultados en `static/results`.
