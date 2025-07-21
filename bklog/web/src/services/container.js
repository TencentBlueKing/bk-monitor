/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

/**
 * 容器日志接口
 */

// 新建容器日志
const create = {
  method: 'post',
  url: '/databus/collectors/',
};

// 更新容器日志
const update = {
  method: 'put',
  url: '/databus/collectors/:collector_config_id/',
};

// 获取容器日志详情
const getDetail = {
  method: 'get',
  url: '/databus/collectors/:collector_config_id/',
};

// 获取namespace列表
const getNameSpace = {
  method: 'get',
  url: '/databus/collectors/list_namespace/',
};

// 获取 集群-node树或集群-namespace-pod列表
const getPodTree = {
  method: 'get',
  url: '/databus/collectors/list_topo/',
};

// 获取node 标签列表
const getNodeLabelList = {
  method: 'get',
  url: '/databus/collectors/get_labels/',
};

// 获取标签命中的结果
const getHitResult = {
  method: 'post',
  url: '/databus/collectors/match_labels/',
};

// 获取workload类型
const getWorkLoadType = {
  method: 'get',
  url: '/databus/collectors/list_workload_type/',
};

// 获取workload name
const getWorkLoadName = {
  method: 'get',
  url: '/databus/collectors/get_workload/',
};

// 获取bcs集群列表
const getBcsList = {
  method: 'get',
  url: '/databus/collectors/list_bcs_clusters/',
};

// yaml判断
const yamlJudgement = {
  method: 'post',
  url: '/databus/collectors/validate_container_config_yaml/',
};

// ui配置转yaml base64
const containerConfigsToYaml = {
  method: 'post',
  url: 'databus/collectors/container_configs_to_yaml/',
};

// 预览
const getLabelHitView = {
  method: 'post',
  url: '/databus/collectors/preview_containers/',
};

export {
  create,
  update,
  getDetail,
  getNameSpace,
  getPodTree,
  getNodeLabelList,
  getHitResult,
  getWorkLoadType,
  getWorkLoadName,
  getBcsList,
  yamlJudgement,
  containerConfigsToYaml,
  getLabelHitView,
};
