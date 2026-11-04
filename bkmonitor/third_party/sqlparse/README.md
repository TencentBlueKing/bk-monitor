# sqlparse 0.4.2+bk1

3.9.x 使用 Python 3.6。此包以 PyPI 的 sqlparse 0.4.2 为基线，保留旧版 `IN` 和 `REGEXP` 分词规则。BSD-3-Clause 许可证随 wheel 分发。

| 漏洞 | 补丁来源 |
| --- | --- |
| CVE-2023-30608 | [c457abd](https://github.com/andialbrecht/sqlparse/commit/c457abd)，将有重叠的转义分支改为互斥，保留旧版反斜线分句用例 |
| CVE-2024-4340 | [b4a39d9](https://github.com/andialbrecht/sqlparse/commit/b4a39d9) 和 [bbd8f51](https://github.com/andialbrecht/sqlparse/commit/bbd8f51)，将解析中的递归错误转换为 `SQLParseError` |
| CVE-2026-54284 | [939b129](https://github.com/andialbrecht/sqlparse/commit/939b129)，以子 token 的缓存值构造分组，避免反复展开子树 |

按 [上游分组限制](https://github.com/andialbrecht/sqlparse/commit/40ed3aa) 使用深度 100、单语句 10,000 token 的上限。单语句的 token 数在分组前检查，包含空白和注释。深度在压入下一层开始符时检查，避免先构造深层子树。

## 重建

下载 [PyPI 源码包](https://files.pythonhosted.org/packages/32/fe/8a8575debfd924c8160295686a7ea661107fc34d831429cce212b6442edb/sqlparse-0.4.2.tar.gz)，核对 SHA256 `0c00730c74263a94e5a9919ade150dfc3b19c574389985446148402998287dae`。在安装了 `setuptools==59.6.0` 和 `wheel==0.37.1` 的独立 Python 3.6 环境中执行下列命令。将 `PATCH_DIR` 设为本文件所在目录的绝对路径。

```sh
tar -xzf sqlparse-0.4.2.tar.gz
cd sqlparse-0.4.2
git apply "$PATCH_DIR/security.patch"
SOURCE_DATE_EPOCH=1631290641 python3.6 setup.py -q bdist_wheel
sha256sum dist/sqlparse-0.4.2+bk1-py3-none-any.whl
```

wheel SHA256 为 `76ff8835f8616ef7d5a1ca251b7cb03540fee4ec0575715480251c9f65197bf0`。
