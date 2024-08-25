INFO='\033[0;102m[INFO]\033[0m'
ERROR='\033[0;101m[ERROR]\033[0m'
WARN='\033[0;103m[WARNING]\033[0m'

now=$(pwd)
module=$(realpath $0 | xargs dirname | gawk -F '/' '{print $(NF-1)"_"$NF}')
dir=$(dirname $0)
ini="main/uwsgi.ini main/uwsgi.daemonize.ini"
log=logs/uwsgi.log
pidfile=pids/uwsgi.pid

cd ${dir}

if [ -f ~/.bashrc ]; then
    source ~/.bashrc
fi

function usage(){
    echo -e "\033[31m"
    echo -e "Usage:"
    echo -e "   $0 [start|stop|restart|state|run]"
    echo -e "\033[0m"
}

function check() {
    attempt=1
    while [[ $attempt -le 5 ]]; do
        if [ -f ${pidfile} ]; then
            echo -e "${INFO} ${module} uwsgi start success"
            break
        fi
        attempt=$(($attempt + 1))
        sleep 1
    done

    if [ ! -f ${pidfile} ]; then
        echo -e "${ERROR} ${module} uwsgi start fail or timeout"
        exit 1
    fi
}

function start() {
    mkdir -p logs pids

    if [ -f ${pidfile} ]; then
        echo -e "${ERROR} ${module} uwsgi already started, using restart"
        exit 1
    fi

    uwsgi --ini ${ini} --pyargv ${module} --daemonize ${log} --logger file:${log}
    check

    num=$(grep -n 'Starting uWSGI' $log | gawk -F ':' '{print $1}' | tail -n 1)
    end=$(($num + 40))
    sed -n "${num},${end}p" ${log}
}

function stop() {
    if [ ! -f "$pidfile" ]; then
       echo "${ERROR} ${module} uwsgi not running"
       exit 1
    fi
    uwsgi --stop ${pidfile}
}

function state() {
    ps aux | grep uwsgi | grep ${module} | grep -v grep
}

function restart() {
    poetry install

    if [ ! -f ${pidfile} ]; then
        echo -e "${WARN} ${module} uwsgi not running, force restart."
        kill -9 $(ps aux | grep uwsgi | grep ${module} | grep -v grep | grep -v bash | awk '{print $2}')
        start
        exit
    fi

    uwsgi --ini ${ini} --reload ${pidfile}
    check
}

function run() {
    if [ -f ${pidfile} ]; then
        echo -e "${ERROR} ${module} uwsgi already started, using restart"
        exit 1
    fi
    uwsgi --ini ${ini} --pyargv ${module} --stats :3031 --stats-http
}

case $1 in
start | stop | restart | state | run)
    $1
    ;;
*)
    usage
    ;;
esac

cd $now
