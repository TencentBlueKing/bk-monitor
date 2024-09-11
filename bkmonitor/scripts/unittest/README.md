# 单元测试镜像

## 快速开始

> ⚠️ 不支持 MacOS

### Docker build

```shell
make build-test-image
```

### Docker run

```shell
docker run -it mirrors.tencent.com/bkmonitorv3/bkmonitor-test:latest bash
```

### Install dependencies

```shell
pip install --no-cache-dir -r requirements_test.txt
```

## Migrate

```shell
mysql -e 'CREATE DATABASE `bk_monitor_saas` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;'
mysql -e 'CREATE DATABASE `bk_monitor_api` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;'

env DJANGO_CONF_MODULE="" BKAPP_DEPLOY_ENV="web" python manage.py migrate || true
env DJANGO_CONF_MODULE="" BKAPP_DEPLOY_ENV="web" python manage.py migrate || true
```

## Test

```shell
pytest alarm_backends/tests 2>&1 | tee pytest.log || true
python manage.py test alarm_backends.tests 2>&1 | tee testcase.log || true


# 解析单测结果
python scripts/unittest/parse_test_output.py "$(pwd)/pytest.log"
python scripts/unittest/parse_test_output.py "$(pwd)/testcase.log"
```

## Coverage

```shell
# 仅统计告警后台覆盖度
COVERAGE_SOURCE="alarm_backends,bkmonitor/data_source"
# 忽略部分无关文件
COVERAGE_OMIT_PATH="*/test/*,*/virtualenv/*,*/venv/*,*/migrations/*,*/mock_data/*,*/tests/*"
# -p 表示覆盖率统计文件追加机器名称，进程pid和随机数，用于区分不同模块之间生成的 .coverage 文件
coverage run --parallel-mode --source="$COVERAGE_SOURCE" --omit="$COVERAGE_OMIT_PATH" -m pytest alarm_backends/tests bkmonitor/data_source/tests 2>&1 | tee pytest.log || true
coverage run --parallel-mode --source="$COVERAGE_SOURCE" --omit="$COVERAGE_OMIT_PATH" ./manage.py test alarm_backends.tests bkmonitor.data_source.tests 2>&1 | tee testcase.log || true

# 合并多个覆盖度统计结果
coverage combine

# 输出单测覆盖率结果
# --sort=cover 按覆盖度升序
coverage report --sort=cover | tee coverage.log

# 解析覆盖度结果
# > 61% (7294 / 18881)
python scripts/unittest/parse_test_output.py "$(pwd)/coverage.log"

# 可选：保存 html 报告到 htmlcov/index.html
coverage html
```
