# DecryptPasswordResource

## 基本信息

- **源文件**：`resources/toolkit.py`
- **HTTP 端点**：无直接 HTTP 端点（内部使用）
- **resource 路径**：`resource.collecting.decrypt_password`
- **功能**：基于内置 RSA 私钥，对密文进行解密
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| encrypted_text | str | 是 | - | 密文 |

## 出参

```python
str  # 解密后的明文
```

## 核心依赖

- `RSACipher`：RSA 解密工具
- `settings.RSA_PRIVATE_KEY`：RSA 私钥配置

## bk-monitor-base 适配分析

### 适配建议
- 与 `EncryptPasswordResource` 配对，可独立封装

### 风险点
- 未配置 RSA 密钥时直接 `raise`（无异常消息），需改进

### 注意
- 当前实现有 bug：未配置密钥时 `raise` 无参数
