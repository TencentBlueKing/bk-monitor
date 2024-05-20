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
import './alarm-dispatch-action.scss';
// import { getCookie } from 'monitor-common/utils/utils';

const AlarmDispatchAction = ctx => {
  const {
    props: {
      actions = [],
      alarmGroupList = [],
      showAlarmGroup = () => {},
      showDetail = () => {},
      processPackage = [],
      userType = '',
    },
  } = ctx;
  const { i18n } = window;

  // const language = getCookie('blueking_language') || 'zhCN';

  const noticeConfig = actions.find(item => item.action_type === 'notice') || {};
  const processConfig = actions.find(item => item.action_type === 'itsm') || {};

  const userTypeMap = {
    main: i18n.t('负责人'),
    follower: i18n.t('关注人'),
  };

  const getAlarmGroupNames = (id: number) => alarmGroupList.find(item => item.id === id)?.name || '';

  const getProcessPackageName = (id: number) => processPackage.find(item => item.id === id)?.name || id;
  return (
    <div class='alarm-dispatch-action'>
      <div class='action-row'>
        <span>{i18n.t(noticeConfig?.upgrade_config?.is_enabled ? '通知升级' : '通知')} : </span>
        {noticeConfig?.is_enabled ? (
          <span>
            {noticeConfig?.upgrade_config?.is_enabled ? (
              <span>
                {i18n.t('间隔{0}分钟，逐个通知', { 0: noticeConfig.upgrade_config?.upgrade_interval })}
                {noticeConfig.upgrade_config?.user_groups.map((item, index) => (
                  <span>
                    <span
                      class='package'
                      onClick={() => {
                        showAlarmGroup(item);
                      }}
                    >
                      {' '}
                      {getAlarmGroupNames(item)}
                    </span>
                    {noticeConfig.upgrade_config?.user_groups.length - 1 !== index && <span> , </span>}
                  </span>
                ))}
              </span>
            ) : (
              i18n.t('直接通知')
            )}
          </span>
        ) : (
          <span>{i18n.t('关闭通知')}</span>
        )}
      </div>
      <div class='action-row'>
        <span>{i18n.t('流程服务')} : </span>
        {processConfig.action_id ? (
          <span
            class='package'
            onClick={() => showDetail(processConfig.action_id)}
          >
            {getProcessPackageName(processConfig.action_id)}
          </span>
        ) : (
          <span>{i18n.t('未配置')}</span>
        )}
      </div>
      {!!userType && (
        <div class='action-row'>
          <span>{i18n.t('通知人员类型')} : </span>
          <span>{userTypeMap?.[userType] || userType}</span>
        </div>
      )}
    </div>
  );
};

export default AlarmDispatchAction;
