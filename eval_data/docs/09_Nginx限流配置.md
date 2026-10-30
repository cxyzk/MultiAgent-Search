# Nginx 限流配置

Nginx 内置两个限流模块：`limit_req`（请求速率，漏桶）和 `limit_conn`（并发连接数），是最经济的入口限流方案。

## limit_req：请求速率限流

```nginx
http {
    # 定义限流区：10MB 共享内存，按 IP 限制 10 r/s
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    server {
        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;
            limit_req_status 429;
            proxy_pass http://backend;
        }
    }
}
```

### 三个关键参数

| 参数 | 含义 | 说明 |
|---|---|---|
| `zone=名字:大小` | 共享内存区 | 10MB 约存 16 万个 IP 的状态 |
| `rate=10r/s` | 平均速率 | 也支持 `r/m`（每分钟） |
| `burst=20` | 漏桶队列长度 | 允许 20 个请求排队 |
| `nodelay` | 不延迟处理 | 队列里的请求立即处理，而不是按 rate 均匀放行 |

### nodelay 的取舍

- **不加 nodelay**：burst 里的请求按 rate 匀速放行（如 10r/s 时每 100ms 一个）→ **延迟明显**
- **加 nodelay**：burst 里的请求立即处理 → **允许瞬时突发**，但超出 burst 的直接 429

**推荐加 nodelay**：用户体验优先，burst 本身就是"允许的突发额度"。

## 按维度限流

```nginx
# 按 IP（最常用，防刷）
limit_req_zone $binary_remote_addr zone=per_ip:10m rate=10r/s;

# 按用户 ID（从 header 取，需配合 auth）
limit_req_zone $http_x_user_id zone=per_user:10m rate=50r/s;

# 按接口路径
limit_req_zone $uri zone=per_uri:10m rate=100r/s;

# 全局限流（所有请求共享一个桶）
limit_req_zone $server_name zone=global:10m rate=1000r/s;
```

**多维度叠加**：一个 location 可以配多个 `limit_req`，**任一超限就拒绝**：

```nginx
location /api/pay/ {
    limit_req zone=per_ip burst=5 nodelay;
    limit_req zone=per_user burst=20 nodelay;
    limit_req zone=global burst=500 nodelay;
}
```

## limit_conn：并发连接限流

```nginx
limit_conn_zone $binary_remote_addr zone=conn_per_ip:10m;

server {
    limit_conn conn_per_ip 10;      # 每个 IP 最多 10 个并发连接
    limit_conn_status 429;
}
```

适合**长连接/大文件下载**场景（限流管不住"一个连接传 1 小时"的情况）。

## 响应头与监控

```nginx
# 让客户端知道限流状态（需 ngx_http_headers_module）
add_header X-RateLimit-Limit 10;
add_header X-RateLimit-Remaining $limit_req_status;
```

**监控**：`limit_req` 的拒绝数在 `nginx_status` 里看不到，需要在 access log 里统计 429：

```bash
grep ' 429 ' /var/log/nginx/access.log | wc -l
```

## 常见坑

1. **`rate=10r/s` 写成 `rate=10`**：Nginx 会按 `10r/s` 解析，但显式写单位更清晰
2. **`burst=0`**：任何超过 rate 的请求都立即 429，抖动时误杀严重
3. **共享内存太小**：`zone=api:1m` 只能存 1.6 万个 IP，超出后旧状态被淘汰，限流失效
4. **只限 IP 不限用户**：NAT 环境下整个公司共用一个出口 IP，一个人刷会被全公司连坐
5. **忘了 `limit_req_status 429`**：默认返回 503，客户端会误以为是服务故障而重试

## FAQ

**Q：limit_req 是令牌桶还是漏桶？**
**漏桶**。`burst` 就是桶的队列容量，超出队列的请求直接拒绝。它不积累"令牌"，所以不支持突发额度（除非用 nodelay 变相实现）。

**Q：Nginx 限流和网关限流怎么选？**
Nginx 在最外层，性能最好（C 实现），适合 **IP 级、全局限流**；网关（如 Spring Cloud Gateway）能拿到用户身份，适合 **用户级、接口级**细粒度限流。两者叠加使用。

**Q：rate 能设成 0.5r/s 吗？**
可以，Nginx 支持小数速率（0.5r/s = 每 2 秒 1 个），但 burst 要相应调大。
