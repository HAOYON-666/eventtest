ps -ef | grep CloudEagleTest | awk '{print $2}' | xargs kill -9 
ps -ef | grep kill_run | awk '{print $2}' | xargs kill -9 
