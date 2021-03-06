shopt -s extglob
bash deploy.sh

kill_c_procs() {
    pkill -P $$
}

trap kill_c_procs INT

for i in {1..2};
do
    cd server-$i
    python sumofsquares.py `expr $i - 1` &
    cd ../
done
wait
