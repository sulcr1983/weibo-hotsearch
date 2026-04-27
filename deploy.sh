#!/bin/bash

echo "🚀 开始部署微博热搜监控系统..."

# 创建目标目录
echo "📁 创建部署目录 /opt/weibo-hotsearch ..."
sudo mkdir -p /opt/weibo-hotsearch

# 复制所有代码文件
echo "📦 复制代码到部署目录 ..."
sudo cp -r ./* /opt/weibo-hotsearch/

# 安装 Python 依赖（使用虚拟环境，避免污染系统环境）
echo "📥 创建虚拟环境 ..."
sudo python3 -m venv /opt/weibo-hotsearch/venv

echo "📥 安装 Python 依赖 ..."
sudo /opt/weibo-hotsearch/venv/bin/pip install --upgrade pip
sudo /opt/weibo-hotsearch/venv/bin/pip install -r /opt/weibo-hotsearch/requirements.txt

# 创建 logs 目录
echo "📁 创建日志目录 ..."
sudo mkdir -p /opt/weibo-hotsearch/logs

# 复制服务文件
echo "⚙️ 配置系统服务 ..."
sudo cp /opt/weibo-hotsearch/weibo-monitor.service /etc/systemd/system/

# 重新加载 systemd 配置
echo "🔄 重载系统服务配置 ..."
sudo systemctl daemon-reload

# 启用并启动服务
echo "🚀 启动服务 ..."
sudo systemctl enable weibo-monitor.service
sudo systemctl restart weibo-monitor.service

# 等待服务启动
sleep 3

# 显示服务状态
echo ""
echo "========================================="
echo "📊 服务状态检查"
echo "========================================="
sudo systemctl status weibo-monitor.service --no-pager || true

echo ""
echo "========================================="
echo "📋 最近日志（前10行）"
echo "========================================="
if [ -f /opt/weibo-hotsearch/logs/monitor.log ]; then
    tail -n 10 /opt/weibo-hotsearch/logs/monitor.log || echo "暂无日志"
else
    echo "日志文件尚未生成"
fi

echo ""
echo "✅ 部署完成！"
echo ""
echo "常用命令："
echo "  查看状态: sudo systemctl status weibo-monitor"
echo "  查看日志: tail -f /opt/weibo-hotsearch/logs/monitor.log"
echo "  重启服务: sudo systemctl restart weibo-monitor"
echo "  停止服务: sudo systemctl stop weibo-monitor"
