SCRIPT_DIR="$( dirname -- $( realpath "${BASH_SOURCE[0]}" ) )"
WORKLOG=~/.worklog
if [ "$1" = "h" ] ; then
    echo >> $WORKLOG
    history | tail -n 30 | sed 's/^[[:space:][:digit:]]*//' >> $WORKLOG
    vim $WORKLOG -c "normal G" -c '?^\d\{8\}-\d\{4\}' -c "normal zz"
else
    python $SCRIPT_DIR/logwork.py $@
fi
