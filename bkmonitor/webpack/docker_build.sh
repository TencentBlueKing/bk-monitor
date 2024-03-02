#!/bin/bash -e

# 默认为./build
target=${1:-./build}

rm -rf ./build

docker build -t bkmonitor_web_build .

docker run -d --name web-temp-container bkmonitor_web_build

mkdir -p "$target"

docker cp web-temp-container:/code/frontend.tar.gz "$target"

docker rm web-temp-container

