FROM python:3.11-slim

WORKDIR /app

# System dependencies for OpenCV and image processing
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU build first (smaller image, no GPU needed)
RUN pip install --no-cache-dir \
    torch==2.2.2 \
    torchvision==0.17.2 \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Models must be mounted at runtime — not baked into image
# docker run -v /path/to/models:/app/models ...
VOLUME ["/app/models"]

EXPOSE 5000

CMD ["python", "app.py"]
