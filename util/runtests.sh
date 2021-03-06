#!/bin/bash
# Should be run in the directory where the log files should be saved.
# It should also have ../mic-odm-yaml/ directory, which contains all the microscopes files.
# Ex:
# cd odemis-testing/
# ../odemis/util/runtests.sh 2>&1 | tee test-$(date +%Y%m%d).log
#
# The global result is saved in test-XXX.log
# It will generate one file and one directory:
#  * unittest-full-$DATE.log : results of unit tests
#  * ./integtest-$DATE/ : results of integration testing (2 files per conf)

# Root path of the repo
ODEMIS_DIR="$(readlink -m $(dirname $0)/../)"
ODEMIS_SRC="$ODEMIS_DIR/src/odemis"

# Some basic static analysis
echo "Total number of lines of code (not including test cases):"
find "$ODEMIS_SRC" -name "*.py" -a -not -name "*_test.py" -print0 | wc -l --files0-from=- | tail -1

# Not related to tests, but to QA in general: Exceptions usually take only 1 argument
# So a comma is probably a sign of syntax error and should be replace by a %
echo "These files might have syntax error when raising an exception:"
grep -IrE --colour 'raise.*",' --include=*.py "$ODEMIS_SRC"
echo "---"

echo "These files are not using division from the future:"
find "$ODEMIS_SRC" -name "*.py" -size +20c -exec grep -IL "from __future__ import.*division" {} \;
#grep -IrL "from __future__ import.*division" --include=*.py "$ODEMIS_SRC"
echo "---"

echo "These files do not have the license header:"
grep -LIr "GNU General Public License" --include=*.py "$ODEMIS_SRC"
echo "---"

DATE=$(date +%Y%m%d)

# Run all the unit tests that can be found:
# Every file which is in the pattern /test/*_test.py
MAXTIME=1800  # 30 min maximum per test case

PYTHONPATH="$ODEMIS_SRC"/../:../Pyro4/src/:"$PYTHONPATH"
if [ -f /etc/odemis.conf ]; then
    # use the odemis config if it's available
    . /etc/odemis.conf
fi
export PYTHONPATH

# This environment variable makes the GUI test cases automatically close the test frames
export NOMANUAL=1

# This environment variable (should) make the driver test not try to use real hardware (only simulator)
export TEST_NOHW=1

TESTLOG=./unittest-full-$DATE.log
# make sure it is full path
TESTLOG="$(readlink -m "$TESTLOG")"

if [ ! -d /var/run/odemisd ] ; then
    echo  "Need /var/run/odemisd"
    sudo mkdir -m 777 /var/run/odemisd
fi

# stop the backend
sudo odemis-stop

# find the test scripts (should not contain spaces)
testfiles="$(find "$ODEMIS_SRC" -wholename "*/test/*test.py")"

#Warn if some files are misnamed
skippedfiles="$(find "$ODEMIS_SRC" -wholename "*/test/*.py" -and -not -wholename "*/test/*test.py")"
if [ "$skippedfiles" != "" ]; then
    echo "Warning, these scripts are not named *_test.py and will be skipped:"
    echo "$skippedfiles"
fi

echo "Running unit tests"
echo "Running unit tests on $(date)" > "$TESTLOG"

# run each test script and save the output
failures=0
for f in $testfiles; do
    echo "Running $f..."
    if ! grep -q "__main__" $f; then
        echo "WARNING: test $f seems to not be runnable"
    fi
    echo "Running $f:" >> "$TESTLOG"
    # run it in its own directory (sometimes they need specific files from there)
    pushd "$(dirname $f)" > /dev/null
        # Automatically kill after MAXTIME, then try harder after 30 s
        timeout -k 30 $MAXTIME python $f --verbose >> "$TESTLOG" 2>&1
        status=$?
        echo $f returned $status >> "$TESTLOG" 2>&1
    popd > /dev/null
    grep -E "(OK|FAILED)" "$TESTLOG" | tail -1
    if [ "$status" -gt 0 ]; then
        # TODO: failures can increase even if the test reported OK, if it was killed
        # => synchronise it with FAILED
        failures=$(( $failures + 1 ))
    fi
    echo Failures so far: $failures
done

if [ $failures -gt 0 ]; then
    echo "$failures test failed. See $TESTLOG for error messages."
else
    echo "All tests passed"
fi

# try to clean up a bit
sudo odemis-stop


# Run the integration tests
ODMPATH="$ODEMIS_DIR/../mic-odm-yaml/"
INTEGLOGDIR="./integtest-$DATE/"
mkdir -p "$INTEGLOGDIR"

echo "Running integration tests"
"$ODEMIS_DIR/util/run_intg_tests.py" --log-path "$INTEGLOGDIR" "$ODMPATH"/*/
