#!/usr/bin/env bash
# 构建并把 dist/ 推送到腾讯云主站。用法：
#   DEPLOY_HOST=root@<服务器公网IP> bash deploy/push-dist.sh
# 可选：DEPLOY_KEY=<私钥路径> 指定 SSH 密钥。
# 服务器需先按 deploy/README.md 装好 nginx 并建 /var/www/alethicinsight。
set -euo pipefail

HOST="${DEPLOY_HOST:?set DEPLOY_HOST=user@ip}"
SSH_OPTS=(-o ConnectTimeout=10)
if [ -n "${DEPLOY_KEY:-}" ]; then SSH_OPTS+=(-i "$DEPLOY_KEY"); fi

cd "$(dirname "$0")/.."
echo "[1/4] build"
npm run build

STAMP="$(date +%Y%m%d-%H%M%S)"
RELEASE="/var/www/alethicinsight/releases/$STAMP"

echo "[2/4] upload dist -> $HOST:$RELEASE"
tar czf - -C dist . | ssh "${SSH_OPTS[@]}" "$HOST" "mkdir -p '$RELEASE' && tar xzf - -C '$RELEASE'"

echo "[3/4] switch current symlink"
ssh "${SSH_OPTS[@]}" "$HOST" "ln -sfn '$RELEASE' /var/www/alethicinsight/current && nginx -t && systemctl reload nginx"

echo "[4/4] prune old releases (keep 5)"
ssh "${SSH_OPTS[@]}" "$HOST" "cd /var/www/alethicinsight/releases && ls -1t | tail -n +6 | xargs -r rm -rf"

echo "done: $RELEASE is live"
