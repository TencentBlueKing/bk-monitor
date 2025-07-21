#!/usr/bin/env node

/**
 * 前端安全检测脚本
 * 检测常见的安全漏洞和风险代码
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// 安全风险模式
const SECURITY_PATTERNS = {
  // XSS 风险 - 未过滤的 innerHTML
  xss: {
    patterns: [
      // 检测未过滤的 innerHTML 使用
      {
        pattern: /\.innerHTML\s*=\s*[^;]+(?!.*xssFilter)/,
        description: '未进行 XSS 过滤的 innerHTML 使用',
        severity: 'error'
      },
      // 检测未过滤的 dangerouslySetInnerHTML
      {
        pattern: /dangerouslySetInnerHTML\s*=\s*\{[^}]*\}(?!.*xssFilter)/,
        description: '未进行 XSS 过滤的 dangerouslySetInnerHTML 使用',
        severity: 'error'
      },
      // 检测直接使用 document.write
      {
        pattern: /document\.write\s*\(/,
        description: '不安全的 document.write 使用',
        severity: 'error'
      },
      // 检测 eval 使用
      {
        pattern: /eval\s*\(/,
        description: '不安全的 eval 使用',
        severity: 'error'
      },
      // 检测 new Function 使用
      {
        pattern: /new Function\s*\(/,
        description: '不安全的 Function 构造函数使用',
        severity: 'error'
      },
      // 检测动态 setTimeout/setInterval
      {
        pattern: /setTimeout\s*\(\s*['"`][^'"`]*['"`]/,
        description: '动态 setTimeout 可能导致代码注入',
        severity: 'warn'
      },
      {
        pattern: /setInterval\s*\(\s*['"`][^'"`]*['"`]/,
        description: '动态 setInterval 可能导致代码注入',
        severity: 'warn'
      }
    ],
    description: 'XSS 跨站脚本攻击风险'
  },
  
  // 注入攻击风险
  injection: {
    patterns: [
      // 检测动态正则表达式（未转义）
      {
        pattern: /new RegExp\s*\(\s*[^)]*\+/,
        description: '动态正则表达式可能导致注入',
        severity: 'warn'
      },
      // 检测动态 JSON 解析
      {
        pattern: /JSON\.parse\s*\(\s*[^)]*\+/,
        description: '动态 JSON 解析可能导致注入',
        severity: 'warn'
      }
    ],
    description: '代码注入风险'
  },
  
  // 敏感信息泄露
  sensitive: {
    patterns: [
      // 检测硬编码的敏感信息
      {
        pattern: /password\s*[:=]\s*['"`][^'"`]+['"`]/,
        description: '硬编码密码',
        severity: 'error'
      },
      {
        pattern: /token\s*[:=]\s*['"`][^'"`]+['"`]/,
        description: '硬编码 token',
        severity: 'error'
      },
      {
        pattern: /secret\s*[:=]\s*['"`][^'"`]+['"`]/,
        description: '硬编码密钥',
        severity: 'error'
      },
      {
        pattern: /api_key\s*[:=]\s*['"`][^'"`]+['"`]/,
        description: '硬编码 API 密钥',
        severity: 'error'
      },
      {
        pattern: /private_key\s*[:=]\s*['"`][^'"`]+['"`]/,
        description: '硬编码私钥',
        severity: 'error'
      },
      // 检测生产环境的 console 语句
      {
        pattern: /console\.(log|warn|error|info)\s*\(/,
        description: '生产环境应避免使用 console 语句',
        severity: 'warn'
      }
    ],
    description: '敏感信息泄露风险'
  },
  
  // 不安全的 URL 处理
  unsafeUrl: {
    patterns: [
      // 检测 javascript: URL
      {
        pattern: /href\s*=\s*["']javascript:/,
        description: '不安全的 javascript: URL',
        severity: 'error'
      },
      // 检测直接设置 location
      {
        pattern: /window\.location\s*=/,
        description: '直接设置 window.location 可能不安全',
        severity: 'warn'
      },
      {
        pattern: /location\.href\s*=/,
        description: '直接设置 location.href 可能不安全',
        severity: 'warn'
      }
    ],
    description: '不安全的 URL 处理'
  }
};

// 检查文件中的安全风险
function checkFileSecurity(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const issues = [];
  
  Object.entries(SECURITY_PATTERNS).forEach(([type, config]) => {
    config.patterns.forEach((patternConfig) => {
      const { pattern, description, severity } = patternConfig;
      const lines = content.split('\n');
      
      lines.forEach((line, lineIndex) => {
        if (pattern.test(line)) {
          // 检查是否有 XSS 过滤
          if (type === 'xss' && (line.includes('xssFilter') || line.includes('DOMPurify') || line.includes('sanitize'))) {
            return; // 跳过已过滤的 innerHTML
          }
          
          issues.push({
            type,
            description,
            file: filePath,
            line: lineIndex + 1,
            code: line.trim(),
            severity
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
    console.log('2. 移除生产环境中的 console 语句');
    console.log('3. 避免使用 javascript: URL');
    console.log('4. 对用户输入进行严格验证和转义');
    console.log('5. 使用 Content Security Policy (CSP)');
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  checkFileSecurity,
  scanDirectory,
  SECURITY_PATTERNS
}; 