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
import { reactive } from 'vue';
import { useI18n } from 'vue-i18n';

import { LEVEL_LIST, STATUS_LIST } from '../constant';

/** 文案对应表 */
export const typeTextMap = {
  incident_create: '生成故障，包含{alert_count}个告警，故障负责人：{assignees}',
  incident_observe: '故障观察中，剩余观察时间{last_minutes}分钟',
  incident_recover: '故障已恢复',
  incident_notice: '故障通知已发送（接收人：{receivers}）',
  incident_merge: '故障{merged_incident_name}被合并入当前故障',
  incident_update: '{operator}故障属性{incident_key_alias}: 从{from_value}被修改为{to_value}',
  alert_trigger: '检测到新告警（{alert_name}）',
  alert_recover: '告警已恢复（{alert_name}）',
  alert_invalid: '告警已失效（{alert_name}）',
  alert_notice: '告警通知已发送（{alert_name}；接收人：{receivers}）',
  alert_convergence: '告警已收敛（共包含{converged_count}个关联的告警事件）',
  manual_update: '{operator}故障属性{incident_key_alias}: 从{from_value}被修改为{to_value}',
  feedback: '反馈根因：{feedback_incident_root}',
  incident_close: '故障已关闭',
  group_gather: '一键拉群（{group_name}）',
  alert_confirm: '告警已确认（{alert_name}）',
  alert_shield: '告警已屏蔽（{alert_name}）',
  alert_handle: '告警已被手动处理（{alert_name}）',
  alert_close: '告警已被关闭（{alert_name}）',
  alert_dispatch: '告警已分派（{alert_name}；处理人：{handlers}）',
};
/** 渲染tag */
export const renderHandlers = handles => {
  return handles?.length
    ? handles.map(tag => (
        <span
          key={tag}
          class='tag-item'
        >
          {tag}
        </span>
      ))
    : '--';
};

/** 渲染人员相关tag */
export const renderHandlersForUser = handles => {
  return handles?.length
    ? handles.map(tag => (
        <bk-user-display-name
          key={tag}
          class='tag-item'
          user-id={tag}
        />
      ))
    : '--';
};

export const handleFun = (data, callback) => {
  callback?.(data);
  const node = JSON.parse(JSON.stringify({ ...data }));
  node.id = data.alert_id;
  window.__BK_WEWEB_DATA__?.showDetailSlider?.(node);
};

