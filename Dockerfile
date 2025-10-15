FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Install Git, TeX packages, and cron
RUN apt-get update && apt-get install -y \
    git \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY app.py .
COPY extract_metrics.py .
COPY .streamlit/ ./.streamlit/

# Set up cron job for hourly extraction
RUN echo "0 * * * * cd /app && /usr/local/bin/python3 /app/extract_metrics.py >> /app/data/cron.log 2>&1" > /etc/cron.d/extract-metrics && \
    chmod 0644 /etc/cron.d/extract-metrics && \
    crontab /etc/cron.d/extract-metrics

# Create startup script
RUN echo '#!/bin/bash\n\
# Start cron in background\n\
cron\n\
# Run extraction once on startup\n\
python3 /app/extract_metrics.py\n\
# Start Streamlit\n\
streamlit run app.py' > /app/start.sh && \
    chmod +x /app/start.sh

EXPOSE 8501

CMD ["/app/start.sh"]
