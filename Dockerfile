FROM python:3.11-slim

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt
RUN python -m spacy download en_core_web_lg

COPY . .

ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
