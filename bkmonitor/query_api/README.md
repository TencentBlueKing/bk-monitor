# query api

## Overview

query api 是蓝鲸监控数据链路中的查询模块。允许用户通过SQL或者ES DSL查询接入蓝鲸监控的数据。

> 该模块提供的数据查询API，属于蓝鲸监控api的一部分，均接入ESB。

支持的数据类型：

- 时序数据
- 日志数据（todo）

## API

本模块不单独提供API，仅实现Resource供kenrel_api模块下的[views](kernel_api/views/query.py)调用。

> [数据查询API文档](docs/api/apidocs/zh_hans/get_ts_data.md)

## Runing Test

```shell
cd ${project_root}
pytest --cov=query_api -vv query_api
```


## Design

![query_api_design.png](docs/resource/img/query_api_design.png)
