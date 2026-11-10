/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
 * 【MOCK】POST /rest/v2/collecting_config/validate_tencent_cloud_configmap/
 *
 * 真实接口上线后，将调用方的 import 替换为生成的 API 即可：
 *   import { validateTencentCloudConfigmap } from 'monitor-api/modules/collecting';
 *
 * 与 monitor-api `request()` 保持一致：入参 (data, config)，成功时直接返回业务 data。
 * 返回结构对齐联调清单 5.2 / 5.3；校验规则是对后端规则的简化模拟，仅用于前端联调。
 */
import type {
  IFileCheckError,
  IUploadedFile,
  IValidateFileResult,
  IValidateResult,
} from '../utils/multi-file-upload-utils';

interface IValidateParams {
  bk_biz_id?: number | string;
  /** 编辑时传：源部署版本 */
  deployment_id?: number;
  /** 编辑时传：采集配置 ID */
  id?: number;
  params: {
    collector: { period: number; timeout: number };
    plugin: { config_mode: string; configmaps: IUploadedFile[] };
  };
}

const MOCK_DELAY = 600;

/** 取 `qcloud.yml: |` 之后的缩进块并去除公共缩进 */
const extractQcloudYaml = (content: string): null | string => {
  const lines = content.split('\n');
  const start = lines.findIndex(line => /^\s*qcloud\.yml:\s*\|/.test(line));
  if (start < 0) return null;
  const block: string[] = [];
  for (const line of lines.slice(start + 1)) {
    if (line.trim() && !/^\s{2,}/.test(line)) break;
    block.push(line);
  }
  const indent = Math.min(...block.filter(line => line.trim()).map(line => line.match(/^\s*/)[0].length));
  return `${block
    .map(line => line.slice(indent))
    .join('\n')
    .trim()}\n`;
};

const validateFile = (file: IUploadedFile, existed: IUploadedFile[]): IValidateFileResult => {
  const errors: IFileCheckError[] = [];
  const { content } = file;
  const duplicated = existed.find(item => item.content === content);
  if (duplicated) {
    errors.push({
      code: 'DUPLICATE_FILE',
      path: 'content',
      message: '文件内容已存在，请保留一份',
      related_uid: duplicated.uid,
    });
  }
  if (!/^kind:\s*ConfigMap\s*$/m.test(content)) {
    errors.push({ code: 'CONFIGMAP_KIND_INVALID', path: 'kind', message: '仅支持 v1 ConfigMap 资源' });
  }
  const qcloudYaml = extractQcloudYaml(content);
  if (!qcloudYaml) {
    errors.push({ code: 'CONFIGMAP_DATA_INVALID', path: 'data', message: 'data 中缺少 qcloud.yml' });
  } else {
    for (const key of ['access_key', 'secret_key']) {
      if (new RegExp(`^\\s*${key}:\\s*["']?[^"'\\s]+`, 'm').test(qcloudYaml)) {
        errors.push({
          code: 'CREDENTIAL_IN_CONFIGMAP',
          path: `data.qcloud.yml.credential.${key}`,
          message: '配置文件中不能包含腾讯云密钥，请在页面填写',
        });
      }
    }
    const products = [...qcloudYaml.matchAll(/^\s*-?\s*namespace:\s*(\S+)/gm)].map(match => match[1]);
    if (!products.length) {
      errors.push({
        code: 'QCLOUD_CONFIG_INVALID',
        path: 'data.qcloud.yml.products',
        message: 'products 不能为空，且每项需包含 namespace',
      });
    }
    if (products.some(item => /etcd/i.test(item))) {
      errors.push({
        code: 'PRODUCT_NOT_SUPPORTED',
        path: 'data.qcloud.yml.products',
        message: '暂不支持 etcd 产品',
      });
    }
    if (!errors.length) {
      return {
        uid: file.uid,
        filename: file.filename,
        valid: true,
        summary: { region: qcloudYaml.match(/^\s*region:\s*(\S+)/m)?.[1] ?? '', products },
        preview: { qcloud_yaml: qcloudYaml, credential_source: 'secret_env' },
        errors: [],
      };
    }
  }
  return { uid: file.uid, filename: file.filename, valid: false, summary: null, preview: null, errors };
};

export const validateTencentCloudConfigmap = (data: IValidateParams, _config?: Record<string, unknown>) =>
  new Promise<IValidateResult>(resolve => {
    setTimeout(() => {
      const { collector, plugin } = data.params;
      const configmaps = plugin.configmaps || [];
      const errors: IFileCheckError[] = [];
      if (!configmaps.length) {
        errors.push({
          code: 'CONFIGMAP_REQUIRED',
          path: 'params.plugin.configmaps',
          message: '请至少上传一份有效配置文件',
        });
      }
      if (Number(collector.timeout) > Number(collector.period)) {
        errors.push({
          code: 'TIMEOUT_INVALID',
          path: 'params.collector.timeout',
          message: '超时时间不能大于采集周期',
        });
      }
      const files = configmaps.map((file, index) => validateFile(file, configmaps.slice(0, index)));
      resolve({ valid: !errors.length && files.every(file => file.valid), errors, files });
    }, MOCK_DELAY);
  });
