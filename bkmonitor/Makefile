MAKE_FILE_DIR = $(shell pwd)/$(lastword $(MAKEFILE_LIST))
PROJECT_DIR = $(shell dirname $(MAKE_FILE_DIR))
WEBPACK_DIR = $(PROJECT_DIR)/webpack

# 版本类型
PLATFORM = ce
ROLE = web
VERSION = 1.0.0
TARGET_DIR = xxxxxx

.PHONY: clean
clean:
	find ${PROJECT_DIR} -name "*.pyc" -delete

.PHONY: npm-install
npm-install:
	cd ${WEBPACK_DIR}  && npm i

.PHONY: webpack-build
webpack-build:
	cd ${WEBPACK_DIR} && pnpm i && npm run build

.PHONY: webpack-package
webpack-package:
	cd ${WEBPACK_DIR} && mkdir -p ../build && tar -czvf ../build/frontend.tar.gz monitor fta weixin apm trace external

.PHONY: webpack-copy
webpack-copy:
	cd static && rm -rf monitor fta weixin apm trace external && cd ${WEBPACK_DIR} && cp -R monitor fta weixin apm trace external ../static

.PHONY: build-clean
build-clean:
	sh version/pack.sh ${TARGET_DIR} ${PLATFORM} ${ROLE} ${VERSION}


build-test-image:
	cp scripts/unittest/.dockerignore .dockerignore && docker build -f scripts/unittest/Dockerfile -t mirrors.tencent.com/bkmonitorv3/bkmonitor-test:latest .
