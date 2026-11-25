# AZ Email – trang soạn email gửi key bản quyền (LaptopAZ)
# OCR: PaddleOCR (Apache-2.0) chạy offline trên CPU của server. GPU NVIDIA: xem README (Dockerfile.gpu).
FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir paddlepaddle==3.0.0 paddleocr==2.10.0 pillow==11.0.0

RUN useradd -r -m -u 10001 azmail
USER azmail
# Tải sẵn mô hình OCR lúc build → khi chạy không cần Internet, ảnh không rời server
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=False, lang='en', show_log=False)"

WORKDIR /srv/az-email
COPY --chown=azmail app/ app/
USER root
RUN mkdir -p /srv/az-email/data && chown azmail /srv/az-email/data
USER azmail

ENV HOST=0.0.0.0 PORT=8889 DATA_DIR=/srv/az-email/data OCR_ENGINE=paddle PYTHONUNBUFFERED=1
EXPOSE 8889
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8889/healthz')" || exit 1
CMD ["python", "app/web.py"]
