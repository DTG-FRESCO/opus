set logscale x 2
set term png
set output "data.png"
set title "Effect on message processing time of varying sync frequency"
set ylabel "Time taken (ms)"
set xlabel "Sync Frequency (every nth)"
plot "data.dat" using 1:2 title 'process_msg' with linesp, \
     "data.dat" using 1:3 title 'dump' with linesp, \
     "data.dat" using 1:4 title 'sync' with linesp
set term x11
