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
 * PromQL 语法特征枚举
 */
enum PromQLFeature {
  AGGREGATIONS = 'aggregations',
  FUNCTIONS = 'functions',
  KEYWORDS = 'keywords',
  LABEL_SELECTOR = 'label_selector',
  METRIC_NAME = 'metric_name',
  OPERATORS = 'operators',
  TIME_RANGE = 'time_range',
}

/**
 * PromQL 检测结果接口
 */
interface IPromQLDetectionResult {
  /** 置信度评分 (0-100) */
  confidence: number;
  /** 匹配的特征 */
  features: string[];
  /** 是否为 PromQL */
  isPromQL: boolean;
  /** 检测到的关键字 */
  keywords: string[];
}

/**
 * PromQL 检测配置接口
 */
interface IPromQLDetectorConfig {
  /** 自定义关键字 */
  customKeywords?: string[];
  /** 最小置信度阈值 */
  minConfidence?: number;
  /** 是否启用严格模式 */
  strictMode?: boolean;
}

/**
 * PromQL 检测器类
 */
class PromQLDetector {
  private readonly aggregations: string[] = [
    'sum',
    'min',
    'max',
    'avg',
    'group',
    'stddev',
    'stdvar',
    'count',
    'count_values',
    'bottomk',
    'topk',
    'quantile',
  ];

  private readonly allKeywords: string[];

  private readonly config: Required<IPromQLDetectorConfig>;

  private readonly functions: string[] = [
    'abs',
    'absent',
    'absent_over_time',
    'acos',
    'acosh',
    'asin',
    'asinh',
    'atan',
    'atanh',
    'avg_over_time',
    'ceil',
    'changes',
    'clamp',
    'clamp_max',
    'clamp_min',
    'cos',
    'cosh',
    'count_over_time',
    'days_in_month',
    'day_of_month',
    'day_of_week',
    'deg',
    'delta',
    'deriv',
    'exp',
    'floor',
    'histogram_quantile',
    'holt_winters',
    'hour',
    'idelta',
    'increase',
    'irate',
    'label_replace',
    'label_join',
    'last_over_time',
    'ln',
    'log10',
    'log2',
    'max_over_time',
    'min_over_time',
    'minute',
    'month',
    'pi',
    'predict_linear',
    'present_over_time',
    'quantile_over_time',
    'rad',
    'rate',
    'resets',
    'round',
    'scalar',
    'sgn',
    'sin',
    'sinh',
    'sort',
    'sort_desc',
    'sqrt',
    'stddev_over_time',
    'stdvar_over_time',
    'sum_over_time',
    'tan',
    'tanh',
    'time',
    'timestamp',
    'vector',
    'year',
  ];

  private readonly offsetModifier: string[] = ['offset'];

  private readonly operators: string[] = [
    '==',
    '!=',
    '=~',
    '!~',
    '<=',
    '>=',
    '<',
    '>',
    '+',
    '-',
    '*',
    '/',
    '%',
    '^',
    'and',
    'or',
    'unless',
  ];
  private readonly vectorMatching: string[] = ['on', 'ignoring', 'group_right', 'group_left', 'by', 'without'];

