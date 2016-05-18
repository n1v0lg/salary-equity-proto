shopt -s extglob
bash deploy.sh

kill_c_procs() {
    pkill -P $$
}

trap kill_c_procs INT

for i in {1..3};
do
    cd server-$i
    echo $PWD
    python server.py `expr $i - 1` &
    cd ../
done
wait
