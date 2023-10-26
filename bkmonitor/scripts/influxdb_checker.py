import requests
import json

url = "http://bk-monitor-influxdb:8086/query"

# 数据库磁盘使用量
r = requests.get(
    f"{url}?db=_internal",
    params={
        "q": 'select sum(diskBytes) / 1024 / 1024 /1024 from _internal."monitor"."shard" where time > now() - 10s group by "database"'
    },
)
data = r.json()
disk_usages = {}
for record in data["results"][0]["series"]:
    disk_usages[record["tags"]["database"]] = record["values"][0][1]

# 查询数据库series数量
r = requests.get(
    f"{url}?db=_internal", params={"q": 'select *::tag, numSeries from "database" where time > now() - 5m;'}
)
data = r.json()
series_numbers = {}
for record in data["results"][0]["series"][0]["values"]:
    series_numbers[record[1]] = record[3]

# 查询所有数据库
r = requests.get(url, params={"q": "show databases"})
data = r.json()
database_names = [record[0] for record in data["results"][0]["series"][0]["values"] if record[0] != "_internal"]

databases = {}
for database in database_names:
    print(f"processing database {database}")

    r = requests.get(f"{url}?db={database}", params={"q": "SHOW RETENTION POLICIES"})
    data = r.json()
    policy = data["results"][0]["series"][0]["values"][0]

    r = requests.get(f"{url}?db={database}", params={"q": "SHOW measurements"})
    data = r.json()

    measurements = {}
    if "series" in data["results"][0]:
        measurement_names = [record[0] for record in data["results"][0]["series"][0]["values"]]
        for measurement in measurement_names:
            r = requests.get(f"{url}?db={database}", params={"q": f"show series cardinality from {measurement}"})
            data = r.json()
            if "series" not in data["results"][0]:
                series_number = None
            else:
                series_number = data["results"][0]["series"][0]["values"][0][0]

            r = requests.get(f"{url}?db={database}", params={"q": f"select count(*) from {measurement}"})
            data = r.json()
            if "series" not in data["results"][0]:
                metrics_number = None
                points_number = None
            else:
                metrics = [d for d in data["results"][0]["series"][0]["values"][0] if isinstance(d, int)]
                metrics_number = len(metrics)
                points_number = max(metrics)

            measurements[measurement] = {
                "metrics_number": metrics_number,
                "points_number": points_number,
                "series_number": series_number,
            }
    databases[database] = {
        "policy": policy,
        "measurements": measurements,
        "series_number": series_numbers.get(database),
        "disk_usage": disk_usages.get(database),
    }

with open("influxdb_info.json", "w+") as f:
    f.write(json.dumps(databases))
