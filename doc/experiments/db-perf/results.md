# Results

## ./test.py --iters 1000 --files 100 --fds 10
### neo4j
    handle_process_start :   54.46
    handle_file_close    :   52.93
    process_msg          :   37.11
    local_by_name        :   36.23
    handle_file_open     :   20.85
    drop_g               :   16.45
    version_global       :   12.93
    get_l                :   11.10
    get_g                :    9.45
    create_new_global    :    4.31
    version_local        :    1.46
    drop_l               :    0.26
### sqldump
    process_msg          :    3.99
### dump
    process_msg          :    0.45
    sync                 :    0.39
    dump                 :    0.05
### sql
    process_msg          :    8.24
    handle_process_start :    7.14
    handle_file_open     :    4.83
    handle_file_close    :    4.40
    drop_g               :    3.72
    get_g                :    3.62
    version_global       :    3.37
    version_local        :    2.56
    get_l                :    0.76
    drop_l               :    0.33
