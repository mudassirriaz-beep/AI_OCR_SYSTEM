@echo off
echo Starting SLM server (model.gguf) on port 8080...
cd /d "%~dp0"
python -m llama_cpp.server --model model.gguf --port 8080 --n_ctx 2048 --n_threads 4
pause
