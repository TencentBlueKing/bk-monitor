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

import Alert from '../../../static/img/failure/icon-alert.svg';
import NodeHost from '../../../static/img/failure/icon-BCSNode.svg';
import BcsService from '../../../static/img/failure/icon-BCSService.svg';
import IdcSvg from '../../../static/img/failure/icon-mc-target-cloud.svg';
import PodSvg from '../../../static/img/failure/icon-Pod.svg';
import RackSvg from '../../../static/img/failure/icon-Rack.svg';

export const NODE_TYPE_SVG = {
  Idc: IdcSvg,
  IdcUnit: IdcSvg,
  Rack: RackSvg,
  BcsService,
  Unknown: BcsService,
  BkNodeHost: NodeHost,
  BcsNode: NodeHost,
  BcsPod: PodSvg,
  Alert: Alert,
};

export const NODE_TYPE_ICON = {
  Idc: 'icon-mc-target-cloud',
  IdcUnit: 'icon-mc-target-cloud',
  Rack: 'icon-mc-rack',
  BkNodeHost: 'icon-mc-bcs-node',
  BcsNode: 'icon-mc-bcs-node',
  BcsPod: 'icon-mc-pod',
  BcsService: 'icon-mc-bcs-service',
  Unknown: 'icon-mc-bcs-service',
};
