<p align="center">
  <img src="./docs/img/logo.png">
</p>

<p align="center">
  <em>蓝鲸智云监控平台(BLUEKING-MONITOR)是蓝鲸智云官方推出的一款监控平台产品，除了具有丰富的数据采集能力，大规模的数据处理能力，简单易用，还提供更多的平台扩展能力。依托于蓝鲸 PaaS，有别于传统的 CS 结构，在整个蓝鲸生态中可以形成监控的闭环能力。</em>

---

# 简介

此项目是监控平台的子项目，主要是提供监控平台的基础能力，如空间管理、数据采集、元数据管理等。上层SaaS可以基于此项目提供的能力，实现多样的场景化能力。

1. 空间管理：提供空间管理能力，根据第三方平台接口同步空间信息。
2. 数据采集：提供数据采集能力，包括数据采集、数据处理、数据存储等。
3. 元数据管理：提供元数据管理能力，包括元数据创建、元数据删除、元数据查询等。

# 项目开发

## 目录结构

```
bk_monitor_base
├── domains # 领域服务
├── infras # 基础设施
├── config # 配置
└── cli # 命令行工具
```

1. 领域服务：包含主要的业务逻辑，如空间管理、数据采集、元数据管理等。
2. 基础设施：包含基础的组件或工具，如数据库、缓存、日志等。
3. 配置：主要是读取环境变量或配置文件，定义配置项。
4. 命令行工具：包含命令行工具，如shell，migrate等。

## 🚀 快速开始

### 环境要求

- Python 3.11+
- 推荐使用 [uv](https://docs.astral.sh/uv/getting-started/) 管理依赖

### 快速安装

```bash
# 克隆项目
git clone <repository-url>
cd bk-monitor-base

# 创建虚拟环境并安装依赖
uv venv --seed
source .venv/bin/activate
uv sync --all-groups
```

## 💻 开发指南

- [架构概览](./docs/architecture/overview.md) - 项目架构
- [开发环境搭建](./docs/development/setup.md) - 环境配置和依赖管理
- [代码风格和注释规范](./docs/development/code-style.md) - 编码规范和注释要求
- [测试指南](./docs/development/testing.md) - 测试框架和最佳实践
- [命令行工具](./docs/development/cli-tools.md) - CLI工具使用和开发
- [领域服务](./src/bk_monitor_base/domains/README.md) - 业务领域模块说明
- [测试文档](./src/bk_monitor_base/tests/README.md) - 测试相关说明

## 🔗 相关链接

- [项目主页](https://github.com/TencentBlueKing/bk-monitor)
- [蓝鲸智云官网](https://bk.tencent.com/)

