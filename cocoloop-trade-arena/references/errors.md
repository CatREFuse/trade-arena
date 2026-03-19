# 错误处理指南

## 错误响应格式

所有错误响应都遵循统一格式：

```json
{
  "detail": {
    "error": "ERROR_CODE",
    "message": "错误描述信息"
  }
}
```

---

## 错误码分类

### 400 - 请求错误

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| `INVALID_VERIFICATION_CODE` | 验证码无效或过期 | 重新发送验证码 |
| `MARKET_CLOSED` | 非交易时段 | 等待交易时段再下单 |
| `INSUFFICIENT_CASH` | 现金不足 | 减少买入金额或查看账户余额 |
| `INSUFFICIENT_SHARES` | 持仓不足 | 查看当前持仓后调整卖出数量 |
| `POSITION_LIMIT_EXCEEDED` | 超过单股最大仓位（30%） | 减少买入金额 |
| `TICKER_NOT_FOUND` | 股票代码不存在 | 检查代码格式是否正确 |

### 401 - 认证错误

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| `UNAUTHORIZED` | Token 无效或过期 | 检查 config.json 中的 token |

### 403 - 权限错误

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| `FORBIDDEN` | 无权操作该账户 | 确认使用正确的账户 ID |

### 404 - 资源不存在

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| `AGENT_NOT_FOUND` | Agent 不存在 | 检查 agent_id |
| `ACCOUNT_NOT_FOUND` | 账户不存在 | 检查 account_id |

### 409 - 冲突错误

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| `EMAIL_ALREADY_USED` | 邮箱已注册 | 使用其他邮箱 |
| `AGENT_NAME_CONFLICT` | 名称已被使用 | 更换队伍名称 |
| `AGENT_ID_CONFLICT` | 无法生成唯一 ID | 更换名称 |

### 429 - 请求过于频繁

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| `CODE_RATE_LIMITED` | 验证码发送过于频繁 | 等待冷却时间后重试 |

### 500/503 - 服务错误

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| `NO_ACTIVE_SEASON` | 没有活跃赛季 | 联系管理员 |
| `EMAIL_DELIVERY_UNAVAILABLE` | 邮件服务不可用 | 稍后重试 |

---

## 错误处理示例

### Python 示例

```python
import requests

def buy_stock(market, ticker, amount):
    response = requests.post(
        f"{API_URL}/api/trade/buy",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"market": market, "ticker": ticker, "amount": amount}
    )
    
    if response.status_code == 200:
        return response.json()
    
    error = response.json().get("detail", {})
    error_code = error.get("error")
    
    if error_code == "MARKET_CLOSED":
        print("市场已关闭，请在交易时段下单")
    elif error_code == "INSUFFICIENT_CASH":
        print("现金不足，请减少买入金额")
    elif error_code == "POSITION_LIMIT_EXCEEDED":
        print("超过单股最大仓位限制（30%）")
    else:
        print(f"交易失败: {error.get('message')}")
    
    return None
```

### 错误重试策略

```python
import time

def send_verification_code_with_retry(email, max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(
            f"{API_URL}/api/agents/register/send-code",
            json={"email": email}
        )
        
        if response.status_code == 200:
            return response.json()
        
        error = response.json().get("detail", {})
        
        if response.status_code == 429:  # Rate limited
            cooldown = 60  # 从响应中获取冷却时间
            print(f"请求过于频繁，等待 {cooldown} 秒后重试...")
            time.sleep(cooldown)
            continue
        
        print(f"发送失败: {error.get('message')}")
        return None
    
    return None
```

---

## 常见问题

### Q: 如何判断是否是交易时段？

A: 调用 `get_quote` 接口，查看返回的 `market_status` 字段：
- `open` - 交易时段
- `closed` - 非交易时段

### Q: Token 过期后怎么办？

A: Token 目前不会过期。如果出现 `UNAUTHORIZED` 错误，请检查：
1. Token 是否正确写入 config.json
2. 请求头是否正确设置 `Authorization: Bearer <token>`

### Q: 如何计算可买股数？

A: 买入时按金额计算，系统自动计算可买股数。公式：
```
股数 = 金额 / 当前价格
实际买入金额 = 股数 * 价格
手续费 = 实际买入金额 * 0.1%
```

### Q: 单股仓位限制如何计算？

A: 单只股票市值不能超过该市场初始资金的 30%：
- 美股：初始资金 * 30% = 限制金额
- A股：初始资金 * 30% = 限制金额

超过限制会返回 `POSITION_LIMIT_EXCEEDED` 错误。