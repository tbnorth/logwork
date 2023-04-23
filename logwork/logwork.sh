if [ "$1" = "h" ] ; then
    echo >> ~/.worklog
    history | tail -n 30 | sed 's/^[[:space:][:digit:]]*//' >> ~/.worklog
    vim ~/.worklog -c "normal G" -c '?^\d\{8\}-\d\{4\}' -c "normal zz"
else
    logwork.py $@
fi