  /**
   * 严格模式下的置信度调整
   */
  private applyStrictModeAdjustments(text: string, confidence: number): number {
    let adjustedConfidence = confidence;

    // 如果包含明显非 PromQL 的 SQL 关键字，降低置信度
    const sqlKeywords = ['SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP'];
    const sqlPattern = new RegExp(`\\b(${sqlKeywords.join('|')})\\b`, 'i');
    if (sqlPattern.test(text)) {
      adjustedConfidence -= 50;
    }

    // 如果包含明显的编程语言语法，降低置信度
    const codePatterns = [
      /function\s+\w+\s*\(/, // JavaScript 函数
      /def\s+\w+\s*\(/, // Python 函数
      /class\s+\w+/, // 类定义
      /import\s+\w+/, // 导入语句
      /console\.log/, // 控制台输出
      /print\s*\(/, // 打印语句
    ];

    for (const pattern of codePatterns) {
      if (pattern.test(text)) {
        adjustedConfidence -= 30;
        break;
      }
    }

    return Math.max(adjustedConfidence, 0);
  }

  /**
   * 获取检测到的关键字
   */
  private getDetectedKeywords(text: string): string[] {
    const keywords: string[] = [];
    const keywordPattern = new RegExp(`\\b(${this.allKeywords.join('|')})\\b`, 'gi');
    let match: null | RegExpExecArray;

    match = keywordPattern.exec(text);
    while (match !== null) {
      keywords.push(match[1].toLowerCase());
      match = keywordPattern.exec(text);
    }

    return [...new Set(keywords)];
  }

  /**
   * 检查是否包含聚合操作
   */
  private hasAggregation(text: string): boolean {
    const aggregationPattern = new RegExp(`\\b(${this.aggregations.join('|')})\\s*\\(`, 'i');
    return aggregationPattern.test(text);
  }

  /**
   * 检查是否包含函数调用
   */
  private hasFunctionCall(text: string): boolean {
    const functionPattern = new RegExp(`\\b(${this.functions.join('|')})\\s*\\(`, 'i');
    return functionPattern.test(text);
  }

  /**
   * 检查是否包含标签选择器
   */
  private hasLabelSelector(text: string): boolean {
    // 匹配 {key="value"} 或 {key=~"regex"} 等格式
    return /\{[^}]*[=!~]+[^}]*\}/.test(text);
  }

  /**
   * 检查是否包含指标名称模式
   */
  private hasMetricName(text: string): boolean {
    // PromQL 指标名称规则：字母、数字、下划线、冒号，必须以字母、下划线或冒号开头
    return /\b[a-zA-Z_:][a-zA-Z0-9_:]*\b/.test(text);
  }

  /**
   * 检查是否包含运算符
   */
  private hasOperators(text: string): boolean {
    const operatorPattern = new RegExp(this.operators.map(op => op.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'));
    return operatorPattern.test(text);
  }

  /**
   * 检查是否包含时间范围选择器
   */
  private hasTimeRange(text: string): boolean {
    // 匹配 [5m], [1h], [30s] 等格式
    return /\[[0-9]+[smhdwy]\]/.test(text);
  }

  /**
   * 检查文本是否全部是中文字符
   */
  private isAllChinese(text: string): boolean {
    // 匹配只包含中文字符、空格和标点符号的文本
    return /^[\u4e00-\u9fff\s\u3000-\u303f\uff00-\uffef]*$/.test(text) && /[\u4e00-\u9fff]/.test(text);
  }

  /**
   * 检查文本是否全部是数字
   */
  private isAllNumbers(text: string): boolean {
    // 匹配只包含数字、小数点、空格的文本
    return /^[\d\s.]*$/.test(text) && /\d/.test(text);
  }

  constructor(config: IPromQLDetectorConfig = {}) {
    this.config = {
      minConfidence: config.minConfidence ?? 30,
      strictMode: config.strictMode ?? false,
      customKeywords: config.customKeywords ?? [],
    };

    this.allKeywords = [
      ...this.aggregations,
      ...this.functions,
      ...this.vectorMatching,
      ...this.offsetModifier,
      ...this.config.customKeywords,
    ];
  }

  /**
   * 完整检测 PromQL
   */
  public detect(text: string): IPromQLDetectionResult {
    const trimmedText = text.trim();

    if (!trimmedText) {
      return {
        isPromQL: false,
        confidence: 0,
        features: [],
        keywords: [],
      };
    }

    // 前置判断：如果文本全部是中文或全部是数字，则判断为 false
    if (this.isAllChinese(trimmedText) || this.isAllNumbers(trimmedText)) {
      return {
        isPromQL: false,
        confidence: 0,
        features: [],
        keywords: [],
      };
    }

    const features: string[] = [];
    const keywords: string[] = [];
    let confidence = 0;

    // 检测指标名称模式
    if (this.hasMetricName(trimmedText)) {
      features.push(PromQLFeature.METRIC_NAME);
      confidence += 20;
    }

    // 检测关键字
    const detectedKeywords = this.getDetectedKeywords(trimmedText);
    if (detectedKeywords.length > 0) {
      features.push(PromQLFeature.KEYWORDS);
      keywords.push(...detectedKeywords);
      confidence += Math.min(detectedKeywords.length * 10, 30);
    }

    // 检测时间范围
    if (this.hasTimeRange(trimmedText)) {
      features.push(PromQLFeature.TIME_RANGE);
      confidence += 25;
    }

    // 检测标签选择器
    if (this.hasLabelSelector(trimmedText)) {
      features.push(PromQLFeature.LABEL_SELECTOR);
      confidence += 15;
    }

    // 检测运算符
    if (this.hasOperators(trimmedText)) {
      features.push(PromQLFeature.OPERATORS);
      confidence += 10;
    }

    // 检测函数调用
    if (this.hasFunctionCall(trimmedText)) {
      features.push(PromQLFeature.FUNCTIONS);
      confidence += 20;
    }

    // 检测聚合操作
    if (this.hasAggregation(trimmedText)) {
      features.push(PromQLFeature.AGGREGATIONS);
      confidence += 15;
    }

    // 严格模式下的额外检查
    if (this.config.strictMode) {
      confidence = this.applyStrictModeAdjustments(trimmedText, confidence);
    }

    const finalConfidence = Math.min(confidence, 100);

    return {
      isPromQL: finalConfidence >= this.config.minConfidence,
      confidence: finalConfidence,
      features,
      keywords: [...new Set(keywords)],
    };
  }

  /**
   * 获取所有支持的关键字
   */
  public getAllKeywords(): string[] {
    return [...this.allKeywords];
  }

  /**
   * 获取配置信息
   */
  public getConfig(): Required<IPromQLDetectorConfig> {
    return { ...this.config };
  }

  /**
   * 检测文本是否为 PromQL
   */
  public isPromQL(text: string): boolean {
    const result = this.detect(text);
    return result.confidence >= this.config.minConfidence;
  }
}

/**
 * 详细的 PromQL 检测函数
 */
export function detectPromQL(text: string, config?: IPromQLDetectorConfig): IPromQLDetectionResult {
  const detector = new PromQLDetector(config);
  return detector.detect(text);
}

/**
 * 基础 PromQL 正则表达式检测（快速版本）
 */
export function isBasicPromQL(text: string): boolean {
  const trimmedText = text.trim();
  if (!trimmedText) return false;

  // 前置判断：如果文本全部是中文或全部是数字，则判断为 false
  if (isAllChinese(trimmedText) || isAllNumbers(trimmedText)) {
    return false;
  }

  // 基础 PromQL 模式
  const basicPatterns = [
    // 指标名称（可带标签和时间范围）
    /^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[^}]*\})?(\[[0-9]+[smhdwy]\])?$/,

    // 包含时间范围的查询
    /\[[0-9]+[smhdwy]\]/,

    // 包含标签选择器的查询
    /\{[^}]*[=!~]+[^}]*\}/,

    // 包含 PromQL 运算符
    /(==|!=|=~|!~|<=|>=|<|>|\+|-|\*|\/|%|\^)/,

    // 包含常见 PromQL 函数
    /\b(rate|sum|avg|max|min|count|increase|delta)\s*\(/i,
  ];

  return basicPatterns.some(pattern => pattern.test(trimmedText));
}

/**
 * 简单的 PromQL 检测函数
 */
export function isPromQL(text: string, minConfidence = 40): boolean {
  const detector = new PromQLDetector({ minConfidence });
  return detector.isPromQL(text);
}

/**
 * 检查文本是否全部是中文字符
 */
function isAllChinese(text: string): boolean {
  // 匹配只包含中文字符、空格和标点符号的文本
  return /^[\u4e00-\u9fff\s\u3000-\u303f\uff00-\uffef]*$/.test(text) && /[\u4e00-\u9fff]/.test(text);
}

/**
 * 检查文本是否全部是数字
 */
function isAllNumbers(text: string): boolean {
  // 匹配只包含数字、小数点、空格的文本
  return /^[\d\s.]*$/.test(text) && /\d/.test(text);
}

export default PromQLDetector;
export type { IPromQLDetectionResult, IPromQLDetectorConfig };
export { PromQLFeature };
