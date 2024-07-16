## This is a self-documented Makefile. For usage information, run `make help`:

.DEFAULT_GOAL := help

##@ Dependencies

deps: ## Install frontend dependencies.
	@if ! command -v pnpm &> /dev/null; then \
		echo "pnpm not found, installing..."; \
		npm i -g pnpm@8; \
	else \
		echo "pnpm is already installed"; \
	fi
	pnpm i

##@ Development

dev-pc: ## Start development server for Monitor.
	npx nodemon --exec "bkmonitor-cli dev"

dev-apm: ## Start development server for Monitor APM.
	npx nodemon --exec "bkmonitor-cli dev -apm"

dev-fta: ## Start development server for Monitor FTA.
	npx nodemon --exec "bkmonitor-cli dev -f"

dev-vue3: ## Start development server for Monitor Vue3 APP.
	npx nodemon --exec "bkmonitor-cli dev -t"

dev-mobile: ## Start development server for Monitor Mobile APP.
	npx nodemon --exec "bkmonitor-cli dev -m"

dev-external: ## Start development server for Monitor External APP.
	npx nodemon --exec "bkmonitor-cli dev -external"

.PHONY: all build build-pc build-apm build-fta build-vue3 build-mobile build-external clean move help

##@ Build

all: build-pc build-apm build-fta build-vue3 build-mobile build-external
	@echo "All build tasks completed."

build: ## Build all applications in parallel.
	$(MAKE) -j 6 all

prod: build clean move ## Build for production, then clean and move files to ../static/.

build-s: build-pc build-apm build-fta build-vue3 build-mobile build-external ## Build all applications in serial.

build-pc: ## Build Monitor.
	npx bkmonitor-cli build

build-apm: ## Build Monitor APM.
	npx bkmonitor-cli build -apm

build-fta: ## Build Monitor FTA.
	npx bkmonitor-cli build -f

build-vue3: ## Build Monitor Vue3 APP.
	npx bkmonitor-cli build -t

build-mobile: ## Build Monitor Mobile APP.
	npx bkmonitor-cli build -m

build-external: ## Build Monitor External APP.
	npx bkmonitor-cli build -external

##@ Linter

check-pc: ## Biome check monitor-pc code.
	npx biome check --write ./src/monitor-pc

eslint-pc: ## Eslint check monitor-pc code.
	npx eslint --fix ./src/monitor-pc

##@ Visualization

vis-pc: ## Visualize Monitor.
	npx bkmonitor-cli build -a

vis-apm: ## Visualize Monitor APM.
	npx bkmonitor-cli build -apm -a

vis-fta: ## Visualize Monitor FTA.
	npx bkmonitor-cli build -f -a

vis-vue3: ## Visualize Monitor Vue3 APP.
	npx bkmonitor-cli build -t -a

vis-mobile: ## Visualize Monitor Mobile APP.
	npx bkmonitor-cli build -m -a

vis-external: ## Visualize Monitor External APP.
	npx bkmonitor-cli build -external -a

##@ Docker

docker-build: ## Build Docker image and extract frontend.tar.gz.
	@target=${1:-./build}; \
	rm -rf ./build; \
	docker build -t bkmonitor_web_build .; \
	docker run -d --name web-temp-container bkmonitor_web_build; \
	mkdir -p "$$target"; \
	docker cp web-temp-container:/code/frontend.tar.gz "$$target"; \
	docker rm web-temp-container

##@ Utilities

clean: ## Clean old static files.
	rm -rf ../static/monitor
	rm -rf ../static/weixin
	rm -rf ../static/fta
	rm -rf ../static/apm
	rm -rf ../static/trace
	rm -rf ../static/external

move: ## Move new build files to static directory.
	mv -f ./monitor ../static/
	mv -f ./weixin ../static/
	mv -f ./fta ../static/
	mv -f ./apm ../static/
	mv -f ./trace ../static/
	mv -f ./external ../static/

reflesh-git-hooks: ## Reflesh git hooks.
	npx simple-git-hooks

##@ Help

help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[1-9a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
