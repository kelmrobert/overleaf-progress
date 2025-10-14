FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Install Git and essential TeX packages
RUN apt-get update && apt-get install -y \
    git \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY app.py .
COPY .streamlit/ ./.streamlit/

EXPOSE 8501

CMD ["streamlit", "run", "app.py"]
