#!/usr/bin/env bash
set -e

echo "🚀 开始部署汽车行业舆情监控系统..."

echo "📁 创建部署目录 /opt/weibo-hotsearch ..."
sudo mkdir -p /opt/weibo-hotsearch

echo "🛑 停止旧服务（如果存在）..."
sudo systemctl stop weibo-monitor.service 2>/dev/null || true
sudo systemctl stop car-monitor-v2.service 2>/dev/null || true

echo "📦 复制 system/ 源码到部署目录..."
sudo cp -r system /opt/weibo-hotsearch/

echo "📦 复制根目录入口文件..."
if [ -f "run.sh" ]; then sudo cp run.sh /opt/weibo-hotsearch/; fi
if [ -f ".env" ]; then sudo cp .env /opt/weibo-hotsearch/; fi

echo "📥 创建虚拟环境 ..."
sudo python3 -m venv /opt/weibo-hotsearch/venv

echo "📥 安装 Python 依赖 ..."
sudo /opt/weibo-hotsearch/venv/bin/pip install --upgrade pip -q
sudo /opt/weibo-hotsearch/venv/bin/pip install -r /opt/weibo-hotsearch/system/requirements.txt

echo "📁 创建业务目录 ..."
sudo mkdir -p /opt/weibo-hotsearch/data
sudo mkdir -p /opt/weibo-hotsearch/logs

echo "⚙️ 配置系统服务 ..."
sudo cp /opt/weibo-hotsearch/system/services/weibo-monitor.service /etc/systemd/system/
sudo cp /opt/weibo-hotsearch/system/services/car-monitor-v2.service /etc/systemd/system/

echo "🔄 重载系统服务配置 ..."
sudo systemctl daemon-reload

echo "🚀 启动服务 ..."
sudo systemctl enable weibo-monitor.service
sudo systemctl start weibo-monitor.service
sudo systemctl enable car-monitor-v2.service
sudo systemctl start car-monitor-v2.service

sleep 3

echo ""
echo "========================================="
echo "📊 服务状态检查"
echo "========================================="
sudo systemctl status car-monitor-v2.service --no-pager || true
sudo systemctl status weibo-monitor.service --no-pager || true

echo ""
echo "✅ 部署完成！"
echo ""
echo "常用命令："
echo "  查看 V2 状态:     sudo systemctl status car-monitor-v2"
echo "  查看 V1 状态:     sudo systemctl status weibo-monitor"
echo "  查看日志:         tail -f /opt/weibo-hotsearch/logs/monitor.log"
echo "  重启 V2:          sudo systemctl restart car-monitor-v2"
echo "  重启 V1:          sudo systemctl restart weibo-monitor"
echo "  停止全部:         sudo systemctl stop weibo-monitor car-monitor-v2"
