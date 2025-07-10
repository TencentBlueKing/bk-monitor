
export const aiContent = [
  {
    key: 1,
    title: '告警问题',
    label:
      '当前服务 (activity-microservices.msgcenter) 调用接口(trpc.cj.trpc2s.activitiyscvr/SendAwardSync) 的成功率为 65%',
  },
  {
    key: 2,
    title: '告警原因',
    label: '被调接口 (trpc.cj.trpc2s.activitiyscvr/SendAwardSync) 服务所在主机 10.0.2.12 网络不通导致',
  },
  { key: 3, title: '关联故障', label: '【Pod】BcsPod(activity-10111-deployment-bys)引起的故障', link: true },
  { key: 4, title: '关联故障', label: '', link: true },
  { key: 5, title: '处理建议', label: '我是一个文本占位' },
  { key: 6, title: '处理经验', label: '重启服务器 或 联系驻场维修检查服务器网络是否正常' },
  { key: 7, title: '处理经验', label: '', edit: true },
];

const data = [
  {
    key: 'name',
    value: 'VM-156-110-centos',
    label: '主机名',
  },
  {
    key: 'ip',
    value: '11.185.157.110',
    label: '目标IP',
  },

  {
    key: 'area',
    value: 0,
    label: '管控区域',
  },
  {
    key: 'key',
    value: 'Value 占位',
    label: 'Key占位',
  },
];
export const dimensional = [
  {
    name: '异常维度（组合）1',
    content: '拥有支撑数百款腾讯业务的经验沉淀，兼容各种复杂的系统架构，生于运维 · 精于运维',
    percentage: '90%',
    data,
    message: '可疑原因：在（2025-04-16 00:00:00 ～ 2025-04-17 00:00:00）时间段内，告警产生具有相似性。'
  },
  {
    name: '异常维度（组合）2',
    percentage: '80%',
    content:
      '从配置管理，到作业执行、任务调度和监控自愈，再通过运维大数据分析辅助运营决策，全方位覆盖业务运营的全周期保障管理。',
    data,
    message: '可疑原因：在（2025-04-16 00:00:00 ～ 2025-04-17 00:00:00）时间段内，告警产生具有相似性。'
  },
];
export const content = `### 错误情况
- tE monitor_web，incident，resources, fronted_resources. IncidentHandlersResource 这个 span 中，发生了一个类型为 TypeError 的异常。
- 异常信息为'<' not supported between instances of 'str' and 'int'. 这表明在代表中存在一个比较操作。试图将字符串和整数进行比较，导致了类型错误。

### 错误详情
- 异常类型：TypenError
- 异常信息：'<' not supported between instances of 'str' and 'int'

### 堆栈跟踪
TraranarkImnct rarant`;
