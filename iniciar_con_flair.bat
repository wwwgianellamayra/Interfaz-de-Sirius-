@echo off
setlocal
set ROOT=%~dp0
set FLAIR_PY=%ROOT%..\FLAIR-1\.venv\Scripts\python.exe
if not exist "%FLAIR_PY%" (
  echo No se encontro el entorno FLAIR en ..\FLAIR-1\.venv
  echo Revisa la ubicacion del proyecto o ejecuta app.py con tu Python de FLAIR.
  pause
  exit /b 1
)
"%FLAIR_PY%" -m pip install Flask==3.1.1
"%FLAIR_PY%" "%ROOT%app.py"
pause
