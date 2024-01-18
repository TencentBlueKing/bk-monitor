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

import { getCookie } from '../../../../monitor-common/utils/utils';
import { LEVELLIST } from '../typing';

import './alarm-update-content.scss';

const { i18n } = window;

const AlarmUpdateContent = ctx => {
  const {
    props: { severity, tag }
  } = ctx;
  const language = getCookie('blueking_language') || 'zhCN';

  const level = LEVELLIST.find(item => item.value === severity);
  return (
    <div class='alarm-update-content'>
      {tag.length || severity !== 0 ? (
        <span class='alarm-update-content-wrap'>
          {severity > 0 && (
            <span>
              <span
                class='content-label'
                style={{ width: language === 'en' ? '104px' : '56px' }}
              >
                {i18n.t('等级调整')} :{' '}
              </span>
              <span>
                <i
                  class={`icon-common ${level.icon}`}
                  style={{ color: level.color }}
                ></i>
                <span>{level.name}</span>
              </span>
            </span>
          )}
          {tag.length > 0 ? (
            <span>
              <span
                class='content-label'
                style={{ width: language === 'en' ? '104px' : '56px' }}
              >
                {i18n.t('追加标签')} :{' '}
              </span>
              {tag.map((item, index) => (
                <bk-tag key={index}>{`${item.key}:${item.value}`}</bk-tag>
              ))}
            </span>
          ) : null}
        </span>
      ) : (
        <span>{i18n.t('无')}</span>
      )}
    </div>
  );
};

export default AlarmUpdateContent;
