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
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// 安全风险模式
const SECURITY_PATTERNS = {
  // 注入攻击风险
  injection: {
    description: '代码注入风险',
    patterns: [
      // 检测动态正则表达式（未转义）
      {
        description: '动态正则表达式可能导致注入',
        pattern: /new RegExp\s*\(\s*[^)]*\+/,
        severity: 'warn',
      },
      // 检测动态 JSON 解析
      {
        description: '动态 JSON 解析可能导致注入',
        pattern: /JSON\.parse\s*\(\s*[^)]*\+/,
        severity: 'warn',
      },
    ],
  },

  // 敏感信息泄露
  sensitive: {
    description: '敏感信息泄露风险',
    patterns: [
      // 检测硬编码的敏感信息
      {
        description: '硬编码密码',
        pattern: /password\s*[:=]\s*['"`][^'"`]+['"`]/,
        severity: 'error',
      },
      {
        description: '硬编码 token',
        pattern: /token\s*[:=]\s*['"`][^'"`]+['"`]/,
        severity: 'error',
      },
      {
        description: '硬编码密钥',
        pattern: /secret\s*[:=]\s*['"`][^'"`]+['"`]/,
        severity: 'error',
      },
      {
        description: '硬编码 API 密钥',
        pattern: /api_key\s*[:=]\s*['"`][^'"`]+['"`]/,
        severity: 'error',
      },
      {
        description: '硬编码私钥',
        pattern: /private_key\s*[:=]\s*['"`][^'"`]+['"`]/,
        severity: 'error',
      },
    ],
  },

  // 不安全的 URL 处理
  unsafeUrl: {
    description: '不安全的 URL 处理',
    patterns: [
      // 检测 javascript: URL
      {
        description: '不安全的 javascript: URL',
        pattern: /href\s*=\s*["']javascript:/,
        severity: 'error',
      },
      // 检测直接设置 location
      {
        description: '直接设置 window.location 可能不安全',
        pattern: /window\.location\s*=/,
        severity: 'warn',
      },
      {
        description: '直接设置 location.href 可能不安全',
        pattern: /location\.href\s*=/,
        severity: 'warn',
      },
    ],
  },

  // XSS 风险 - 未过滤的 innerHTML
  xss: {
    description: 'XSS 跨站脚本攻击风险',
    patterns: [
      // 检测未过滤的 innerHTML 使用
      {
        description: '未进行 XSS 过滤的 innerHTML 使用',
        pattern: /\.innerHTML\s*=\s*[^;]+(?!.*xssFilter)/,
        severity: 'error',
      },
      // 检测未过滤的 dangerouslySetInnerHTML
      {
        description: '未进行 XSS 过滤的 dangerouslySetInnerHTML 使用',
        pattern: /dangerouslySetInnerHTML\s*=\s*\{[^}]*\}(?!.*xssFilter)/,
        severity: 'error',
      },
      // 检测直接使用 document.write
      {
        description: '不安全的 document.write 使用',
        pattern: /document\.write\s*\(/,
        severity: 'error',
      },
      // 检测 eval 使用
      {
        description: '不安全的 eval 使用',
        pattern: /eval\s*\(/,
        severity: 'error',
      },
      // 检测 new Function 使用
      {
        description: '不安全的 Function 构造函数使用',
        pattern: /new Function\s*\(/,
        severity: 'error',
      },
      // 检测动态 setTimeout/setInterval
      {
        description: '动态 setTimeout 可能导致代码注入',
        pattern: /setTimeout\s*\(\s*['"`][^'"`]*['"`]/,
        severity: 'warn',
      },
      {
        description: '动态 setInterval 可能导致代码注入',
        pattern: /setInterval\s*\(\s*['"`][^'"`]*['"`]/,
        severity: 'warn',
      },
    ],
  },
};

// 检查文件中的安全风险
function checkFileSecurity(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const issues = [];

  Object.entries(SECURITY_PATTERNS).forEach(([type, config]) => {
    config.patterns.forEach(patternConfig => {
      const { description, pattern, severity } = patternConfig;
      const lines = content.split('\n');

      lines.forEach((line, lineIndex) => {
        if (pattern.test(line)) {
          // 检查是否有 XSS 过滤
          if (
            type === 'xss' &&
            (line.includes('xssFilter') || line.includes('DOMPurify') || line.includes('sanitize'))
          ) {
            return; // 跳过已过滤的 innerHTML
          }

          issues.push({
            code: line.trim(),
            description,
            file: filePath,
            line: lineIndex + 1,
            severity,
            type,
          });
        }
      });
    });
  });

  return issues;
}

// 递归扫描目录
function scanDirectory(dir, extensions = ['.js', '.ts', '.vue', '.tsx']) {
  const files = [];

  function traverse(currentDir) {
    const items = fs.readdirSync(currentDir);

    items.forEach(item => {
      const fullPath = path.join(currentDir, item);
      const stat = fs.statSync(fullPath);

      if (stat.isDirectory() && !item.startsWith('.') && item !== 'node_modules') {
        traverse(fullPath);
      } else if (stat.isFile() && extensions.some(ext => item.endsWith(ext))) {
        files.push(fullPath);
      }
    });
  }

  traverse(dir);
  return files;
}

// 主函数
function main() {
  console.log('🔒 开始前端安全检测...\n');

  const srcDir = path.join(__dirname, '../src');
  const files = scanDirectory(srcDir);

  let totalIssues = 0;
  const allIssues = [];

  files.forEach(file => {
    const issues = checkFileSecurity(file);
    if (issues.length > 0) {
      allIssues.push(...issues);
      totalIssues += issues.length;
    }
  });

  // 输出结果
  if (totalIssues === 0) {
    console.log('✅ 未发现安全风险');
  } else {
    console.log(`⚠️  发现 ${totalIssues} 个潜在安全风险:\n`);

    // 按严重程度分组
    const errorIssues = allIssues.filter(issue => issue.severity === 'error');
    const warningIssues = allIssues.filter(issue => issue.severity === 'warn');

    if (errorIssues.length > 0) {
      console.log('🚨 严重问题 (需要立即修复):');
      errorIssues.forEach(issue => {
        console.log(`   [ERROR] ${issue.description}`);
        console.log(`       文件: ${issue.file}`);
        console.log(`       行号: ${issue.line}`);
        console.log(`       代码: ${issue.code}`);
        console.log('');
      });
    }

    if (warningIssues.length > 0) {
      console.log('⚠️  警告问题 (建议修复):');
      warningIssues.forEach(issue => {
        console.log(`   [WARN] ${issue.description}`);
        console.log(`       文件: ${issue.file}`);
        console.log(`       行号: ${issue.line}`);
        console.log(`       代码: ${issue.code}`);
        console.log('');
      });
    }
  }

  // 运行 ESLint 安全检查
  console.log('🔍 运行 ESLint 安全检查...\n');
  try {
    execSync('npm run lint', { stdio: 'inherit' });
  } catch (error) {
    console.log('ESLint 检查完成（发现一些问题）');
  }

  // 运行 Biome 检查
  console.log('\n🔍 运行 Biome 安全检查...\n');
  try {
    execSync('npm run biome:check', { stdio: 'inherit' });
  } catch (error) {
    console.log('Biome 检查完成（发现一些问题）');
  }

  console.log('\n🎉 安全检测完成！');

  // 输出建议
  if (totalIssues > 0) {
    console.log('\n💡 安全建议:');
    console.log('1. 使用 XSS 过滤函数处理 innerHTML 内容');
    console.log('2. 避免使用 javascript: URL');
    console.log('3. 对用户输入进行严格验证和转义');
    console.log('4. 使用 Content Security Policy (CSP)');
    console.log('5. 避免硬编码敏感信息');
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  SECURITY_PATTERNS,
  checkFileSecurity,
  scanDirectory,
};
