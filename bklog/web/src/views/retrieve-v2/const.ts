export const getDefaultRetrieveParams = () => {
  const currentTime = Math.floor(new Date().getTime() / 1000);
  const startTime = currentTime - 15 * 60;
  const endTime = currentTime;

  return {
    keyword: '*', // 搜索关键字
    start_time: startTime, // 时间范围，格式 YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z]
    end_time: endTime, // 时间范围
    host_scopes: {
      // ip 快选，modules 和 ips 只能修改其一，另一个传默认值
      // 拓扑选择模块列表，单个模块格式 {bk_inst_id: 2000003580, bk_obj_id: 'module'}
      modules: [],
      // 手动输入 ip，多个 ip 用英文 , 分隔
      ips: '',
      // 目标节点
      target_nodes: [],
      // 目标节点类型
      target_node_type: '',
    },
    ip_chooser: {},
    addition: [],
    begin: 0,
    size: 500,
    interval: 'auto', // 聚合周期
  };
}

export const DEFAULT_RETRIEVE_PARAMS = getDefaultRetrieveParams();
