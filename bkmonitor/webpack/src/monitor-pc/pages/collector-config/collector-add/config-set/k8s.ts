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
const PLUGIN_PARAMS = [
  {
    name: window.i18n.t('云产品'),
    required: true,
    type: 'list',
    key: 'tencent_cloud_product',
    field: 'products',
    default: [],
    election: [
      { id: 'QCE/CMONGO', name: '数据库MongoDB' },
      { id: 'QCE/CDB', name: '数据库MySQL(CDB)' },
      { id: 'QCE/REDIS', name: 'Redis标准版' },
      { id: 'QCE/REDIS_CLUSTER', name: 'Redis集群版' },
      { id: 'QCE/REDIS_MEM', name: '数据库Redis(内存版)' },
      { id: 'QCE/CVM', name: '云服务器CVM' },
      { id: 'QCE/COS', name: 'COS' },
      { id: 'QCE/CDN', name: 'CDN' },
      { id: 'QCE/LB_PUBLIC', name: '负载均衡CLB(公网)' },
      { id: 'QCE/LOADBALANCE', name: '负载均衡CLB(7层)' },
      { id: 'QCE/NAT_GATEWAY', name: 'NAT网关' },
      { id: 'QCE/DC', name: '物理专线' },
      { id: 'QCE/DCX', name: '专用通道' },
      { id: 'QCE/CBS', name: '云硬盘' },
      { id: 'QCE/SQLSERVER', name: '数据库SQL Server' },
      { id: 'QCE/MARIADB', name: '数据库MariaDB' },
      { id: 'QCE/CES', name: 'Elasticsearch' },
      { id: 'QCE/CMQ', name: 'CMQ 队列服务' },
      { id: 'QCE/CMQTOPIC', name: 'CMQ 主题订阅' },
      { id: 'QCE/POSTGRES', name: '数据库PostgreSQL' },
      { id: 'QCE/CKAFKA', name: 'CKafka 实例' },
      { id: 'QCE/MEMCACHED', name: 'Memcached' },
      { id: 'QCE/LIGHTHOUSE', name: '轻量应用服务器Lighthouse' },
      { id: 'QCE/TDMYSQL', name: '分布式数据库 TDSQL MySQL' },
      { id: 'QCE/LB', name: '弹性公网 IP' },
      { id: 'QCE/TDMQ', name: '消息队列RocketMQ版' },
      { id: 'QCE/VPNGW', name: 'VPN 网关' },
      { id: 'QCE/VPNX', name: 'VPN 通道' },
      { id: 'QCE/CYNOSDB_MYSQL', name: 'CYNOSDB_MYSQL' },
      { id: 'QCE/VBC', name: '云联网' },
      { id: 'QCE/DTS', name: '数据传输' },
      { id: 'QCE/DCG', name: '专线网关' },
      { id: 'QCE/QAAP', name: '全球应用加速' },
      { id: 'QCE/WAF', name: 'Web应用防火墙' },
      { id: 'QCE/LB_PRIVATE', name: '负载均衡CLB(内网)' },
    ],
    validate: { isValidate: false, content: '' },
  },
  {
    name: 'secretId',
    required: true,
    type: 'text',
    field: 'secret_id',
    default: '',
    validate: { isValidate: false, content: '' },
  },
  {
    name: 'secretKey',
    required: true,
    type: 'text',
    field: 'secret_key',
    default: '',
    validate: { isValidate: false, content: '' },
  },
  {
    name: 'region',
    required: true,
    type: 'text',
    field: 'region',
    default: '',
    validate: { isValidate: false, content: '' },
  },
];
export const getK8sPluginParams = () => {
  return structuredClone(PLUGIN_PARAMS);
};
