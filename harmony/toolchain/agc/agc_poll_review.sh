#!/usr/bin/env bash
# 阶段 5:轮询 AGC 上架审核状态,每 10 分钟一次,直到出现终态或达到上限(约 7 天)。
#
# 用法:
#   nohup bash harmony/toolchain/agc/agc_poll_review.sh >/dev/null 2>&1 &
#   tail -f /tmp/agc_poll.log        # 看轮询结果
#   bash harmony/toolchain/agc/agc_poll_review.sh --self-test   # 自测状态判定
#
# 说明:
# * 依赖浏览器开着 CDP(默认 127.0.0.1:9333)且已登录华为账号;
# * 只调 harmony/toolchain/agc/agc_version_status.py(不改动 agc_console.py 的既有逻辑);
# * 状态一旦变成「已上架/已发布/审核通过」或「不通过/未通过/待修改/已退回」,
#   脚本自动停止并写进日志;被打回时还会自动把审核报告原文抓下来。
set -u
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_DIR" || exit 1
LOG="${AGC_POLL_LOG:-/tmp/agc_poll.log}"

# 把控制台上的状态词归成三类:REJECTED(被打回)/APPROVED(通过)/PENDING(还在等)。
#
# 为什么单独抽出来:判定逻辑是这个脚本里唯一"错了就完蛋"的地方 ——
# 误判成被打回,会在审核还没结论时就把轮询停掉并去抓一份空的审核报告;
# 漏判成被打回,则会一直转、也不会自动抓报告(而控制台历史上「待修改」和
# 「不通过」两种说法都出现过)。所以写成纯函数 + 自测,改完能立刻验证。
#
# 注意:只对「状态:」那一行做判定,不对整段输出做判定 —— 整段输出里混着
# 页面上别的字,容易误判(比如页面提示语里也出现「不通过」两个字)。
classify_status() {
  case "$1" in
    *不通过*|*未通过*|*待修改*|*已退回*) echo REJECTED ;;
    *已上架*|*已发布*|*审核通过*)      echo APPROVED ;;
    *)                                  echo PENDING ;;
  esac
}

self_test() {
  local bad=0
  check() { # 期望 实际 描述
    if [ "$1" = "$2" ]; then
      printf '  ✓ %-28s -> %s\n' "$3" "$2"
    else
      printf '  ✗ %-28s -> %s(应为 %s)\n' "$3" "$2" "$1"
      bad=1
    fi
  }
  check PENDING  "$(classify_status '正在等待审核')"   '正在等待审核'
  check PENDING  "$(classify_status '正在审核')"       '正在审核'
  check PENDING  "$(classify_status '预审中')"         '预审中'
  check PENDING  "$(classify_status '准备提交')"       '准备提交'
  check PENDING  "$(classify_status '未识别(页面上没有状态关键词,可能不在版本页)')" '未识别'
  check PENDING  "$(classify_status '跳过(页面上没有包名 com.sabernotes.saber,可能连到了别的标签页)')" '跳过'
  check REJECTED "$(classify_status '不通过')"         '不通过'
  check REJECTED "$(classify_status '审核不通过')"     '审核不通过'
  check REJECTED "$(classify_status '未通过')"         '未通过'
  check REJECTED "$(classify_status '待修改')"         '待修改'
  check REJECTED "$(classify_status '已退回')"         '已退回'
  check APPROVED "$(classify_status '已上架')"         '已上架'
  check APPROVED "$(classify_status '已发布')"         '已发布'
  check APPROVED "$(classify_status '审核通过')"       '审核通过'
  if [ "$bad" = 0 ]; then
    echo "状态判定自测全部通过 ✓"
  else
    echo "状态判定自测有失败项 ✗" >&2
  fi
  return "$bad"
}

if [ "${1:-}" = "--self-test" ]; then
  self_test
  exit $?
fi

for i in $(seq 1 "${AGC_POLL_MAX:-1000}"); do
  echo "=== $(date +'%m-%d %H:%M:%S') 第${i}次 ===" >> "$LOG"
  out=$(timeout 150 python3 harmony/toolchain/agc/agc_version_status.py 2>&1)
  echo "$out" >> "$LOG"
  status_line=$(echo "$out" | sed -n 's/^状态: //p' | head -1)
  case "$(classify_status "$status_line")" in
    REJECTED)
      echo "### 检测到被打回(状态:$status_line),正在抓取审核报告原文 ###" >> "$LOG"
      # 被打回时自动把审核报告抓下来 —— 6 条问题分在报告页的 4 个 tab 上,
      # 脚本会逐个 tab 点开读取,不用再手工点控制台。
      ver=$(echo "$out" | sed -n 's/^版本: //p' | head -1)
      rep="/tmp/agc_audit_report_${ver:-unknown}.txt"
      timeout 280 python3 harmony/toolchain/agc/agc_audit_report.py --out "$rep" >> "$LOG" 2>&1
      echo "### 审核报告已保存到 $rep,轮询结束(需要人工按报告整改后重提) ###" >> "$LOG"
      break ;;
    APPROVED)
      echo "### 检测到终态(状态:$status_line),轮询结束 ###" >> "$LOG"
      break ;;
  esac
  sleep "${AGC_POLL_INTERVAL:-600}"
done
