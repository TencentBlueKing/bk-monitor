/*
  ("feat", "A new feature. Correlates with MINOR in SemVer"),
  ("fix", "A bug fix. Correlates with PATCH in SemVer"),
  ("docs", "Documentation only changes"),
  ("style", "Changes that do not affect the meaning of the code"),
  ("refactor", "A code change that neither fixes a bug nor adds a feature"),
  ("perf", "A code change that improves performance"),
  ("test", "Adding missing or correcting existing tests"),
  ("chore", "Changes to the build process or auxiliary tools and libraries such as documentation generation"),

# 即将启用的prefix，仍保留一段时间
  ("feature", "新特性"),
  ("bugfix", "线上功能bug"),
  ("minor", "不重要的修改（换行，拼写错误等）"),
  ("optimization", "功能优化"),
  ("sprintfix", "未上线代码修改 （功能模块未上线部分bug）"),
  ("merge", "分支合并及冲突解决"),
*/
const colors = require('picocolors');
const { readFileSync } = require('fs');
const msgPath = process.argv[2];
const msg = readFileSync(msgPath, 'utf-8').trim();
const oldCommitRE = /^(revert: )?(feature|bugfix|minor|optimization|sprintfix|merge)(\(.+\))?: .{1,50}/;
const newCommitRE = /^(revert: )?(feat|fix|docs|style|refactor|perf|test|chore)(\(.+\))?: .{1,50}/;
if (!(oldCommitRE.test(msg) || newCommitRE.test(msg)) && !msg.includes('Merge branch')) {
  console.log(msg);
  console.log('\n');
  console.error(`  ${colors.bgRed(colors.white(' ERROR '))} ${colors.red('invalid commit message format.')}\n\n${colors.red('  Proper commit message format is required for automated changelog generation. Examples:\n\n')}    ${colors.green('feature: add \'comments\' option')}\n`
      + `    ${colors.green('bugfix: handle events on blur (close #28)')}\n}`);
  process.exit(1);
}
