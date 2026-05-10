#!/bin/bash
# weibo-hotsearch 心跳检测 & 调度状态监控
# 用法:
#   bash system/services/health_check.sh          # 一次检查
#   bash system/services/health_check.sh --daemon # 持续监控（cron 替代）
#
# 返回码: 0 = 健康, 1 = 警告, 2 = 严重

set -euo pipefail

PROJECT_DIR="/opt/weibo-hotsearch"
LOG_DIR="${PROJECT_DIR}/logs"
ALERT_LOG="${LOG_DIR}/health_alerts.log"
WEBHOOK_URL=""    # 可选：填入飞书/企业微信 Webhook

mkdir -p "$LOG_DIR"

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()  { echo -e "  ${GREEN}✅${NC} $1"; }
warn(){ echo -e "  ${YELLOW}⚠️${NC} $1"; }
fail(){ echo -e "  ${RED}❌${NC} $1"; }

# ── 检查 1: 进程存活 ──
check_process() {
    PID=$(pgrep -f "python.*system/main.py" | head -1)
    if [ -n "$PID" ]; then
        ok "服务进程 PID=$PID"
        # 检查 CPU / 内存
        STAT=$(ps -p "$PID" -o rss,pcpu,etime --no-headers 2>/dev/null || true)
        if [ -n "$STAT" ]; then
            RSS=$(echo "$STAT" | awk '{printf "%.0f", $1/1024}')
            CPU=$(echo "$STAT" | awk '{print $2}')
            ELAPSED=$(echo "$STAT" | awk '{print $3}')
            echo "    RSS=${RSS}MB CPU=${CPU}% 运行时长=${ELAPSED}"
            # 内存超过 500MB 告警
            [ "$RSS" -gt 500 ] && warn "内存使用偏高 (${RSS}MB)"
        fi
        return 0
    else
        fail "服务进程不存在"
        return 2
    fi
}

# ── 检查 2: 端口监听 ──
check_port() {
    local PORT="${1:-8001}"
    if command -v ss &>/dev/null; then
        if ss -tlnp | grep -q ":${PORT} "; then
            ok "端口 ${PORT} 监听正常"
            return 0
        fi
    elif command -v netstat &>/dev/null; then
        if netstat -tlnp 2>/dev/null | grep -q ":${PORT} "; then
            ok "端口 ${PORT} 监听正常"
            return 0
        fi
    fi
    fail "端口 ${PORT} 未监听"
    return 2
}

# ── 检查 3: API 健康接口 ──
check_api() {
    local BASE="http://localhost:${1:-8001}"
    local HTTP_CODE
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${BASE}/" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" = "200" ]; then
        ok "/ 响应 HTTP 200"
    else
        fail "/ 响应异常 (HTTP ${HTTP_CODE})"
        return 2
    fi

    # /status 接口
    local STATUS_BODY
    STATUS_BODY=$(curl -s --max-time 5 "${BASE}/status" 2>/dev/null || echo "")
    if [ -n "$STATUS_BODY" ]; then
        if echo "$STATUS_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('db',{}).get('articles',-1))" 2>/dev/null; then
            ok "/status 正常"
        else
            warn "/status 返回异常: ${STATUS_BODY:0:100}"
        fi
    else
        warn "/status 无响应"
    fi
}

# ── 检查 4: 调度任务状态 ──
check_scheduler() {
    local BASE="http://localhost:${1:-8001}"
    local BODY
    BODY=$(curl -s --max-tim 5 "${BASE}/status" 2>/dev/null || echo "{}")

    local JOB_COUNT
    JOB_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('scheduler_jobs',[])))" 2>/dev/null || echo "0")

    if [ "$JOB_COUNT" -gt 0 ]; then
        ok "定时任务 ${JOB_COUNT} 个已注册"
        echo "$BODY" | python3 -c "
import sys,json
for j in json.load(sys.stdin).get('scheduler_jobs',[]):
    print(f'    📅 {j[\"id\"]:30s} next={j[\"next_run\"]}')
" 2>/dev/null
    else
        warn "无定时任务（调度器可能未启动）"
    fi
}

