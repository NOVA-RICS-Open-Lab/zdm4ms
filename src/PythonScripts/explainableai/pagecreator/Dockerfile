FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "explainableai_page_creator.py"]

EXPOSE 5008
EXPOSE 7860