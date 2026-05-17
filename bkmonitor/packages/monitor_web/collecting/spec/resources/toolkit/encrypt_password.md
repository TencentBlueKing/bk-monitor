# EncryptPasswordResource

## 基本信息

- **源文件**：`resources/toolkit.py`
- **HTTP 端点**：无直接 HTTP 端点（内部使用）
- **resource 路径**：`resource.collecting.encrypt_password`
- **功能**：基于内置 RSA 公钥，对密码类文本进行加密
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| password | str | 是 | - | 明文密码 |

## 出参

```python
str  # 加密后的密文（或未配置RSA时返回明文）
```

## 核心依赖

- `RSACipher`：RSA 加密工具
- `settings.RSA_PRIVATE_KEY`：RSA 私钥配置

## bk-monitor-base 适配分析

### 适配建议
- **可独立封装**，与采集配置无直接关系
- base 侧可提供统一的加解密工具

### 风险点
- 无风险，逻辑简单

### 跨模块调用
- 被 `plugin/manager/exporter.py` 通过 `resource.collecting.encrypt_password` 调用
