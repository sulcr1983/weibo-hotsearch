#!/bin/bash
# weibo-hotsearch 一键诊断脚本
# 用法：bash system/services/diagnose.sh

cd /opt/weibo-hotsearch
VENV=./venv/bin/python

echo "========================================"
echo " weibo-hotsearch 系统诊断报告"
echo " $(date)"
echo "========================================"

# 1. 进程检查
echo ""
echo "【1】进程状态"
PID=$(pgrep -f "python system/main.py")
if [ -n "$PID" ]; then
    echo "  ✅ 服务运行中 PID=$PID"
    ps -p $PID -o pid,vsz,rss,pcpu,etime --no-headers | awk '{printf "  内存: %dMB | CPU: %s%% | 运行: %s\n", $3/1024, $4, $5}'
else
    echo "  ❌ 服务未运行"
fi

# 2. 端口检查
echo ""
echo "【2】端口监听"
if ss -tlnp | grep -q ':8001'; then
    echo "  ✅ :8001 端口监听正常"
else
    echo "  ❌ :8001 端口未监听"
fi

# 3. API 健康检查
echo ""
echo "【3】API 健康检查"
RESP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ 2>/dev/null)
if [ "$RESP" = "200" ]; then
    echo "  ✅ API 响应正常 (HTTP 200)"
else
    echo "  ❌ API 无响应或异常 (HTTP $RESP)"
fi

# 4. 数据库检查
echo ""
echo "【4】数据库状态"
for DB in data/v3_monitor.db data/v3_weibo.db; do
    if [ -f "$DB" ]; then
        echo "  ✅ $DB 存在"
    else
        echo "  ❌ $DB 不存在"
    fi
done

# 5. 环境变量检查
echo ""
echo "【5】环境变量检查"
source .env 2>/dev/null || true
[ -n "$FEISHU_WEBHOOK_URL" ] && echo "  ✅ FEISHU_WEBHOOK_URL 已配置" || echo "  ❌ FEISHU_WEBHOOK_URL 未配置"
[ -n "$AI_API_KEY" ] && echo "  ✅ AI_API_KEY 已配置" || echo "  ❌ AI_API_KEY 未配置"
[ -n "$EMAIL_SENDER" ] && echo "  ✅ EMAIL_SENDER 已配置" || echo "  ❌ EMAIL_SENDER 未配置"

# 6. 日志最后20行
echo ""
echo "【6】最新日志（最后20行）"
if [ -f "logs/main.log" ]; then
    tail -20 logs/main.log
else
    echo "  ⚠️ 日志文件不存在"
fi

# 7. 最近错误统计
echo ""
echo "【7】最近24小时错误统计"
if [ -f "logs/main.log" ]; then
    echo "  错误统计："
    grep -c "ERROR" logs/main.log 2>/dev/null
    grep -c "WARNING" logs/main.log 2>/dev/null
    echo "  最近错误："
    grep "ERROR" logs/main.log | tail -5
fi

echo ""
echo "========================================"
echo " 诊断完成"
echo "========================================"