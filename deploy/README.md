# 腾讯云主站部署说明（alethicinsight.org）

主站架构：GitHub 仅作代码仓库（不走 Actions/Pages），腾讯云轻量服务器跑 nginx 托管
`dist/` 静态产物；域名 DNS 与跳转在 Cloudflare，回源走 Full (strict)。

## 服务器一次性初始化（Ubuntu 24.04）

```bash
apt update && apt install -y nginx
mkdir -p /var/www/alethicinsight/releases /var/www/acme
# TLS：Cloudflare Dashboard -> SSL/TLS -> Origin Server -> Create Certificate，
# 把 Origin Certificate 和 Private Key 分别存为：
#   /etc/nginx/ssl/alethicinsight-origin.pem
#   /etc/nginx/ssl/alethicinsight-origin.key
cp deploy/nginx-alethicinsight.conf /etc/nginx/sites-available/alethicinsight
ln -s /etc/nginx/sites-available/alethicinsight /etc/nginx/sites-enabled/alethicinsight
nginx -t && systemctl enable --now nginx && systemctl reload nginx
# 防火墙/安全组放行 80、443（22 建议限源 IP）
```

## 每次发布（在本机 website/ 下）

```bash
DEPLOY_HOST=root@<服务器公网IP> bash deploy/push-dist.sh
```

脚本会 `npm run build`、打包上传 `dist/` 到带时间戳的 release 目录、切换
`current` 软链并 reload nginx；保留最近 5 个 release 便于回滚（改指软链即可）。

## Cloudflare 侧（一次性）

1. DNS：A 记录 `alethicinsight.org`（及 `www`）→ 服务器公网 IP，代理状态开启（橙云）；
2. SSL/TLS：模式 **Full (strict)**；
3. 若用旧域名（aletheion.cn / preview.aletheion.cn 等）做跳转，在 Rules 里配
   Redirect Rule 到 `https://alethicinsight.org`，Tunnel 方案退役。

## 回滚

```bash
ssh root@<IP> "ln -sfn /var/www/alethicinsight/releases/<旧时间戳> /var/www/alethicinsight/current && systemctl reload nginx"
```
