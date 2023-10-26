# 代码架构



## Overview

![代码架构图](../resource/img/code.png)

代码分为三层：应用层、资源层、适配层。

## 应用层

应用层按应用类型分为：web、alarm backends

- web：web 应用服务
- alarm backends：告警后台服务

### web

web应用服务根据应用场景，细分为：

- [frontend](#)：基于蓝鲸PaaS平台托管的蓝鲸监控SaaS的web后台服务，为前端提供api
- [api services](#)：可单独部署的api 服务

### alarm backends

- [告警后台](#)

## 资源层

资源层主要给应用层提供通用业务逻辑。

## 适配层

适配层主要实现各依赖模块对应的原子api，供资源层resource调用组装。

## 公共模块

### models

- db模型定义
- 蓝鲸监控内部数据模型定义

### utils

工具函数

### core

框架

## healthz

自监控服务

## 资源模板

### static

### template(todo 需要去掉)

## 其他

- docs
- scripts
- locale
- tests

----

## 这是一个示例

- docs
	- api
		- apidocs
		- extend

- scripts	
	- githooks
	- pack
- locale
- utils
	- common				// 通用工具类
		- patchs
			- monkey.py
	- host.py
- models
- resource
	- cc
		- resource.py
		- models.py
	- job
	- bkmonitor
		- plugin
	- bkdata
- adapter
	- cc
		- define.py
		- enterprise
		- community
		- tencent
	- job
- core
	- esb 	// 剥离sdk
- conf
- web
	- account
	- metadata
	- query
	- api_service
	- frontend
		- plugin
		- weixin
- healthz
- alarm_backends
- tests
- template
- static