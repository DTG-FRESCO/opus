#!/usr/bin/perl -w

use strict;
use POSIX qw(EXIT_SUCCESS EXIT_FAILURE);

use constant TEST_TIMEOUT => 60;

my $proj_home = $ENV{"PROJ_HOME"};
die "PROJ_HOME not set" if (not defined $proj_home);

my $opus_lib = $ENV{"OPUS_LIB_NAME"};
die "OPUS_LIB_NAME not set" if (not defined $opus_lib);

$opus_lib = "$proj_home/lib/lib$opus_lib.so";
die "$opus_lib not present" if (not -e $opus_lib);

my $libc_src_path = $ENV{"LIBC_SRC_PATH"};
die "LIBC_SRC_PATH not set" if (not defined $libc_src_path);

my $libc_build_path = $ENV{"LIBC_BUILD_PATH"};
die "LIBC_BUILD_PATH not set" if (not defined $libc_build_path);

my $proto_lib_path = $ENV{"PROTO_LIB_PATH"};
die "PROTO_LIB_PATH not set" if (not defined $proto_lib_path);

my $log_file = "$proj_home/src/tests/frontend/libc_reg_test.log";
open(LOG_FILE, ">$log_file") or die "Could not create $log_file";

# Redirect stdout and stderr to log file
open(STDOUT, ">&LOG_FILE") or print "Could not redirect stdout to $log_file";
open(STDERR, ">&LOG_FILE") or print "Could not redirect stderr to $log_file";

&main();
close LOG_FILE;

sub execute_test
{
    my $exit = 0;
    my $signal = 0;
    my $exec_cmd = shift;

    &print_log("$exec_cmd\n");

    my $pidx = fork;
    if (!defined $pidx)
    {
        &print_log("Fork failed: $!\n");
        return ($exit, $signal);
    }
    elsif($pidx == 0)
    {
        exec $exec_cmd or print "Could not exec $exec_cmd: $!";
        exit(EXIT_FAILURE);
    }

    eval
    {
        local $SIG{ALRM} = sub { kill 9, $pidx; &print_log("Child $pidx TIMEOUT!!\n") };
        alarm TEST_TIMEOUT;
        my $cpid = wait;
        alarm 0;
        &print_log("Wait returned $cpid\n");
    };

    my $status = $?;

    if ($status & 128)
    {
        &print_log("core dumped\n");
        return ($exit, $signal);
    }

    $exit = $? >> 8;
    $signal = $? & 127;

    &print_log("exit = $exit, signal = $signal\n");
    return ($exit, $signal);
}

sub change_dir
{
    my $line = shift;
    my @tokens = split(/\s+/, $line);
    my $dir_path = pop(@tokens);

    $dir_path =~ s{^`|'$}{}g;
    chdir($dir_path);
}

sub get_sys_lib_paths
{
    my @paths = ();

    my $cmd = "ldconfig -v 2>/dev/null";
    open(FPIPE, "$cmd |") or die "Could not open pipe";

    while (<FPIPE>)
    {
        chomp;
        next if ($_ =~ /^\t/);
        push(@paths, $_);
    }
    close FPIPE;

    my $sys_lib_paths = join("", @paths);
    chop($sys_lib_paths);

    return $sys_lib_paths;
}

sub get_exec_cmd
{
    my $line = shift;

    my @tokens = split(/\s+/, $line);

    my $library_paths;
    my $index = 0;
    foreach my $token (@tokens)
    {
        if ($token =~ /--library-path/)
        {
            # Get a reference to the next index
            $library_paths = \$tokens[$index + 1];
            $$library_paths .= ":$proto_lib_path";

            my $sys_lib_paths = &get_sys_lib_paths();
            $$library_paths .= ":$sys_lib_paths";
        }
        ++$index;
    }

    my $cmd = join(" ", @tokens);
    return $cmd;
}

sub gen_test_log
{
    &print_log("Recompiling tests....\n");

    my $logfile = shift;

    chdir($libc_build_path);

    if (-e $logfile)
    {
        my $rm_cmd = "rm -f $logfile";
        system($rm_cmd);
        print "($rm_cmd): $!\n" if ($? == -1);
    }

    my $clean_cmd = "make tests-clean";

    system($clean_cmd);
    print "($clean_cmd): $!\n" if ($? == -1);

    my $check_cmd = "make -k check > $logfile 2>&1";
    system($check_cmd);
    print "($check_cmd): $!\n" if ($? == -1);

    die "Could not compile glibc test programs" if (not -e $logfile);
}

sub main
{
    my $test_log = "$libc_build_path/glibc_test.log";
    &gen_test_log($test_log);

    open(TLOG, "<$test_log") or die "Could not open $test_log";
    while (<TLOG>)
    {
        chomp;

        my $line = $_;

        &change_dir($line) if ($line =~ /Entering directory/);
        next if ($line !~ /^env/);

        my $exec_cmd = &get_exec_cmd($line);

        &print_log("Executing without OPUS library preloaded\n");
        my ($exit1, $signal1) = &execute_test($exec_cmd);

        $exec_cmd =~ s{.out}{.out.opus}g;
        &print_log("Executing with OPUS library preloaded\n");
        my $ld_preloaded_cmd = "LD_PRELOAD=$opus_lib $exec_cmd";
        my ($exit2, $signal2) = &execute_test($ld_preloaded_cmd);

        &print_log("Test failed!!\n") if (($exit1 != $exit2) or ($signal1 != $signal2));
        &print_log("\n");
    }
    close TLOG;

    &print_log("Finished executing tests\n");
}

sub print_log
{
    my $current_time = localtime;
    print LOG_FILE $current_time, ": ", @_;
}
