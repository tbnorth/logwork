if [ "$1" = "h" ] ; then
    echo >> ~/.worklog
    history | tail -n 30 | sed 's/^[[:space:][:digit:]]*//' >> ~/.worklog
    vim -c "normal G" ~/.worklog
else
    logwork.py $@
fi
