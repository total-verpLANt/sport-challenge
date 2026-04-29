# Gunicorn production config
# Workers: 2 * CPU + 1 (I/O-bound Flask app)
workers = 3  # adjust to 2*nproc+1 on prod server

bind = "0.0.0.0:5000"
worker_class = "sync"

# Graceful shutdown: wait up to 30s for in-flight requests
timeout = 30
graceful_timeout = 30
keepalive = 5

# Logging: stdout/stderr so the shell script can redirect to server.log
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Reload on SIGHUP without dropping connections
preload_app = False  # False = workers can be reloaded individually on SIGHUP
