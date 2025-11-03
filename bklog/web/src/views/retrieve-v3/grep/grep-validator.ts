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
 * Grep 语法验证器
 * 根据 EBNF 语法定义验证 grep 命令的正确性
 */

export interface ValidationError {
  message: string;
  position: number;
  length: number;
  type: 'error' | 'warning';
}

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
}

export class GrepValidator {
  private readonly supportedArgs = ['i', 'v', 'E', 'e', 'w', 'x', 'c', 'n', 'H', 'h'];

  /**
   * 验证 grep 命令语法
   */
  validate(input: string): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationError[] = [];

    if (!input.trim()) {
      return { isValid: true, errors, warnings };
    }

    // 分析管道命令
    const pipeCommands = this.splitPipeCommands(input);

    for (let i = 0; i < pipeCommands.length; i++) {
      const command = pipeCommands[i];
      const commandErrors = this.validateSingleCommand(command, this.getCommandPosition(input, i));
      errors.push(...commandErrors.filter(e => e.type === 'error'));
      warnings.push(...commandErrors.filter(e => e.type === 'warning'));
    }

    // 检查逻辑组合合理性
    const logicWarnings = this.validateLogicCombination(pipeCommands);
    warnings.push(...logicWarnings);

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
    };
  }

  /**
   * 分割管道命令
   */
  private splitPipeCommands(input: string): string[] {
    const commands: string[] = [];
    let current = '';
    let inQuotes = false;
    let quoteChar = '';
    let escaped = false;

    for (const char of input) {
      if (escaped === true) {
        current += char;
        escaped = false;
        continue;
      }

      if (char === '\\') {
        current += char;
        escaped = true;
        continue;
      }

      if (!inQuotes && (char === '"' || char === "'")) {
        inQuotes = true;
        quoteChar = char;
        current += char;
        continue;
      }

      if (inQuotes === true && char === quoteChar) {
        inQuotes = false;
        quoteChar = '';
        current += char;
        continue;
      }

      if (!inQuotes && char === '|') {
        commands.push(current.trim());
        current = '';
        continue;
      }

      current += char;
    }

    if (current.trim()) {
      commands.push(current.trim());
    }

    return commands;
  }

  /**
   * 验证单个命令
   */
  private validateSingleCommand(command: string, basePosition: number): ValidationError[] {
    const errors: ValidationError[] = [];
    const tokens = this.tokenizeCommand(command);

    let _hasCommand = false;
    let hasPattern = false;

    for (const token of tokens) {
      const position = basePosition + token.position;

      switch (token.type) {
        case 'command':
          _hasCommand = true;
          break;

        case 'argument': {
          const argErrors = this.validateArgument(token.value, position);
          errors.push(...argErrors);
          break;
        }

        case 'string': {
          hasPattern = true;
          const stringErrors = this.validateString(token.value, position);
          errors.push(...stringErrors);
          break;
        }

        case 'pattern':
          hasPattern = true;
          break;

        case 'unknown':
          errors.push({
            message: `未识别的标记: "${token.value}"`,
            position,
            length: token.value.length,
            type: 'error',
          });
          break;
        default:
          break;
      }
    }

    // 检查是否有搜索模式
    if (!hasPattern && command.trim()) {
      errors.push({
        message: '缺少搜索模式',
        position: basePosition,
        length: command.length,
        type: 'error',
      });
    }

    return errors;
  }

  /**
   * 验证参数
   */
  private validateArgument(arg: string, position: number): ValidationError[] {
    const errors: ValidationError[] = [];

    if (!arg.startsWith('-')) {
      errors.push({
        message: '参数必须以 "-" 开头',
        position,
        length: arg.length,
        type: 'error',
      });
      return errors;
    }

    const argName = arg.substring(1);
    if (!argName) {
      errors.push({
        message: '参数名不能为空',
        position,
        length: arg.length,
        type: 'error',
      });
      return errors;
    }

    // 检查每个参数字符
    for (let i = 0; i < argName.length; i++) {
      const char = argName[i];
      if (!this.supportedArgs.includes(char)) {
        errors.push({
          message: `不支持的参数: "-${char}"`,
          position: position + 1 + i,
          length: 1,
          type: 'warning',
        });
      }
    }

    return errors;
  }

  /**
   * 验证字符串
   */
  private validateString(str: string, position: number): ValidationError[] {
    const errors: ValidationError[] = [];

    if (str.length < 2) {
      errors.push({
        message: '字符串格式错误',
        position,
        length: str.length,
        type: 'error',
      });
      return errors;
    }

    const quote = str[0];
    if (quote !== '"' && quote !== "'") {
      return errors; // 不是引号字符串
    }

    if (str.at(-1) !== quote) {
      errors.push({
        message: `未闭合的${quote === '"' ? '双' : '单'}引号`,
        position,
        length: str.length,
        type: 'error',
      });
      return errors;
    }

    // 检查转义字符
    for (let i = 1; i < str.length - 1; i++) {
      if (str[i] === '\\' && i + 1 < str.length - 1) {
        const nextChar = str[i + 1];
        if (!(['"', "'", '\\', 'n', 't', 'r'].includes(nextChar) || nextChar.match(/x[0-9a-fA-F]/))) {
          errors.push({
            message: `无效的转义字符: "\\${nextChar}"`,
            position: position + i,
            length: 2,
            type: 'warning',
          });
        }
      }
    }

    return errors;
  }

  /**
   * 验证逻辑组合合理性
   */
  private validateLogicCombination(commands: string[]): ValidationError[] {
    const warnings: ValidationError[] = [];

    // 检查最后一个命令是否为 -v，如果是则提醒不会高亮
    if (commands.length > 0) {
      const lastCommand = commands.at(-1);
      if (lastCommand?.includes('-v')) {
        warnings.push({
          message: '最后一个命令包含 -v 参数，结果将不会高亮',
          position: 0,
          length: 0,
          type: 'warning',
        });
      }
    }

    // 检查重复的 -i 参数
    let hasIgnoreCase = false;
    for (const command of commands) {
      if (command.includes('-i')) {
        if (hasIgnoreCase === true) {
          warnings.push({
            message: '检测到重复的 -i 参数',
            position: 0,
            length: 0,
            type: 'warning',
          });
          break;
        }
        hasIgnoreCase = true;
      }
    }

    return warnings;
  }

  /**
   * 命令分词
   */
  private tokenizeCommand(command: string): Array<{
    type: string;
    value: string;
    position: number;
  }> {
    const tokens: Array<{ type: string; value: string; position: number }> = [];
    let pos = 0;
    const len = command.length;

    while (pos < len) {
      // 跳过空白
      if (/\s/.test(command[pos])) {
        pos++;
        continue;
      }

      // grep/egrep 命令
      const grepMatch = command.substr(pos).match(/^(grep|egrep)(?=\s|$)/);
      if (grepMatch) {
        tokens.push({
          type: 'command',
          value: grepMatch[0],
          position: pos,
        });
        pos += grepMatch[0].length;
        continue;
      }

      // 参数
      const argMatch = command.substr(pos).match(/^-[a-zA-Z0-9]+/);
      if (argMatch) {
        tokens.push({
          type: 'argument',
          value: argMatch[0],
          position: pos,
        });
        pos += argMatch[0].length;
        continue;
      }

      // 引号字符串
      if (command[pos] === '"' || command[pos] === "'") {
        const quote = command[pos];
        let end = pos + 1;
        while (end < len && command[end] !== quote) {
          if (command[end] === '\\' && end + 1 < len) {
            end += 2;
          } else {
            end++;
          }
        }
        if (end < len) {
          end++;
        } // 包含结束引号

        tokens.push({
          type: 'string',
          value: command.substring(pos, end),
          position: pos,
        });
        pos = end;
        continue;
      }

      // 未加引号的模式
      const patternMatch = command.substr(pos).match(/^[^\s]+/);
      if (patternMatch) {
        tokens.push({
          type: 'pattern',
          value: patternMatch[0],
          position: pos,
        });
        pos += patternMatch[0].length;
        continue;
      }

      // 未知标记
      tokens.push({
        type: 'unknown',
        value: command[pos],
        position: pos,
      });
      pos++;
    }

    return tokens;
  }

  /**
   * 获取命令在原始输入中的位置
   */
  private getCommandPosition(input: string, commandIndex: number): number {
    let position = 0;
    let currentIndex = 0;
    let inQuotes = false;
    let quoteChar = '';
    let escaped = false;

    for (let i = 0; i < input.length; i++) {
      const char = input[i];

      if (escaped === true) {
        escaped = false;
        continue;
      }

      if (char === '\\') {
        escaped = true;
        continue;
      }

      if (!inQuotes && (char === '"' || char === "'")) {
        inQuotes = true;
        quoteChar = char;
        continue;
      }

      if (inQuotes === true && char === quoteChar) {
        inQuotes = false;
        quoteChar = '';
        continue;
      }

      if (!inQuotes && char === '|') {
        if (currentIndex === commandIndex) {
          return position;
        }
        currentIndex++;
        position = i + 1;
        // 跳过空白
        while (position < input.length && /\s/.test(input[position])) {
          position++;
        }
        i = position - 1; // 因为循环会 i++
      }
    }

    return position;
  }
}

// 导出默认实例
export const grepValidator = new GrepValidator();
