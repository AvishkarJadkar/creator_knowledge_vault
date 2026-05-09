import multiprocessing
import os

# Workers: (2 × CPU cores) + 1 is the standard formula.
# Railway's free tier has 1 vCPU, so 3 workers is optimal.
workers = 3
threads = 2                   # 2 threads per worker = 6 concurrent requests
worker_class = "gthread"      # Thread-based (better for I/O-heavy AI calls)
timeout = 120                 # 2-minute timeout (covers slow AI responses)
graceful_timeout = 30         # Give workers time to finish in-progress requests
keepalive = 5                 # Keep connections alive for 5 seconds
max_requests = 500            # Recycle workers to prevent memory leaks
max_requests_jitter = 50      # Randomize recycling to avoid simultaneous restarts
preload_app = True            # Load app once in master, fork workers (saves RAM)

# Bind: Railway injects $PORT automatically, we default to 8000 for local test
port = os.environ.get("PORT", "8000")
bind = f"0.0.0.0:{port}"

accesslog = "-"               # Log to stdout (Railway captures this)
errorlog = "-"                # Log errors to stdout
loglevel = "info"
