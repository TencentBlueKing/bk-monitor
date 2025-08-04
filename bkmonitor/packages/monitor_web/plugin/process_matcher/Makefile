.SILENT:

.PHONY: build
build:
	go build -ldflags="-s -w" -o bin/process_matcher main.go

.PHONY: build-dev
build-dev:
	go build -o bin/process_matcher main.go

.PHONY: test
test:
	go test -v