# ── 检查 5: 数据库文件 ──
check_db() {
    local DB_DIR="${PROJECT_DIR}/data"
    local ISSUES=0
    for DB in v3_monitor.db v3_weibo.db; do
        local F="${DB_DIR}/${DB}"
        if [ -f "$F" ]; then
            local SIZE
            SIZE=$(stat -c%s "$F" 2>/dev/null || stat -f%z "$F" 2>/dev/null || echo 0)
            if [ "$SIZE" -gt 1048576 ]; then
                ok "${DB} 存在 (${SIZE} bytes)"
            elif [ "$SIZE" -gt 0 ]; then
                warn "${DB} 文件偏小 (${SIZE} bytes)"
            else
                fail "${DB} 文件为空"
                ISSUES=$((ISSUES+1))
            fi
        else
            fail "${DB} 不存在"
            ISSUES=$((ISSUES+1))
        fi
    done
    return $ISSUES
}

# ── 检查 6: 最近日志错误 ──
check_logs() {
    local LOG_FILE="${LOG_DIR}/main.log"
    if [ ! -f "$LOG_FILE" ]; then
        warn "日志文件不存在"
        return 1
    fi

    local ERRORS
    ERRORS=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo 0)
    local WARNINGS
    WARNINGS=$(grep -c "WARNING" "$LOG_FILE" 2>/dev/null || echo 0)
    local ERRORS_1H
    ERRORS_1H=$(grep "ERROR" "$LOG_FILE" 2>/dev/null | tail -20)

    if [ "$ERRORS" -gt 0 ]; then
        warn "日志累计错误 ${ERRORS} 条，警告 ${WARNINGS} 条"
        if [ -n "$ERRORS_1H" ]; then
            echo "    最近错误:"
            echo "$ERRORS_1H" | tail -5 | sed 's/^/    /'
        fi
    else
        ok "日志无 ERROR"
    fi

    # 检查是否有 OOM / 重启痕迹
    if grep -q "Killed\|OutOfMemory\|Segmentation fault" "$LOG_FILE" 2>/dev/null; then
        fail "检测到进程异常终止"
        return 1
    fi
}

# ── 告警发送 ──
send_alert() {
    local LEVEL="$1"
    local MESSAGE="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${LEVEL}] ${MESSAGE}" >> "$ALERT_LOG"

    if [ -n "$WEBHOOK_URL" ]; then
        curl -s -X POST "$WEBHOOK_URL" \
          -H "Content-Type: application/json" \
          -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"[weibo-monitor] ${LEVEL}: ${MESSAGE}\"}}" \
          -o /dev/null &
    fi
}

# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════
main() {
    local PORT=8001
    local EXIT_CODE=0

    echo "=========================================="
    echo " weibo-hotsearch 心跳检测"
    echo " $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="

    echo ""
    echo "【1/6】进程状态"
    check_process || EXIT_CODE=$?

    echo ""
    echo "【2/6】端口监听"
    check_port "$PORT" || EXIT_CODE=$?

    echo ""
    echo "【3/6】API 健康"
    check_api "$PORT" || EXIT_CODE=$?

    echo ""
    echo "【4/6】调度任务"
    check_scheduler "$PORT" || EXIT_CODE=$?

    echo ""
    echo "【5/6】数据库文件"
    check_db || EXIT_CODE=$?

    echo ""
    echo "【6/6】日志检查"
    check_logs || EXIT_CODE=$?

    echo ""
    echo "=========================================="
    if [ "$EXIT_CODE" -eq 0 ]; then
        echo "  ✅ 服务健康"
    elif [ "$EXIT_CODE" -ge 2 ]; then
        echo "  ❌ 服务异常 (exit=$EXIT_CODE)"
        send_alert "CRITICAL" "服务异常 (exit=${EXIT_CODE})"
    else
        echo "  ⚠️ 服务带警告运行"
        send_alert "WARNING" "检查项异常 (exit=${EXIT_CODE})"
    fi
    echo "=========================================="

    return "$EXIT_CODE"
}

# ── 持续模式 ──
if [ "${1:-}" = "--daemon" ]; then
    INTERVAL="${2:-300}"
    echo "🔁 持续监控模式，间隔 ${INTERVAL}s ..."
    echo "   按 Ctrl+C 退出"
    while true; do
        main || true
        sleep "$INTERVAL"
    done
else
    main
fi