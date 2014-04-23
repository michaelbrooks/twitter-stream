#!/bin/bash

INI_FILE=$1

pipe=/tmp/euromaidan.pipe
if [[ ! -p $pipe ]]; then
    mkfifo $pipe
fi

function cleanup {
    kill $producer_pid > /dev/null 2>&1
    kill $consumer_pid > /dev/null 2>&1
    rm -f $pipe
    echo "Cleanup finished"
}

trap cleanup EXIT

export PYTHONUNBUFFERED=1

#cat < $pipe >> logs/second.log &
python dbimport.py $INI_FILE < $pipe 2>> logs/import.log &
consumer_pid=$!

#python test.py 2>> logs/first.log > $pipe &
stream_tweets --ini-file $INI_FILE 2>> logs/stream.log > $pipe &
producer_pid=$!

while (kill -0 "$consumer_pid" > /dev/null 2>&1) && (kill -0 "$producer_pid" > /dev/null 2>&1); do
    sleep 1.0
done
echo "Finished"
