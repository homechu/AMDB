now=$(pwd)
project="cmdb_api"
dir=$(dirname $0)
arg=$2
cd ${dir}

cpu=$(nproc --all)
max_concurrency=$(($cpu * 16))

worker_args="-l info --autoscale=${cpu},${max_concurrency} -n ${project}"
worker_daemon="-f logs/worker.log --pidfile=pids/%n.pid"

beat_args="-l info -s pids/beat -f logs/beat.log --pidfile pids/beat.pid --detach"

function usage() {
    echo -e "\033[31m"
    echo -e "Usage:"
    echo -e "   $0 [start|stop|restart|state|worker|beat]"
    echo -e "\033[0m"
}

function start() {
    mkdir -p logs pids

    num=$(state | wc -l)
    if [ ${num} -gt 0 ]; then
        echo "[ERROR] celery had started already"
        exit
    fi

    rm -f pids/beat

    celery multi start worker -A main $worker_args $worker_daemon

    if [ "$arg" != 'nobeat' ]; then
        celery -A main beat $beat_args
    fi

    sleep 1

    num=$(state | grep beat | wc -l)
    if [ ${num} -gt 0 ]; then
        echo "[INFO] celery beat start success"
    else
        echo "[ERROR] celery beat start fail"
    fi

    num=$(state | grep worker | wc -l)
    if [ ${num} -gt 0 ]; then
        echo "[INFO] celery worker start success"
    else
        echo "[ERROR] celery worker start fail"
    fi
}

function stop() {
    celery multi stopwait worker -A main $worker_args $worker_daemon
    kill -9 $(ps aux | grep ${project} | grep celery | grep -v bash | gawk '{print $2}')
    rm -f pids/beat.pid
}

function state() {
    ps aux | grep ${project} | grep celery | grep -v bash
}

function restart() {
    celery multi restart worker -A main $worker_args $worker_daemon

    kill -9 $(ps aux | grep ${project} | grep celery | grep beat | grep -v bash | gawk '{print $2}')
    rm -f pids/beat.pid

    if [ "$arg" != 'nobeat' ]; then
        celery -A main beat $beat_args
    fi
}

function worker() {
    celery -A main worker $worker_args
}

function beat() {
    celery -A main beat -l info -s pids/beat
}

case $1 in
start | stop | restart | state | worker | beat)
    $1 $2
    ;;
*)
    usage
    ;;
esac

cd $now
