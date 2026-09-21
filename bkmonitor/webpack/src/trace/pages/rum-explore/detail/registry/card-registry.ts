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
import { RUM_OUTCOME_TYPE_MAP } from '../../constants';
import { formatUnitValueParts } from '../../utils';
import { RumCardToneEnum, RumRatingEnum } from '../typings';

import type {
  IRumCardDescriptor,
  IRumCardFooterPart,
  IRumCardResolveCtx,
  IRumRatingConfig,
  IRumSummaryCardVM,
} from '../typings';

const t = (text: string) => window.i18n.t(text) as string;

/** HTTP Method 前缀标签的配色，未登记的方法用中性灰 */
const HTTP_METHOD_COLOR: Record<string, string> = {
  GET: '#3A84FF',
  POST: '#3A84FF',
  PUT: '#F59500',
  PATCH: '#F59500',
  DELETE: '#EA3636',
};

/** 空值统一展示为短横线，与设计稿一致 */
const EMPTY_TEXT = '--';

const text = (value: unknown) => {
  if (value === null || value === undefined || value === '') return EMPTY_TEXT;
  return String(value);
};

/** 耗时字段以微秒存储，拆成数值与单位两段供卡片分别排版 */
const durationParts = (value: unknown) => formatUnitValueParts(value, 'us');

/** 首字母大写，用于把 img / cache 这类枚举值渲染成设计稿的 Img / Cache */
const capitalize = (value: string) => (value ? value.charAt(0).toUpperCase() + value.slice(1) : '');

/** 千分位数字，用于发生次数这类计数展示 */
const formatCount = (value: unknown) => {
  const num = Number(value);
  return Number.isFinite(num) ? num.toLocaleString('en-US') : EMPTY_TEXT;
};

/** XHR / Fetch 与静态资源的关键信息卡片形态不同，按资源类型区分 */
const isXhrLike = (ctx: IRumCardResolveCtx) => {
  const resourceType = String(ctx.originData?.attributes?.['resource.type'] ?? '').toLowerCase();
  return resourceType === 'xhr' || resourceType === 'fetch';
};

/**
 * Web Vitals 指标卡描述符工厂：主值为指标值，右上角按 rating_config 阈值挂评级标签，
 * 副文案为指标全称；extraFooter 用于 TTFB 追加分段耗时说明。
 */
const vitalCard = (): IRumCardDescriptor => data => {
  const metric = String(data['attributes.vital.metric'] ?? '').toLowerCase();
  const value = data['attributes.vital.value'];
  const hasValue = value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const configs = (data['display.rating_config'] ?? []) as IRumRatingConfig[];
  /** 按阈值命中评级，最后一段无上界，与评级条（buildRatingBar）同一口径；值缺失时不挂标签 */
  let hitRating = '';
  if (hasValue && configs.length) {
    hitRating = configs[configs.length - 1].rating;
    for (const config of configs) {
      if (config.value === undefined || Number(value) <= config.value) {
        hitRating = config.rating;
        break;
      }
    }
  }

  const ratingToneMap = {
    [RumRatingEnum.GOOD]: RumCardToneEnum.SUCCESS,
    [RumRatingEnum.NEEDS_IMPROVEMENT]: RumCardToneEnum.WARNING,
    [RumRatingEnum.POOR]: RumCardToneEnum.DANGER,
  };

  return [
    {
      label: metric.toUpperCase(),
      value: text(value),
      unit: { text: 'ms', tone: ratingToneMap[hitRating] },
      tone: ratingToneMap[hitRating],
      cardCls: `vital-card ${ratingToneMap[hitRating]}`,
    },
  ];
};

/**
 * 字段分组 -> 统计卡片的映射表。
 *
 * 查找按 `${spanType}.${sectionKey}.${groupKey}` -> `${sectionKey}.${groupKey}` -> `${groupKey}` 三级回退，
 * 都未命中时走 genericCardDescriptor 的通用渲染，因此后端新增分组不会白屏。
 * 新增 span 类型时只需在这里补分组条目，渲染组件无需改动。
 */
