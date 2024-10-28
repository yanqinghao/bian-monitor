import multiprocessing

bind = "0.0.0.0:8000"  # 绑定的IP和端口
workers = multiprocessing.cpu_count() * 2 + 1  # 工作进程数
threads = 2  # 每个工作进程的线程数
worker_class = "gthread"  # 使用线程工作类
timeout = 30  # 请求超时时间（秒）
keepalive = 2  # 在 keep-alive 连接上等待请求的秒数

# 日志设置
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"

# 守护进程设置
daemon = True