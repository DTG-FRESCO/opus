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
    for cat in time_log:
        print("==========")
        print(cat)
        print("==========")
        entries = [(name, f.total/f.count)
                   for name, f in time_log[cat].items()]
        for name, avg in sorted(entries,
                                key=lambda x: x[1],
                                reverse=True):
            print("{}: {:.2f}".format(name, avg))
