from __future__ import division

import collections
import recordclass
import time
import pprint

PRINT_FUNCS = False

Field = recordclass.recordclass("Field", ["total", "count"])

time_log = collections.defaultdict(
    lambda: collections.defaultdict(
        lambda: Field(0, 0)
        )
    )


def reset():
    time_log.clear()


def track(section):
    sec = time_log[section]

    def decorator(func):
        name = func.func_name

        def wrapper(*args, **kwargs):
            if PRINT_FUNCS:
                print name
                pprint.pprint(args)
                pprint.pprint(kwargs)
            start = time.time() * 1000
            ret = func(*args, **kwargs)
            dur = (time.time() * 1000) - start

            sec[name].total += dur
            sec[name].count += 1

            return ret
        return wrapper
    return decorator


def display():
    pad = 1 + max(len(name)
                  for cat in time_log
                  for name in time_log[cat])
    for cat in sorted(time_log):
        print("### {}".format(cat))
        entries = [(name, f.total/f.count)
                   for name, f in time_log[cat].items()]
        for name, avg in sorted(entries,
                                key=lambda x: x[1],
                                reverse=True):
            print("    {0:{pad}}: {1:>9.4f}".format(name, avg, pad=pad))

def gnuplot():
    for cat in sorted(time_log, key=lambda x: int(x.split("-")[1])):
        measures = {name:(f.total/f.count) for name, f in time_log[cat].items()}
        measures['i'] =  int(cat.split("-")[1])
        print("{i} {process_msg} {dump} {sync}".format(**measures))
                                   
