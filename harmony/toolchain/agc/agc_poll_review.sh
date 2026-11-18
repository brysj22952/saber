#!/usr/bin/env bash
# 阶段 5:轮询 AGC 上架审核状态,每 10 分钟一次,直到出现终态或达到上限(约 7 天)。
#
# 用法:
#   nohup bash harmony/toolchain/agc/agc_poll_review.sh >/dev/null 2>&1 &
#   tail -f /tmp/agc_poll.log        # 看轮询结果
#
# 说明:
# * 依赖浏览器开着 CDP(默认 127.0.0.1:9333)且已登录华为账号;
# * 只调 harmony/toolchain/agc/agc_version_status.py(不改动 agc_console.py 的既有逻辑);
# * 状态一旦变成「已上架/已发布」或含「不通过」,脚本自动停止并写进日志。
set -u
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_DIR" || exit 1
LOG="${AGC_POLL_LOG:-/tmp/agc_poll.log}"

for i in $(seq 1 "${AGC_POLL_MAX:-1000}"); do
  echo "=== $(date +'%m-%d %H:%M:%S') 第${i}次 ===" >> "$LOG"
  out=$(timeout 150 python3 harmony/toolchain/agc/agc_version_status.py 2>&1)
  echo "$out" >> "$LOG"
  case "$out" in
    *已上架*|*已发布*)
      echo "### 检测到终态(已上架/已发布),轮询结束 ###" >> "$LOG"
      break ;;
    *不通过*)
      echo "### 检测到「不通过」,正在抓取审核报告原文 ###" >> "$LOG"
      # 被打回时自动把审核报告抓下来 —— 6 条问题分在报告页的 4 个 tab 上,
      # 脚本会逐个 tab 点开读取,不用再手工点控制台。
      ver=$(echo "$out" | sed -n 's/^版本: //p' | head -1)
      rep="/tmp/agc_audit_report_${ver:-unknown}.txt"
      timeout 280 python3 harmony/toolchain/agc/agc_audit_report.py --out "$rep" >> "$LOG" 2>&1
      echo "### 审核报告已保存到 $rep,轮询结束(需要人工按报告整改后重提) ###" >> "$LOG"
      break ;;
  esac
  sleep "${AGC_POLL_INTERVAL:-600}"
done
