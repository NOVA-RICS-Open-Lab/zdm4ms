FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

VOLUME ["/app/data"]

CMD ["python", "aasx_aux.py"]