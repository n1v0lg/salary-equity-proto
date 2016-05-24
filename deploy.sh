shopt -s extglob
for DIRECTORY in server-1 server-2 server-3
do
	if [ ! -d "$DIRECTORY" ]; then
  		mkdir $DIRECTORY
	fi
    rm $DIRECTORY/!(*.cert|*.key|config.py) -f -r
    cp *.py *.html $DIRECTORY
done