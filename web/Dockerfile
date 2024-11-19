# 使用官方 Python 运行时作为父镜像
FROM python:3.9-slim-buster

# 设置工作目录
WORKDIR /app

# 将当前目录内容复制到容器的 /app 中
COPY . /app

# 安装编译工具和依赖
RUN apt-get update && \
    apt-get install -y build-essential wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装 TA-Lib
RUN tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib-0.4.0-src.tar.gz ta-lib/

# 安装 Python 依赖
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# 让端口 8000 可供此容器外的环境使用
EXPOSE 8000

# 定义环境变量
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# 运行应用
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
