#!/bin/bash

CURRENT_DIR=$(pwd)

# 打包目录参数
PROJECT_DIR=$1
if [ ! -e "${PROJECT_DIR}" ]
then
    echo "DIR ${PROJECT_DIR} not exit!"
    exit 1
fi

# 版本类型参数
RELEASE_ENV=$2
case ${RELEASE_ENV} in
    ce)
      PLATFORM="community"
      ;;
    ee)
      PLATFORM="enterprise"
      ;;
    ieod)
      PLATFORM="ieod"
      ;;
    *)
        echo "RELEASE_ENV not set, check your config"
        exit 1
        ;;
esac

# 包类型参数
PACK_TYPE=$3

# 版本号参数
VERSION=$4

cd "${PROJECT_DIR}" || exit 1

# 文件位置调整
mv docs/api/monitor_v3.yaml kernel_api

# 社区版默认轻量启动
if [ "$RELEASE_ENV" = ce ]; then
  cat support-files/templates/\#etc\#supervisor-bkmonitorv3-monitor-lite.conf > support-files/templates/\#etc\#supervisor-bkmonitorv3-monitor.conf
fi

# 包配置文件渲染
if [ "$PACK_TYPE" = web ]; then
  mv version/app.yml .
  sed -i "s/\${VERSION}/${VERSION}/g" app.yml
  rm -rf support-files/pkgs support-files/templates support-files/sql
else
  mv version/project.yml .
  sed -i "s/\${VERSION}/${VERSION}/g" project.yml
  sed -i "s/\${RELEASE_ENV}/${RELEASE_ENV}/g" project.yml
  find support-files/templates -type f -exec sed -i "s/\${PLATFORM}/${PLATFORM}/g" {} \;
  mv support-files "${CURRENT_DIR}"
fi

# 抛弃特定文件
rm -rf \
..?* \
Aptfile \
bkmonitor/utils/rsa/bk.key \
version \
scripts \
tests \
docs \
./*/tests \
./*/*/tests \
webpack \
static/weixin \
static/fta \
static/monitor \
static/apm \
static/trace

# 注入版本类型
sed -i "s/BKAPP_DEPLOY_PLATFORM =.*/BKAPP_DEPLOY_PLATFORM = \"${PLATFORM}\"/g" config/tools/environment.py

# 版本号注入
echo "${VERSION}" > VERSION

# 展示结果
ls -alh .
