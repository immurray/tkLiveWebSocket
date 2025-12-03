## deployment.md 文档

# TikliveTools 部署指南

本文档提供了在各种环境下部署 TikliveTools（TikTok/抖音直播数据采集工具）服务的详细指南。

## 目录

- [基础环境设置](#基础环境设置)
- [使用Docker部署](#使用docker部署)
- [直接在服务器上部署](#直接在服务器上部署)
- [集群部署](#集群部署)
- [使用Nginx反向代理](#使用nginx反向代理)
- [设置系统服务](#设置系统服务)
- [监控与维护](#监控与维护)
- [故障排除](#故障排除)

## 基础环境设置

### 系统要求

- 操作系统：Ubuntu 20.04/22.04 LTS、CentOS 8+、Debian 11+ 或其它现代Linux发行版或Windows 10/11
- CPU：至少2核
- 内存：至少4GB RAM
- 磁盘：至少50GB可用空间
- Python：3.11+ 或更高版本（推荐使用与开发环境相同的版本）

### 安装基础依赖

Ubuntu/Debian:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-dev build-essential git
sudo apt install -y python3-venv  # 可选，使用虚拟环境
```

CentOS/RHEL:
```bash
sudo dnf install -y python3 python3-pip python3-devel git
sudo dnf groupinstall -y "Development Tools"
```

Windows:
```powershell
pip install --upgrade pip
python -m venv venv  # 可选，使用虚拟环境
.\venv\Scripts\activate  # 激活虚拟环境
pip install -r requirements.txt  # 安装依赖
```

## 使用Docker部署

### 1. 准备Docker环境

```bash
# 安装Docker
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker
sudo systemctl start docker

# 安装Docker Compose (可选)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. 创建Dockerfile

在项目根目录创建 `Dockerfile`（或使用项目中已提供的版本）:

```Dockerfile
FROM python:3.11.1-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖列表并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建日志目录并设置权限
RUN mkdir -p logs && chmod 777 logs

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3. 创建docker-compose.yml (可选)

```yaml
version: '3'

services:
  tklivetools:
    build: .
    ports:
      - "8000:8000"
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
```

### 4. 构建并运行Docker容器

使用Docker Compose:
```bash
docker-compose up -d
```

或直接使用Docker:
```bash
docker build -t tklivetools .
docker run -d -p 8000:8000 --env-file .env --name tklivetools tklivetools
```

## 直接在服务器上部署

### 1. 克隆代码库

```bash
git clone https://github.com/TikHubIO/tkliveTools.git
cd tkliveTools
```

### 2. 设置Python虚拟环境(推荐)

```bash
# 确保使用Python 3.11或更高版本
python3 --version

# 如果版本不符，请安装Python 3.11+

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑.env文件设置以下环境变量:
# TIKHUB_API_KEY=""        # 你的TikHub API密钥
# TIKHUB_BASE_URL="https://api.tikhub.io"  # TikHub API基础URL
# WSS_COOKIES=""           # WebSocket连接所需的Cookies
```

### 5. 运行应用

#### 使用screen或tmux(用于测试)

```bash
# 安装screen
sudo apt install screen  # Ubuntu/Debian
sudo dnf install screen  # CentOS/RHEL

# 创建新会话
screen -S tklivetools

# 在screen会话中启动服务
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 3

# 退出screen会话但保持运行: Ctrl+A, 然后按D
# 恢复会话: screen -r tklivetools
```

#### 使用Gunicorn(生产环境)

```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 main:app
```

## 集群部署

集群部署可以显著提高系统的并发处理能力和可用性。以下提供几种集群部署方案：

### 方案一：Docker Swarm 集群部署

#### 1. 初始化Docker Swarm

在主节点执行：
```bash
# 初始化swarm集群
docker swarm init --advertise-addr <主节点IP>

# 获取worker节点加入令牌
docker swarm join-token worker
```

在工作节点执行返回的join命令：
```bash
docker swarm join --token <TOKEN> <主节点IP>:2377
```

#### 2. 创建Docker Stack配置

创建 `docker-stack.yml`:

```yaml
version: '3.8'

services:
  tklivetools:
    image: tklivetools:latest
    deploy:
      replicas: 6  # 根据需要调整副本数量
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      placement:
        constraints:
          - node.role == worker
    ports:
      - target: 8000
        published: 8000
        protocol: tcp
        mode: host
    environment:
      - TIKHUB_API_KEY=${TIKHUB_API_KEY}
      - TIKHUB_BASE_URL=${TIKHUB_BASE_URL}
      - WSS_COOKIES=${WSS_COOKIES}
    volumes:
      - /data/logs:/app/logs
    networks:
      - tklivetools-network

  redis:
    image: redis:7-alpine
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - tklivetools-network

  nginx:
    image: nginx:alpine
    deploy:
      replicas: 2
      placement:
        constraints:
          - node.role == manager
    ports:
      - "80:80"
      - "443:443"
    configs:
      - source: nginx_config
        target: /etc/nginx/nginx.conf
    networks:
      - tklivetools-network
    depends_on:
      - tklivetools

networks:
  tklivetools-network:
    driver: overlay
    attachable: true

volumes:
  redis_data:

configs:
  nginx_config:
    external: true
```

#### 3. 创建Nginx负载均衡配置

创建 `nginx-cluster.conf`:

```nginx
upstream tklivetools_backend {
    least_conn;  # 最少连接数负载均衡
    server tklivetools:8000 max_fails=3 fail_timeout=30s;
    # Docker Swarm会自动处理服务发现和负载均衡
}

server {
    listen 80;
    server_name your-domain.com;

    # WebSocket连接的特殊处理
    location /ws/ {
        proxy_pass http://tklivetools_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;

        # 会话保持 - 对于WebSocket很重要
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }

    # API请求负载均衡
    location / {
        proxy_pass http://tklivetools_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 健康检查端点
    location /health {
        access_log off;
        proxy_pass http://tklivetools_backend/;
        proxy_connect_timeout 2s;
        proxy_read_timeout 2s;
    }
}
```

#### 4. 部署集群

```bash
# 创建nginx配置
docker config create nginx_config nginx-cluster.conf

# 部署stack
docker stack deploy -c docker-stack.yml tklivetools-cluster

# 查看服务状态
docker service ls
docker service ps tklivetools-cluster_tklivetools
```

### 方案二：Kubernetes 集群部署

#### 1. 创建Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tklivetools
```

#### 2. 创建ConfigMap和Secret

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tklivetools-config
  namespace: tklivetools
data:
  TIKHUB_BASE_URL: "https://api.tikhub.io"

---
apiVersion: v1
kind: Secret
metadata:
  name: tklivetools-secret
  namespace: tklivetools
type: Opaque
data:
  TIKHUB_API_KEY: <base64编码的API密钥>
  WSS_COOKIES: <base64编码的Cookies>
```

#### 3. 创建Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tklivetools
  namespace: tklivetools
spec:
  replicas: 6  # 根据需要调整
  selector:
    matchLabels:
      app: tklivetools
  template:
    metadata:
      labels:
        app: tklivetools
    spec:
      containers:
      - name: tklivetools
        image: tklivetools:latest
        ports:
        - containerPort: 8000
        env:
        - name: TIKHUB_API_KEY
          valueFrom:
            secretKeyRef:
              name: tklivetools-secret
              key: TIKHUB_API_KEY
        - name: TIKHUB_BASE_URL
          valueFrom:
            configMapKeyRef:
              name: tklivetools-config
              key: TIKHUB_BASE_URL
        - name: WSS_COOKIES
          valueFrom:
            secretKeyRef:
              name: tklivetools-secret
              key: WSS_COOKIES
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: logs
        emptyDir: {}
```

#### 4. 创建Service和Ingress

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: tklivetools-service
  namespace: tklivetools
spec:
  selector:
    app: tklivetools
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tklivetools-ingress
  namespace: tklivetools
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "86400"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "86400"
    nginx.ingress.kubernetes.io/websocket-services: "tklivetools-service"
spec:
  rules:
  - host: your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: tklivetools-service
            port:
              number: 80
```

#### 5. 部署到Kubernetes

```bash
# 应用配置
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml

# 查看部署状态
kubectl get pods -n tklivetools
kubectl get services -n tklivetools
kubectl describe ingress tklivetools-ingress -n tklivetools
```

### 集群监控和管理

#### 1. 使用Prometheus监控

创建 `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'tklivetools'
    static_configs:
      - targets: ['192.168.1.11:8000', '192.168.1.12:8000', '192.168.1.13:8000']
```

#### 2. 健康检查脚本

```bash
#!/bin/bash
# health_check.sh

SERVERS=("192.168.1.11:8000" "192.168.1.12:8000" "192.168.1.13:8000")

for server in "${SERVERS[@]}"; do
    if curl -f -s "http://$server/" > /dev/null; then
        echo "$(date): $server - 健康"
    else
        echo "$(date): $server - 故障，尝试重启服务"
        # 这里可以添加自动重启逻辑
    fi
done
```

#### 3. 自动扩缩容脚本

```bash
#!/bin/bash
# auto_scale.sh

# 获取当前连接数
CONNECTIONS=$(redis-cli get "total_connections" 2>/dev/null || echo "0")

if [ "$CONNECTIONS" -gt 1000 ]; then
    echo "连接数过高，启动额外实例"
    # 启动新实例的逻辑
    docker service scale tklivetools-cluster_tklivetools=8
elif [ "$CONNECTIONS" -lt 200 ]; then
    echo "连接数较低，减少实例"
    # 减少实例的逻辑
    docker service scale tklivetools-cluster_tklivetools=4
fi
```

### 性能优化建议

1. **连接保持策略**：
   - 使用 ip_hash 确保WebSocket连接的会话保持
   - 配置适当的连接超时时间

2. **数据共享**：
   - 使用Redis存储共享状态
   - 实现分布式锁避免冲突

3. **监控指标**：
   - 监控每个节点的CPU、内存使用率
   - 监控WebSocket连接数和消息处理速度
   - 设置告警阈值

4. **故障转移**：
   - 配置健康检查
   - 自动故障转移和恢复
   - 数据备份和恢复策略

## 使用Nginx反向代理

### 1. 安装Nginx

```bash
# Ubuntu/Debian
sudo apt install -y nginx

# CentOS/RHEL
sudo dnf install -y nginx
```

### 2. 创建Nginx配置文件

```bash
sudo nano /etc/nginx/sites-available/tklivetools
```

添加以下配置:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或服务器IP

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;  # WebSocket连接保持时间
    }
}
```

### 3. 启用站点配置

Ubuntu/Debian:
```bash
sudo ln -s /etc/nginx/sites-available/tklivetools /etc/nginx/sites-enabled/
sudo nginx -t  # 测试配置
sudo systemctl restart nginx
```

CentOS/RHEL:
```bash
sudo cp /etc/nginx/sites-available/tklivetools /etc/nginx/conf.d/tklivetools.conf
sudo nginx -t  # 测试配置
sudo systemctl restart nginx
```

## 设置系统服务

### 1. 创建systemd服务文件

```bash
sudo nano /etc/systemd/system/tklivetools.service
```

添加以下内容:

```ini
[Unit]
Description=TikliveTools Service
After=network.target

[Service]
User=your-username  # 替换为你的用户名
Group=your-username  # 替换为你的用户名
WorkingDirectory=/path/to/tkliveTools  # 替换为项目实际路径
Environment="PATH=/path/to/tkliveTools/venv/bin"
EnvironmentFile=/path/to/tkliveTools/.env
ExecStart=/path/to/tkliveTools/venv/bin/gunicorn -w 3 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 main:app
Restart=always
RestartSec=5
StartLimitInterval=0

[Install]
WantedBy=multi-user.target
```

### 2. 启用并启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable tklivetools
sudo systemctl start tklivetools
sudo systemctl status tklivetools
```

## 监控与维护

### 查看日志

```bash
# 查看系统服务日志
sudo journalctl -u tklivetools

# 如果使用Docker
docker logs -f tklivetools

# 如果使用Docker Swarm
docker service logs -f tklivetools-cluster_tklivetools

# 如果使用Kubernetes
kubectl logs -f deployment/tklivetools -n tklivetools
```

### 集群监控

```bash
# Docker Swarm集群状态
docker node ls
docker service ls
docker service ps tklivetools-cluster_tklivetools

# Kubernetes集群状态
kubectl get nodes
kubectl get pods -n tklivetools -o wide
kubectl top pods -n tklivetools

# Redis监控（如果使用Redis做状态共享）
redis-cli info replication
redis-cli monitor
```

### 资源监控

```bash
# 安装htop进行系统资源监控
sudo apt install htop  # Ubuntu/Debian
sudo dnf install htop  # CentOS/RHEL

# 运行htop
htop
```

## 故障排除

### 常见问题

1. **服务无法启动**
   - 检查环境变量是否正确设置
   - 检查日志文件查看详细错误信息
   - 验证Python版本和依赖安装

2. **WebSocket连接问题**
   - 确保Nginx配置正确设置了WebSocket代理
   - 检查防火墙是否允许WebSocket连接
   - 验证客户端WebSocket URL格式

3. **获取TikTok/抖音直播消息失败**
   - 检查TIKHUB_API_KEY是否有效
   - 确认提供的直播房间ID是否正确
   - 检查WSS_COOKIES配置是否正确
   - 查看日志中的详细错误信息

4. **集群相关问题**
   - WebSocket连接断开：检查负载均衡器的会话保持配置
   - 服务发现失败：验证Docker Swarm或Kubernetes的网络配置
   - Redis连接问题：检查Redis服务是否正常运行
   - 负载不均衡：调整负载均衡算法或增加服务实例

### 性能优化

1. **消息处理优化**
   - 所有消息处理方法都使用 `@classmethod` 装饰器提高性能
   - 统一的错误处理机制减少重复代码
   - 标准化的返回格式便于客户端处理
   - 详细的日志记录便于调试和监控

2. **系统资源优化**
   - 使用异步任务队列处理大量消息
   - 考虑使用Redis存储临时数据和消息缓存
   - 合理配置 uvicorn workers 数量（推荐使用 CPU 核心数）
   - 在集群环境中，使用Redis进行状态共享和会话管理

3. **网络优化**
   - 配置适当的 WebSocket 超时时间
   - 使用 CDN 加速静态资源访问
   - 优化 Nginx 配置以提高并发处理能力
   - 集群部署时使用合适的负载均衡策略

4. **集群优化**
   - 使用容器编排工具（Docker Swarm或Kubernetes）进行自动化管理
   - 配置水平自动扩缩容（HPA）
   - 实施滚动更新策略，确保零停机部署
   - 使用服务网格（如Istio）进行更高级的流量管理

### 消息处理配置

服务支持以下TikTok/抖音直播消息类型的实时处理：

| 消息类型 | 功能描述 | 性能特点 |
|---------|----------|----------|
| `WebcastChatMessage` | 聊天消息处理 | 高频处理，优化解析速度 |
| `WebcastGiftMessage` | 礼物消息处理 | 包含价值计算，需要准确性 |
| `WebcastLikeMessage` | 点赞消息处理 | 超高频处理，批量优化 |
| `WebcastMemberMessage` | 用户进入处理 | 中频处理，用户信息解析 |
| `WebcastSocialMessage` | 关注消息处理 | 低频处理，社交动作记录 |
| `WebcastRoomUserSeqMessage` | 观众排行榜 | 定期更新，排序优化 |
| `WebcastOecLiveShoppingMessage` | 购物消息处理 | 电商集成，事务安全 |

所有消息处理都具备：
- 空数据检查和验证
- 异常捕获和错误处理
- 详细的日志记录
- 统一的返回格式

### 基本使用方法

启动服务后，可以通过以下方式连接：

1. **WebSocket连接**：
   ```
   ws://localhost:8000/ws/{room_id}
   ```
   其中 `{room_id}` 是TikTok/抖音直播间ID

2. **API接口**：
   ```
   GET http://localhost:8000/
   ```
   返回服务状态信息

3. **日志查看**：
   所有日志文件存储在 `logs/` 目录下，按日期和时间命名