/** 点击跳转到告警tab */
export const handleDetail = (e, data, id, bizId, callback) => {
  e.stopPropagation();
  callback?.(data);
  // const word = '?tab=FailureView';
  // const key = location.hash.indexOf(word) === -1 ? word : '';
  // const routeUrl = `${location.hash}${key}`;
  // const url = `${location.origin}${location.pathname}?bizId=${bizId}${routeUrl}`;
  // window.location.href = url;
};
/** 点击告警名 */
export const handleAlertName = (extra_info, callback) => {
  return (
    <span
      class='link cursor'
      onClick={() => handleFun(extra_info, callback)}
    >
      {extra_info.alert_name}
    </span>
  );
};
/** 修改故障属性的渲染函数  */
const handleUpdate = ({ extra_info, operator }) => {
  const { t } = useI18n();
  const { incident_key_alias, from_value, to_value, incident_key } = extra_info;
  const isLevel = incident_key === 'level';
  const isStatus = incident_key === 'status';
  const isIncidentName = incident_key === 'incident_name';
  const statusTag = val => {
    let info: any = {};
    if (isLevel) {
      info = LEVEL_LIST[val];
    }
    if (isStatus) {
      info = STATUS_LIST[val];
    }
    return (
      <span
        style={{ background: info.bgColor, color: info?.color || '#fff' }}
        class='status-tag'
      >
        <i class={`icon-monitor icon-${info.icon} sign-icon`} />
        {t(info.label)}
      </span>
    );
  };
  const className = isIncidentName ? 'tag-txt' : 'tag-item';
  const handleValue = val => {
    return Array.isArray(val) ? val.map(item => item.replace(/\//g, '')).join('、') : val;
  };
  const toValue = isLevel || isStatus ? statusTag(to_value) : <span class={className}>{handleValue(to_value)}</span>;
  const fromValue =
    (isLevel || isStatus) && !!from_value ? (
      statusTag(from_value)
    ) : (
      <span class={className}>{handleValue(from_value) || 'null'}</span>
    );
  return (
    <i18n-t
      v-slots={{
        operator: () => (operator ? <span class='tag-wrap'>{renderHandlers([operator])}</span> : ''),
        incident_key_alias: () => <span class='tag-bold'>{t(incident_key_alias)}</span>,
        from_value: () => fromValue,
        to_value: () => toValue,
      }}
      keypath={typeTextMap.incident_update}
    />
  );
};
/** 各类型文案渲染函数 */
export const renderMap = reactive({
  incident_create: ({ extra_info }, id, bizId, callback) => {
    return (
      <i18n-t
        v-slots={{
          alert_count: () => (
            <span
              class='count link cursor'
              onClick={e => handleDetail(e, extra_info, id, bizId, callback)}
            >
              {extra_info.alert_count}
            </span>
          ),
          assignees: () => <span class='tag-wrap'>{renderHandlersForUser(extra_info.assignees)}</span>,
        }}
        keypath={typeTextMap.incident_create}
      />
    );
  },
  incident_observe: ({ extra_info }) => {
    return (
      <i18n-t
        v-slots={{
          last_minutes: <span class='count'>{extra_info?.last_minutes || 0}</span>,
        }}
        keypath={typeTextMap.incident_observe}
      />
    );
  },
  incident_recover: () => {
    return <span>{typeTextMap.incident_recover}</span>;
  },
  incident_notice: ({ extra_info }) => {
    return (
      <i18n-t
        v-slots={{
          receivers: () => <span class='tag-wrap'>{renderHandlersForUser(extra_info.receivers)}</span>,
        }}
        keypath={typeTextMap.incident_notice}
      />
    );
  },
  incident_merge: ({ extra_info }) => {
    return (
      <i18n-t
        v-slots={{
          merged_incident_name: <span>{extra_info?.merged_incident_name || ''}</span>,
        }}
        keypath={typeTextMap.incident_merge}
      />
    );
  },
  incident_update: handleUpdate,
  alert_trigger: ({ extra_info }, id, bizId, callback) => {
    return (
      <i18n-t
        v-slots={{
          alert_name: () => handleAlertName(extra_info, callback),
        }}
        keypath={typeTextMap.alert_trigger}
      />
    );
  },
  alert_recover: ({ extra_info }, id, bizId, callback) => {
    return (
      <i18n-t
        v-slots={{
          alert_name: () => handleAlertName(extra_info, callback),
        }}
        keypath={typeTextMap.alert_recover}
      />
    );
  },
  alert_invalid: ({ extra_info }, id, bizId, callback) => {
    return (
      <i18n-t
        v-slots={{
          alert_name: () => handleAlertName(extra_info, callback),
        }}
        keypath={typeTextMap.alert_invalid}
      />
    );
  },
  alert_notice: ({ extra_info }, id, bizId, callback) => {
    const { receivers } = extra_info;
    return (
      <i18n-t
        v-slots={{
          alert_name: () => handleAlertName(extra_info, callback),
          receivers: () => <span class='tag-wrap'>{renderHandlersForUser(receivers)}</span>,
        }}
        keypath={typeTextMap.alert_notice}
      />
    );
  },
  alert_convergence: ({ extra_info }, id, bizId, callback) => {
    const { converged_count } = extra_info;
    return (
      <i18n-t
        v-slots={{
          alert_name: () => handleAlertName(extra_info, callback),
          converged_count: () => <span class='count'>{converged_count}</span>,
        }}
        keypath={typeTextMap.alert_convergence}
      />
    );
  },
  // <-- 以下为人工事件  -->
  manual_update: handleUpdate,
  feedback: ({ extra_info }) => {
    const { t } = useI18n();
    const { feedback_incident_root, content, is_cancel } = extra_info;
    if (is_cancel) {
      return <span>{t('取消反馈根因')}</span>;
    }
    return (
      <i18n-t
        v-slots={{
          feedback_incident_root: () => (
            <span>
              {feedback_incident_root}
              {content ? ':' : ''}
              {content}
            </span>
          ),
        }}
        keypath={typeTextMap.feedback}
      />
    );
  },
  incident_close: () => {
    const { t } = useI18n();
    return <span>{t(typeTextMap.incident_close)}</span>;
  },
  group_gather: ({ extra_info }) => {
    return (
      <i18n-t
        v-slots={{
          group_name: () => <span class='tag-wrap'>{renderHandlers(extra_info.group_name)}</span>,
        }}
        keypath={typeTextMap.group_gather}
      />
    );
  },
  alert_confirm: ({ extra_info }, id, bizId, callback) => {
    return (
      <i18n-t
        v-slots={{
          alert_name: () => handleAlertName(extra_info, callback),
        }}
        keypath={typeTextMap.alert_confirm}
      />
    );
  },
  alert_shield: ({ extra_info }, id, bizId, callback) => {
    return (
      <i18n-t
        v-slots={{
          alert_name: () => handleAlertName(extra_info, callback),
        }}
        keypath={typeTextMap.alert_shield}
      />
    );
  },
  alert_handle: ({ extra_info }, id, bizId, callback) => {
    return (
      <i18n-t
        v-slots={{
          alert_name: () => handleAlertName(extra_info, callback),
        }}
        keypath={typeTextMap.alert_handle}
      />
    );
  },
  // 告警关闭
  alert_close: ({ extra_info }, id, bizId, callback) => {
    return (
      <i18n-t
        v-slots={{
          alert_name: () => handleAlertName(extra_info, callback),
        }}
        keypath={typeTextMap.alert_close}
      />
    );
  },
  alert_dispatch: ({ extra_info }, id, bizId, callback) => {
    const { handlers } = extra_info;
    return (
      <i18n-t
        v-slots={{
          alert_name: () => handleAlertName(extra_info, callback),
          handlers: () => <span class='tag-wrap'>{renderHandlersForUser(handlers)}</span>,
        }}
        keypath={typeTextMap.alert_dispatch}
      />
    );
  },
});
/** 将动态文案填入 */
export const replaceStr = (str, extra_info) => {
  return str.replace(/{(\w+)}/g, (match, key) => {
    // 检查这个键是否在对象中
    if (key in extra_info) {
      return extra_info[key]; // 如果是，则替换为对象中的值
    }
    return match; // 如果不是，则不替换，返回原始匹配字符串
  });
};
