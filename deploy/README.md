# 腾讯云主站部署说明（alethicinsight.org）

主站架构：GitHub 仅作代码仓库（不走 Actions/Pages），腾讯云轻量服务器跑 nginx 托管
`dist/` 静态产物；域名 DNS 与跳转在 Cloudflare，回源走 Full (strict)。

域名口径：对外身份（GitHub/HuggingFace/邮箱）一律 `alethicinsight.org`；网站实体
绑 `alethicinsight.com`（.org 不在工信部可备案目录，境内机房无法备案，.com 可以）。
`.org` 及其余域名在 Cloudflare 边缘 301 到 `.com`，不直接解析到源站。

## 前置：ICP 备案（境内机房的硬前置，最先启动）

境内服务器（如成都）的 80/443 在域名未备案前被运营商层面拦截，**先买服务器、
随即在腾讯云备案控制台/小程序提交 `alethicinsight.com` 的备案**（主体=实验室/
个人实名，周期约 2-4 周），备案通过前域名无法指到境内源站。等待期间可先在
本机/临时境外节点演练部署流程。

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

口径：主域名为 `alethicinsight.com`，其余四个域名（`alethicinsight.org`、
`alethicinsight.cn`、`aletheion.cn`、`aletheion.org.cn`）全部 301 到主域名。

1. DNS：`alethicinsight.com` 的 A 记录 → 服务器公网 IP，代理状态开启（橙云）；
   其余四个 zone 不需要指向源站的记录（跳转由 Cloudflare 边缘完成），但可保留
   占位记录（如 A `192.0.2.1` 开橙云）以便 Redirect Rule 生效；
2. SSL/TLS：模式 **Full (strict)**；
3. Origin Server：为 `alethicinsight.com` 创建 Origin CA 证书装到 nginx；
4. Rules → Redirect Rules：为其余四个 zone 各建一条 301 到
   `https://alethicinsight.com`（preserve query string）；旧 Tunnel 方案退役。

## 回滚

```bash
ssh root@<IP> "ln -sfn /var/www/alethicinsight/releases/<旧时间戳> /var/www/alethicinsight/current && systemctl reload nginx"
```
