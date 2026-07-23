# SIRIUS · Estación Terrena

Interfaz web local para visualizar telemetría del CubeSat SIRIUS.

## Requisitos

- Python 3.10 o superior
- Visual Studio Code
- Git

## Instalación en Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abrir en el navegador:

```text
http://127.0.0.1:5000
```

## Estructura

```text
app.py                 Servidor Flask y base SQLite
templates/index.html   Interfaz
static/css/styles.css  Estilos visuales SIRIUS
static/js/dashboard.js Lógica y gráficas
data/sirius.db         Base local, se crea automáticamente
```

## Estado actual

La primera versión usa un simulador de telemetría. Luego se reemplazará la función
`simulated_packet()` por lectura serial mediante PySerial desde el receptor LoRa.

## Subir cambios al repositorio

```powershell
git add .
git commit -m "feat: crear dashboard local de SIRIUS"
git push origin main
```
