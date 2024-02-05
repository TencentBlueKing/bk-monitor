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

import { IBaseInfo, TPluginTypeObj, TScenaris } from '../types';

import './detail-header.scss';

const HeaderFunctional = ctx => {
  const {
    props: { curStatusText, curFontColor, data },
    listeners: { install, viewEvent }
  } = ctx;
  const {
    name,
    label,
    createUser,
    popularity,
    updateUser,
    updateTime,
    logo,
    version,
    sourceCode,
    categoryDisplay,
    scenario,
    pluginType,
    isInstalled
  } = data as IBaseInfo;
  const { i18n } = window;

  const scenarioMap: TScenaris = {
    MONITOR: i18n.tc('监控工具'),
    REST_API: 'REST API',
    EMAIL: 'EMAIL'
  };

  const theWayMap: TPluginTypeObj = {
    http_pull: i18n.tc('拉取'),
    http_push: i18n.tc('推送'),
    email_pull: i18n.tc('拉取')
  };

  const getlogoText = (str: string) => str.slice(0, 1).toLocaleUpperCase();

  return (
    <div class='event-source-header'>
      <div class='header-left-wrap'>
        <span class='logo-wrap'>
          {logo ? (
            <img
              class='logo'
              src={`data:image/png;base64,${logo}`}
              alt='logo'
            />
          ) : (
            <div class='text-logo'>{getlogoText(name)}</div>
          )}
          <span class='logo-status'>
            <span
              style={`color: ${curFontColor}`}
              class='status-text'
            >
              {curStatusText}
            </span>
          </span>
        </span>
      </div>
      <div class='header-right-wrap'>
        <div class='title-wrap'>
          <span class='title'>{name}</span>
          <span class='version-wrap'>
            {sourceCode ? (
              <span class='src-code'>
                <i class='icon-monitor icon-icon_12_source'></i>
                {i18n.t('源码')}
              </span>
            ) : undefined}
            {version ? <span class='version'>V 1.0.1</span> : undefined}
          </span>
        </div>
        <table class='info-table'>
          <tbody>
            <tr>
              <td
                class='label'
                style='width: 51px'
              >
                {i18n.t('类型')}
              </td>
              <td class='value'>{categoryDisplay || ''}</td>
              <td
                class='label right'
                style='width: 120px;'
              >
                {i18n.t('作者')}
              </td>
              <td class='value'>{createUser}</td>
              <td class='label right'>{i18n.t('热度')}</td>
              <td class='value'>
                <i class='icon-monitor icon-icon_12_heat'></i>
                {popularity}
              </td>
            </tr>
            <tr>
              <td
                class='label'
                style='width: 51px'
              >
                {i18n.t('分类')}
              </td>
              <td class='value'>{scenarioMap[scenario] || scenario}</td>
              <td class='label right'>{i18n.t('最近更新人')}</td>
              <td class='value'>{updateUser}</td>
              <td class='label right'>{i18n.t('最近更新时间')}</td>
              <td class='value'>{updateTime}</td>
            </tr>
            <tr>
              <td
                class='label'
                style='width: 51px'
              >
                {i18n.t('方式')}
              </td>
              <td class='value'>{theWayMap[pluginType] || pluginType}</td>
              <td class='label right'>{i18n.t('标签')}</td>
              <td
                class='value'
                colspan={3}
              >
                <div class='label-list-wrap'>
                  {/* <span class="label">{i18n.t('标签')}</span> */}
                  <span class='value value-list'>
                    {label.map(item => (
                      <span class='value-item'>{item}</span>
                    ))}
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class='operate-wrap'>
        {!isInstalled ? (
          <bk-button
            theme='primary'
            onClick={() => install()}
          >
            {i18n.t('安装')}
          </bk-button>
        ) : (
          <bk-button
            theme='primary'
            outline
            onClick={() => viewEvent()}
          >
            {i18n.t('查看数据')}
          </bk-button>
        )}
      </div>
    </div>
  );
};
export default HeaderFunctional;
