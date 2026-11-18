# 容器日志采集

只用于接入类型 = 容器日志采集（容器内文件或节点文件）。不是容器标准输出。

`environment=container`。存储、清洗、名称、数据名、行/段日志、路径、字符集、采集范围、上报链路与主机相同，见 SKILL 第 4、5 节和 [clean.md](clean.md)。

## 与主机的唯一差别

采集目标不用 IP / 拓扑。用户用配置圈定 **Container** 和 **Node** 范围。范围规则必填；没有可执行的范围就停，不要提交。

| 用户圈选 | `configs[].collector_type` | 路径 |
| --- | --- | --- |
| 容器内文件、Container | `container_log_config` | `configs[].params.paths` 必填 |
| 节点文件、Node、宿主机路径 | `node_log_config` | `configs[].params.paths` 必填 |

两种可以同时存在（多条 `configs`）。没说清采容器还是节点时要问。

集群 ID → `bcs_cluster_id`，创建后不可改。圈范围必须先有集群；用户没给就问。

## 范围怎么圈

把用户配置翻译成规则，缺的问，不要把「没说」理解成「全选」——除非用户明确说全部命名空间 / 全部容器。

**Container 范围**（`container_log_config`）

| 用户配置 | 写入 |
| --- | --- |
| 命名空间 / 排除命名空间 | `namespaces` / `namespaces_exclude`（互斥） |
| 工作负载类型、名称 | `container.workload_type`、`container.workload_name` |
| 容器名 / 排除容器名 | `container.container_name` / `container.container_name_exclude`（互斥） |
| Pod 标签 | `label_selector`（`match_labels` / `match_expressions`） |
| Pod 注解 | `annotation_selector` |

空选择器也要显式带上（空数组），更新时不要省略，否则可能报错。

**Node 范围**（`node_log_config`）

按用户给出的节点侧圈选原样写入确认表单和配置。共享集群不能空命名空间。不要把节点范围写成主机 IP 列表。

## 确认表单里怎么展示范围

不要写「采集目标：11.x.x.x」。用「采集配置范围」**竖表**（配置项 / 内容），禁止横表。一条 config 一张表，多条编号。完整表单见 [confirm-forms.md](confirm-forms.md)。

```markdown
### 采集配置范围 1

| 配置项 | 内容 |
| --- | --- |
| 对象 | Container |
| 集群 | BCS-K8S-00000 |
| 命名空间 | blueking |
| 工作负载 | Deployment / demo-web |
| 容器名 | |
| 标签 | app = demo-web |
| 日志路径 | /var/log/app/*.log |

### 采集配置范围 2

| 配置项 | 内容 |
| --- | --- |
| 对象 | Node |
| 集群 | BCS-K8S-00000 |
| 命名空间 | |
| 工作负载 | |
| 容器名 | |
| 标签 | kubernetes.io/hostname = node-1 |
| 日志路径 | /var/log/kubelet.log |
```

用户改范围后更新对应竖表，再确认。
