# DB Performance Tests

A test designed to evaluate the performance of various DB back ends for the purpose of PVM message processing. A set of synthetic PVM messages are generated then provided to each test implementation in turn. The performance of the implementations is measured and then outputted on the terminal. A log of known results can be found in results.md.

## Test Commands
    ./test.py
    usage: test.py [-h] [--iters ITERS] [--files FILES] [--fds FDS]

    Run message processing benchmarks.

    optional arguments:
      -h, --help     show this help message and exit
      --iters ITERS  Set the number of messages to generate.
      --files FILES  Set the number of unique files.
      --fds FDS      Set the number of unique file descriptors

## Backends under test
* Neo4j Bolt - Interfaced via python
* SQLite
* SQLite Dump
* Raw File Dump

## Conclusions
Neo4j Bolt is still too slow to be used, also the characteristic of increasing processing time with larger test sizes is worrying and unhelpful. SQLite shows reasonable results, but still much higher than we would desire. SQL logging is slow enough that it is unlikely to be worth it, direct logging gives a reasonable performance baseline, though is still somewhat slow, potentially we need to look into parallelisation of PVM processing.
