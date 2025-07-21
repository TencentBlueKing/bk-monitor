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
  // XSS 风险
  xss: {
    patterns: [
      /\.innerHTML\s*=/,
      /dangerouslySetInnerHTML/,
      /document\.write\s*\(/,
      /eval\s*\(/,
      /new Function\s*\(/,
      /setTimeout\s*\(\s*['"`][^'"`]*['"`]/,
      /setInterval\s*\(\s*['"`][^'"`]*['"`]/
    ],
    description: 'XSS 跨站脚本攻击风险'
  },
  
  // 注入攻击风险
  injection: {
    patterns: [
      /new RegExp\s*\(\s*[^)]*\+/,
      /\.exec\s*\(\s*[^)]*\+/,
      /\.test\s*\(\s*[^)]*\+/,
      /JSON\.parse\s*\(\s*[^)]*\+/,
      /JSON\.stringify\s*\(\s*[^)]*\+/
    ],
    description: '代码注入风险'
  },
  
  // 敏感信息泄露
  sensitive: {
    patterns: [
      /password\s*[:=]/,
      /token\s*[:=]/,
      /secret\s*[:=]/,
      /api_key\s*[:=]/,
      /private_key\s*[:=]/,
      /console\.log\s*\(/,
      /console\.warn\s*\(/,
      /console\.error\s*\(/
    ],
    description: '敏感信息泄露风险'
  },
  
  // 不安全的 URL 处理
  unsafeUrl: {
    patterns: [
      /window\.location\s*=/,
      /location\.href\s*=/,
      /location\.assign\s*\(/,
      /location\.replace\s*\(/,
      /<script\s+src\s*=/,
      /javascript:/
    ],
    description: '不安全的 URL 处理'
  }
};

// 检查文件中的安全风险
function checkFileSecurity(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const issues = [];
  
  Object.entries(SECURITY_PATTERNS).forEach(([type, config]) => {
    config.patterns.forEach((pattern, index) => {
      const matches = content.match(pattern);
      if (matches) {
        const lines = content.split('\n');
        lines.forEach((line, lineIndex) => {
          if (pattern.test(line)) {
            issues.push({
              type,
              description: config.description,
              file: filePath,
              line: lineIndex + 1,
              code: line.trim(),
              severity: 'warning'
            });
          }
        });
      }
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
    
    allIssues.forEach(issue => {
      console.log(`[${issue.severity.toUpperCase()}] ${issue.description}`);
      console.log(`   文件: ${issue.file}`);
      console.log(`   行号: ${issue.line}`);
      console.log(`   代码: ${issue.code}`);
      console.log('');
    });
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
}

if (require.main === module) {
  main();
}

module.exports = {
  checkFileSecurity,
  scanDirectory,
  SECURITY_PATTERNS
}; 