const CARD_DESCRIPTORS: Record<string, IRumCardDescriptor> = {
  /* ---------------- Resource ---------------- */

  /** 请求方法与路径：Method 色块 + URL 模板，右上角提供完整地址复制 */
  'key_info.request': (data, ctx) => {
    const method = String(data['attributes.http.request.method'] ?? '').toUpperCase();
    const fullUrl = String(data['attributes.url.full'] ?? '');
    const host = String(data['attributes.server.address'] ?? '');
    return [
      {
        label: t('Method · 路径'),
        value: text(data['attributes.url.template']),
        prefixTag: method ? { text: method, bgColor: HTTP_METHOD_COLOR[method] || '#8F9FBD' } : undefined,
        footer: host ? [{ text: `Host: ${host}` }] : undefined,
        operation: fullUrl ? { label: t('复制完整地址'), onClick: () => ctx.copyText(fullUrl) } : undefined,
        cardCls: 'request-method',
      },
    ];
  },

  /** 加载耗时：XHR / Fetch 场景标题为「总耗时」，静态资源为「加载耗时」 */
  'key_info.duration': (data, ctx) => {
    const { text: value, suffix } = durationParts(data.elapsed_time);
    return [
      {
        label: isXhrLike(ctx) ? t('总耗时') : t('加载耗时'),
        value: text(value),
        unit: suffix ? { text: suffix.trim() } : undefined,
        footer: [{ text: t('Resource Span 总耗时') }],
      },
    ];
  },

  /**
   * HTTP 结果：静态资源合并成一张「加载结果」卡；
   * XHR / Fetch 额外拆出「业务结果」卡，用于区分协议层成功但业务失败的场景。
   */
  'key_info.http_result': (data, ctx) => {
    const statusCode = data['attributes.http.response.status_code'];
    const outcome = String(data['attributes.outcome.type'] ?? '');
    const isSuccess = Number(statusCode) >= 200 && Number(statusCode) < 400;
    const tone = isSuccess ? RumCardToneEnum.SUCCESS : RumCardToneEnum.DANGER;
    const statusDesc = `HTTP ${text(statusCode)} · ${isSuccess ? 'OK' : t('失败')} · ${
      isSuccess ? t('协议层请求成功') : t('协议层请求失败')
    }`;
    if (!isXhrLike(ctx)) {
      return [
        {
          label: t('加载结果'),
          value: isSuccess ? t('加载成功') : t('加载失败'),
          tone,
          footer: [{ text: statusDesc, tone }],
        },
      ];
    }
    const outcomeMeta = RUM_OUTCOME_TYPE_MAP[outcome];
    return [
      {
        label: t('HTTP 状态'),
        value: text(statusCode),
        tone,
        footer: [{ text: statusDesc.replace(`HTTP ${text(statusCode)} · `, '') }],
      },
      {
        label: t('业务结果'),
        value: outcomeMeta ? ctx.formatField('attributes.outcome.type', outcome) || outcomeMeta.label : t('未采集'),
        tone: outcomeMeta ? RumCardToneEnum.DEFAULT : RumCardToneEnum.WARNING,
        footer: [{ text: t('业务码、状态与消息均未上报') }],
      },
    ];
  },

  /** 传输大小：主值取传输体积，副文案给出解压后体积与压缩率 */
  'key_info.transfer': data => {
    const { text: value, suffix } = formatUnitValueParts(data['attributes.resource.transfer_size'], 'bytes');
    const decoded = formatUnitValueParts(data['attributes.resource.decoded_body_size'], 'bytes');
    const ratio = Number(data['display.compression_ratio'] ?? 0);
    const footer: IRumCardFooterPart[] = [{ text: `${t('解压后')} ${decoded.text}${decoded.suffix} ·` }];
    if (Number.isFinite(ratio)) {
      footer.push({
        text: ` ${t('压缩')} ${(ratio * 100).toFixed(1)}%`,
        tone: ratio > 0 ? RumCardToneEnum.SUCCESS : RumCardToneEnum.DEFAULT,
      });
    }
    return [
      {
        label: t('传输大小'),
        value: text(value),
        unit: suffix ? { text: suffix.trim() } : undefined,
        footer,
      },
    ];
  },

  /** 交付类型：缓存 / 网络，副文案给出缓存命中情况 */
  'key_info.delivery': data => {
    const deliveryType = String(data['attributes.resource.delivery_type'] ?? '');
    const cacheHit = data['attributes.resource.cache.hit'];
    return [
      {
        label: t('交付类型'),
        value: capitalize(deliveryType) || EMPTY_TEXT,
        footer: [{ text: `${t('缓存命中')}：${cacheHit ? t('命中') : t('未命中')}` }],
      },
    ];
  },

  /** 渲染影响：资源是否阻塞渲染 */
  'key_info.blocking': data => {
    const status = String(data['attributes.resource.render_blocking_status'] ?? '');
    const isBlocking = status === 'blocking';
    return [
      {
        label: t('渲染影响'),
        value: status ? (isBlocking ? t('阻塞') : t('非阻塞')) : EMPTY_TEXT,
        tone: isBlocking ? RumCardToneEnum.WARNING : RumCardToneEnum.DEFAULT,
        footer: [{ text: `render_blocking_status - ${status || EMPTY_TEXT}` }],
      },
    ];
  },

  /* ---------------- Action ---------------- */

  /** 交互类型 */
  'key_info.interaction': data => [
    {
      label: t('交互类型'),
      value: capitalize(String(data['attributes.action.type'] ?? '')) || EMPTY_TEXT,
      footer: [{ text: 'event.type' }],
    },
  ],

  /** 目标元素：tag 与 name 不同时叠加 tag 前缀，相同时只展示 name 以避免重复 */
  'key_info.target': data => {
    const tag = String(data['attributes.action.target.tag'] ?? '');
    const name = String(data['attributes.action.target.name'] ?? '');
    return [
      {
        label: t('目标元素'),
        /** 走 text 的 EMPTY_TEXT 兜底，避免缺失字段被拼成 "undefined" */
        value: tag && tag !== name ? text(`${tag}${name}`) : text(name),
        footer: [{ text: 'CSS Selector' }],
      },
    ];
  },

  /* ---------------- Long Task ---------------- */

  /** 关联交互：Action ID 命中时展示回查到的目标元素名 */
  'long_task.key_info.action': (data, ctx) => {
    const actionName = String(ctx.related.actionName ?? '');
    const hasAction = !!data['attributes.action.id'];
    return [
      {
        label: t('关联交互'),
        value: actionName || EMPTY_TEXT,
        footer: [{ text: hasAction && actionName ? String(ctx.related.actionType ?? '') : t('未关联 Action') }],
      },
    ];
  },

  /** 任务耗时：主值为总耗时，副文案给出阻塞贡献 */
  'long_task.key_info.duration': data => {
    const { text: value, suffix } = durationParts(data.elapsed_time);
    const blocking = Number(data['attributes.long_task.blocking_duration'] ?? 0);
    return [
      {
        label: t('任务耗时'),
        value: text(value),
        unit: suffix ? { text: suffix.trim() } : undefined,
        footer: [{ text: `${t('阻塞贡献')} ${blocking}ms · ${t('超出 50ms 阈值')}` }],
      },
    ];
  },

  /**
   * 主要归因：Performance Entry 名称。
   * 名称与 entry_type 相同说明浏览器没有给出更具体的归因目标，标注为低可信度。
   */
  'key_info.attribution': data => {
    const name = String(data['attributes.long_task.name'] ?? '');
    const entryType = String(data['attributes.long_task.entry_type'] ?? '');
    return [
      {
        label: t('主要归因'),
        value: name || EMPTY_TEXT,
        footer: [{ text: 'Performance Entry name' }],
        tag: name && name !== entryType ? undefined : { text: t('低可信度'), color: '#E38B02', bgColor: '#FDF4E8' },
      },
    ];
  },

  /* ---------------- Error ---------------- */

  /** 错误类型 */
  'key_info.error_type': data => [
    {
      label: t('错误类型'),
      value: text(data['events.attributes.exception.type']),
      tone: RumCardToneEnum.DANGER,
      footer: [{ text: 'exception.type' }],
    },
  ],

  /** 来源文件：主值取文件名，副文案给出行列号 */
  'key_info.source': data => {
    const filepath = String(data['attributes.code.filepath'] ?? '');
    const fileName = filepath.split('/').pop() || filepath;
    const lineno = data['attributes.code.lineno'];
    const column = data['attributes.code.column'];
    return [
      {
        label: t('来源文件'),
        value: fileName || EMPTY_TEXT,
        footer: [{ text: `${t('行')} ${text(lineno)} · ${t('列')} ${text(column)}` }],
      },
    ];
  },

  /* ---------------- View ---------------- */

  /** 停留时长：视图停留时间，原始值以 ms 存储并自适应换算展示 */
  'view.key_info.duration': data => {
    const { text: value, suffix } = formatUnitValueParts(data['display.view.duration'], 'ms');
    return [
      {
        label: t('停留时长'),
        value: text(value),
        unit: suffix ? { text: suffix.trim() } : undefined,
      },
    ];
  },

  /** TTFB：副文案额外给出等待 / DNS / 连接 / 请求的分段耗时 */
  'view.web_vitals.ttfb': vitalCard(),

  'view.web_vitals.fcp': vitalCard(),

  'view.web_vitals.lcp': vitalCard(),

  'view.web_vitals.inp': vitalCard(),

  /** CLS 为无量纲分数，不拼单位 */
  'view.web_vitals.cls': vitalCard(),
};

