# 使用官方 Python 运行时作为父镜像
FROM python:3.9-slim-buster

# 设置工作目录
WORKDIR /app

# 将当前目录内容复制到容器的 /app 中
COPY . /app

# 安装项目依赖
RUN pip install --no-cache-dir -r requirements.txt

# 让端口 8000 可供此容器外的环境使用
EXPOSE 8000

# 定义环境变量
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# 运行应用
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]