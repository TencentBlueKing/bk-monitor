#!/bin/bash

anynowtime="date +'%Y-%m-%d %H:%M:%S'"
NOW="echo [\`$anynowtime\`][PID:$$]"

##### 可在脚本开始运行时调用，打印当时的时间戳及PID。
function job_start
{
    echo "`eval $NOW` job_start"
}

##### 可在脚本执行成功的逻辑分支处调用，打印当时的时间戳及PID。
function job_success
{
    MSG="$*"
    echo "`eval $NOW` job_success:[$MSG]"
    exit 0
}

##### 可在脚本执行失败的逻辑分支处调用，打印当时的时间戳及PID。
function job_fail
{
    MSG="$*"
    echo "`eval $NOW` job_fail:[$MSG]"
    exit 1
}

job_start

###### 可在此处开始编写您的脚本逻辑代码
###### 作业平台中执行脚本成功和失败的标准只取决于脚本最后一条执行语句的返回值
###### 如果返回值为0，则认为此脚本执行成功，如果非0，则认为脚本执行失败
set -o nounset                              # Treat unset variables as an error

usage() {
    echo "cleardata.sh [absolute_path] [N day|minute] [file_pattern]"
    echo "Example: ./cleardata.sh /data/log/ 3 "*.log""
    echo "directory should not be system path"
    echo "with m or M suffix, means N minutes, else N days."
    exit 1
}

# reuse cleardata logic
is_valid_dir() {
    local fn=$1
    # strip  ////* to /
    t=0
    for(( t=0; t<100; t++)); do
        nfn=${fn/\/\//\/}
        if [ $nfn == $fn ];then
            fn=$nfn;
            break;
        fi
        fn=$nfn;
    done

    if [[ "$fn" == "" || $(basename $fn) == "/" ]];then
        return 1
    fi

    for sysdir in /lib/ /usr/ /usr/lib/ /lib64/ /usr/lib64/ /usr/local/lib/ /bin/ /usr/bin/ /usr/local/bin/ /sbin/ /usr/sbin/ /usr/local/sbin/ /boot/ /etc/  /proc/ /sys/; do
     if [[ $(readlink -f $sysdir) = $(readlink -f $fn) ]]; then
            echo $fn is sysdir $sysdir
            return 1
        fi
    done

    return 0
}

get_dir_partition_usage() {
    local dir=$1
    /bin/df "$dir" | grep -Eo '[0-9]+%'
}

del_dir() {
    local dir=$1
    if ! [[ -e "$dir" ]]; then
        echo "$dir is not exist."
        return
    fi

    istest=0
    if [[ "$4" == "test" ]]; then
        istest=1
    fi

    cmd=""
    if echo "$2" | grep -q '[mM]' &>/dev/null; then
        min=$(echo $2 | sed 's/[mM]//')
        if (( istest )); then
            delete_result=$(/usr/bin/find "$dir/" -type f -mmin +$min -name "$3" -printf "DeleteFile: %f Size: %s
")
        else
            delete_result=$(/usr/bin/find "$dir/" -type f -mmin +$min -name "$3" -printf "DeleteFile: %f Size: %s
" -delete)
        fi
    else
        if (( istest )); then
            delete_result=$(/usr/bin/find "$dir/" -type f -mtime +"$2" -name "$3" -printf "DeleteFile: %f Size: %s
")
        else
            delete_result=$(/usr/bin/find "$dir/" -type f -mtime +"$2" -name "$3" -printf "DeleteFile: %f Size: %s
" -delete)
        fi
    fi

    echo "$delete_result" |    awk -v dir="$dir" -v usage=$(get_dir_partition_usage $dir) '{ sum+=$4 } END { print dir, NR-1, sum, usage }'
}

if (( $# < 3 || $# > 4 )); then
    usage
fi

target="$1"
range="$2"
pattern="$3"
if [[ $# -eq 4 ]]; then
    istest="$4"
else
    istest=""
fi

IFS=";" read -r -a Dirs <<< "$target"

if ! echo "$range" | grep -qE '[0-9]+(m|M)?' &>/dev/null; then
    usage
fi

echo -n "FTAARGV return_clear_disk_result:"

for dir in ${Dirs[@]}; do
    if is_valid_dir "$dir"; then
        del_dir  "$dir" "$range" "$pattern" "$istest"
    fi
done