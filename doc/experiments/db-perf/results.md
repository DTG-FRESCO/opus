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

## ./test.py --iters 10000 --files 100 --fds 10
### neo4j
    handle_file_close    : 1907.47
    drop_g               : 1842.30
    process_msg          : 1001.65
    version_global       :  967.75
    create_new_global    :  886.11
    handle_process_start :  613.19
    handle_file_open     :   95.40
    get_g                :   84.81
    local_by_name        :   64.71
    get_l                :   10.28
    version_local        :    1.58
    drop_l               :    0.30
### sqldump
    process_msg          :    4.00
### dump
    process_msg          :    0.44
    sync                 :    0.38
    dump                 :    0.06
### sql
    process_msg          :    9.05
    handle_file_open     :    5.71
    handle_file_close    :    4.88
    get_g                :    4.39
    handle_process_start :    4.33
    drop_g               :    4.09
    version_global       :    3.74
    version_local        :    2.83
    get_l                :    0.83
    drop_l               :    0.37

## Experiments in differing sync frequencies for dump to file
(data.png)
