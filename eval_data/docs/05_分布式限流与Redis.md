# 分布式限流与 Redis

单机限流用内存计数器就够，但多实例部署时，每个实例各限各的，总量会翻倍。分布式限流把计数集中到 Redis（或专门的限流服务）。

## 为什么单机限流不够

假设限流 100 QPS，部署 4 个实例：

```
用户请求 → 负载均衡 → 4 个实例（各限 100 QPS）→ 实际总放行 400 QPS
```

**要么把单机限额除以实例数**（100/4=25，但实例数变化时要改配置），**要么用集中式计数**。

## Redis 方案的三种实现

### 1. INCR + EXPIRE（固定窗口，最简单）

```python
def allow(redis, key, limit=100, window=1):
    k = f"rate:{key}:{int(time.time()) // window}"
    count = redis.incr(k)
    if count == 1:
        redis.expire(k, window)
    return count <= limit
```

- **优点**：实现简单，Redis 压力小
- **缺点**：窗口边界突刺；INCR 和 EXPIRE 非原子

### 2. Lua 脚本（令牌桶 / 滑动窗口，推荐）

```lua
-- 令牌桶：KEYS[1]=rate:key, ARGV=[now_ms, rate, capacity]
local now = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])

local data = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(data[1]) or capacity
local last = tonumber(data[2]) or now

tokens = math.min(capacity, tokens + (now - last) / 1000 * rate)
local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end
redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('PEXPIRE', KEYS[1], 60000)
return allowed
```

- **优点**：原子、精确、支持突发
- **缺点**：每次请求一次 Redis 往返（约 0.5-1ms）

### 3. Redis Cell 模块（`CL.THROTTLE`）

```bash
CL.THROTTLE user:123 100 200 60 1
# 参数: key, 最大突发, 每秒速率, 窗口秒数, 消耗令牌数
```

- **优点**：原生 GCRA 算法，精度高，返回重试等待时间
- **缺点**：需要 Redis 4.0+ 且编译了 cell 模块，云 Redis 不一定支持

## 性能与可靠性

| 方案 | 每次请求开销 | 单 Redis 承载 | 风险 |
|---|---|---|---|
| INCR | 1 次往返 | 10 万+ QPS | 边界突刺 |
| Lua | 1 次往返（脚本执行） | 5-8 万 QPS | 脚本阻塞主线程（要短） |
| Redis Cell | 1 次往返 | 8 万+ QPS | 模块依赖 |

**Redis 挂了的降级策略**（必须想清楚）：

1. **放行（fail-open）**：限流失效，靠下游熔断兜底 —— 适合"限流只是优化"的场景
2. **拒绝（fail-close）**：全站 503 —— 适合"不限流会打挂核心系统"的场景
3. **本地兜底**：切到单机令牌桶（限额 = 全局限额 / 实例数）—— **最推荐**

## 常见坑

1. **key 数量爆炸**：按 `用户ID + 接口` 限流，100 万用户 × 100 接口 = 1 亿 key → 必须设 TTL 且用短 key
2. **Lua 脚本太长**：Redis 单线程，脚本超过 10ms 会阻塞所有请求
3. **没设超时**：Redis 网络抖动时，限流调用不能无限等 → 客户端设 50ms 超时，超时按 fail-open 处理
4. **时钟不同步**：脚本里用 `redis.call('TIME')` 而不是应用时间

## FAQ

**Q：Redis 集群模式下 Lua 能跨 key 吗？**
不能。所有 key 必须在同一个 slot（用 hash tag，如 `rate:{user:123}:api`），否则报 CROSSSLOT 错误。

**Q：限流应该做在网关还是业务层？**
两层都做：网关做粗粒度（IP/全局 QPS），业务层做细粒度（用户/接口/资源）。网关挡洪水，业务层防单点滥用。
