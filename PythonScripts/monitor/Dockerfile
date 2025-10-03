FROM python:3.12-slim

WORKDIR /app

COPY . /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

ADD monitor_aux.py .

CMD ["python", "./monitor_aux.py"]