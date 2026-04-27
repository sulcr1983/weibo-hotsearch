#!/bin/bash

# 远程自动部署脚本
# 安全说明：服务器密码应通过环境变量 REMOTE_SERVER_PASS 传递，不要硬编码在脚本中

# 服务器信息（从环境变量读取）
SERVER_IP="${REMOTE_SERVER_IP:-}"
SERVER_USER="${REMOTE_SERVER_USER:-root}"
SERVER_PASS="${REMOTE_SERVER_PASS:-}"

# 检查密码是否设置
if [ -z "$SERVER_PASS" ]; then
    echo "❌ 错误: 未设置服务器密码"
    echo "请设置环境变量 REMOTE_SERVER_PASS"
    echo "例如: export REMOTE_SERVER_PASS='your_password'"
    exit 1
fi

# 本地项目目录
LOCAL_DIR="$(pwd)"

# 远程临时目录
REMOTE_TMP_DIR="/tmp/weibo_deploy"

# 远程目标目录
REMOTE_TARGET_DIR="/opt/weibo-hotsearch"

echo "🚀 开始远程部署到服务器: ${SERVER_IP}"

# 1. 创建远程临时目录
echo "📁 创建远程临时目录..."
sshpass -p "${SERVER_PASS}" ssh ${SERVER_USER}@${SERVER_IP} "mkdir -p ${REMOTE_TMP_DIR}"

# 2. 上传项目文件
echo "📦 上传项目文件..."
# 上传核心文件
sshpass -p "${SERVER_PASS}" scp "${LOCAL_DIR}/weibo_hotsearch_monitor.py" ${SERVER_USER}@${SERVER_IP}:${REMOTE_TMP_DIR}/
sshpass -p "${SERVER_PASS}" scp "${LOCAL_DIR}/config.py" ${SERVER_USER}@${SERVER_IP}:${REMOTE_TMP_DIR}/
sshpass -p "${SERVER_PASS}" scp "${LOCAL_DIR}/.env" ${SERVER_USER}@${SERVER_IP}:${REMOTE_TMP_DIR}/
sshpass -p "${SERVER_PASS}" scp "${LOCAL_DIR}/requirements.txt" ${SERVER_USER}@${SERVER_IP}:${REMOTE_TMP_DIR}/
sshpass -p "${SERVER_PASS}" scp "${LOCAL_DIR}/weibo-monitor.service" ${SERVER_USER}@${SERVER_IP}:${REMOTE_TMP_DIR}/
sshpass -p "${SERVER_PASS}" scp "${LOCAL_DIR}/deploy.sh" ${SERVER_USER}@${SERVER_IP}:${REMOTE_TMP_DIR}/
sshpass -p "${SERVER_PASS}" scp "${LOCAL_DIR}/.gitignore" ${SERVER_USER}@${SERVER_IP}:${REMOTE_TMP_DIR}/
sshpass -p "${SERVER_PASS}" scp "${LOCAL_DIR}/.env.example" ${SERVER_USER}@${SERVER_IP}:${REMOTE_TMP_DIR}/

# 3. 赋予部署脚本执行权限
echo "🔧 赋予部署脚本执行权限..."
sshpass -p "${SERVER_PASS}" ssh ${SERVER_USER}@${SERVER_IP} "chmod +x ${REMOTE_TMP_DIR}/deploy.sh"

# 4. 执行部署脚本
echo "🚀 执行部署脚本..."
sshpass -p "${SERVER_PASS}" ssh ${SERVER_USER}@${SERVER_IP} "cd ${REMOTE_TMP_DIR} && sudo bash deploy.sh"

# 5. 验证部署结果
echo "\n📊 验证部署结果..."
sshpass -p "${SERVER_PASS}" ssh ${SERVER_USER}@${SERVER_IP} "sudo systemctl status weibo-monitor --no-pager"

# 6. 清理临时目录
echo "\n🧹 清理临时目录..."
sshpass -p "${SERVER_PASS}" ssh ${SERVER_USER}@${SERVER_IP} "rm -rf ${REMOTE_TMP_DIR}"

echo "\n✅ 部署完成！"
echo "\n常用命令："
echo "  查看服务状态: sudo systemctl status weibo-monitor"
echo "  查看日志: tail -f /opt/weibo-hotsearch/logs/monitor.log"
echo "  重启服务: sudo systemctl restart weibo-monitor"
echo "  停止服务: sudo systemctl stop weibo-monitor"