/**
 * @description 通用卡片渲染：分组未登记描述符时的兜底
 * 取分组内第一个字段作为标题与主值，其余字段拼成副文案，保证后端新增分组也能展示
 */
export const genericCardDescriptor: IRumCardDescriptor = (data, ctx) => {
  const entries = Object.entries(data);
  if (!entries.length) return [];
  const [mainField, mainValue] = entries[0];
  return [
    {
      label: ctx.getFieldAlias(mainField),
      value: ctx.formatField(mainField, mainValue) || EMPTY_TEXT,
      footer: entries
        .slice(1)
        .map(([field, value]) => ({ text: `${ctx.getFieldAlias(field)}: ${ctx.formatField(field, value)}` })),
    },
  ];
};

/**
 * @description 取分组对应的卡片描述符
 * @param spanType 当前 span 类型
 * @param sectionKey 区块标识
 * @param groupKey 分组标识
 */
export function getCardDescriptor(spanType: string, sectionKey: string, groupKey: string): IRumCardDescriptor {
  return (
    CARD_DESCRIPTORS[`${spanType}.${sectionKey}.${groupKey}`] ??
    CARD_DESCRIPTORS[`${sectionKey}.${groupKey}`] ??
    CARD_DESCRIPTORS[groupKey]
  );
}

/**
 * @description 平铺字段项（section.items）转卡片：标题取字段别名，副文案固定为字段名
 * @param item 字段项
 * @param ctx 推导上下文
 */
export function itemToCard(
  item: { alias?: string; field_alias?: string; field_name: string; value: unknown },
  ctx: IRumCardResolveCtx
): IRumSummaryCardVM {
  const formatted = item.alias ?? ctx.formatField(item.field_name, item.value);
  return {
    key: item.field_name,
    label: item.field_alias || ctx.getFieldAlias(item.field_name),
    value: formatted || EMPTY_TEXT,
    footer: [{ text: item.field_name }],
  };
}

export { EMPTY_TEXT, formatCount };
