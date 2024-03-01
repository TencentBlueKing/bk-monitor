rm -rf ./build

docker build -t bkmonitor_web_build .

docker run -d --name web-temp-container bkmonitor_web_build

mkdir -p ./build

docker cp web-temp-container:/code/frontend.tar.gz ./build

docker rm web-temp-container

docker rmi bkmonitor_web_build