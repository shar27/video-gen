import os

# Gunicorn configuration for video processing
# Video processing can take several minutes

port = os.environ.get("PORT", "8080")
bind = f"0.0.0.0:{port}"
workers = 1
threads = 1
timeout = 300  # 5 minutes - video processing takes time
graceful_timeout = 300
keepalive = 5

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
capture_output = True