rm -rf ./apm/ ./monitor/ ./fta/ ./external ./trace/ ./weixin/

docker build -t bkmonitor_web_build .

docker run create --name web-temp-container bkmonitor_web_build

docker cp web-temp-container:/code/apm .
docker cp web-temp-container:/code/monitor .
docker cp web-temp-container:/code/fta .
docker cp web-temp-container:/code/external .
docker cp web-temp-container:/code/trace .
docker cp web-temp-container:/code/weixin .

docker rm web-temp-container

docker rmi bkmonitor_web_build