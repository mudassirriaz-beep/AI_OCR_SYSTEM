FROM paddlepaddle/paddle:3.0.0-gpu-cuda11.8-cudnn8.9-trt8.6

WORKDIR /app

RUN apt-get update && apt-get install -y libgl1-mesa-glx && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -i https://mirror.baidu.com/pypi/simple -r requirements.txt

RUN pip install --no-cache-dir --default-timeout=100 -i https://mirror.baidu.com/pypi/simple --upgrade paddleocr

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]