import sys
import os
import threading

from dotenv import load_dotenv
import requests
import time

from labs_control import LabsControl, DSLTestControl

lc = LabsControl('.')
dsl_ctrl = DSLTestControl(lc)

NUM_ENTRIES = 10 # You might want to add more entries later to test consistency
NUM_SERVERS = 4 # you can scale this up but need to change the partitions to test as well

PARTITIONS = [[0, 2], [1, 3]] # You can change this to test different partitions, atm the test for equality is not best suited for partitions, you should check manually as well...

SCENARIO = 'perfect' # 'perfect', 'easy', 'medium', 'hard'
SCENARIO_PARTITIONED = SCENARIO + '_partitioned'

IN_PARALLEL = True

try:
    lc.build()  # build the servers to make sure that they are up to date for the test
    dsl_ctrl.init_servers(NUM_SERVERS)  # Initialize servers
    dsl_ctrl.waits(5)  # Give servers some time to start, otherwise you will see a lot of errors...
    dsl_ctrl.wait_until(lambda: dsl_ctrl.assertion_online('all'))  # wait until all servers are online
    dsl_ctrl.change_scenario(SCENARIO_PARTITIONED)  # Change the scenario and partition the nodes, e.g., to partitions: [0, 2], [1, 3]
    dsl_ctrl.waits(5)  # Give the scenario some time to change...

    start_time = time.time()
    dsl_ctrl.add_entries(NUM_ENTRIES, 'all', parallel=IN_PARALLEL)  # Add entries to each server (in parallel)
    dsl_ctrl.wait_until(lambda: all([dsl_ctrl.assertion_equal(len(p), p) for p in PARTITIONS]))  # wait until all servers have the same number of entries this will loop if there is no consistency!
    print("Time taken to reach consistency in partitions: " + str(time.time() - start_time))

    #dsl_ctrl.waits(60)  # add this to check for consistency manually

    start_time = time.time()
    dsl_ctrl.change_scenario(SCENARIO)  # Change the scenario back to the original one
    dsl_ctrl.wait_until(lambda: dsl_ctrl.assertion_equal('all', 'all'))  # wait until all servers have the same number of entries this will loop if there is no consistency!
    print("Time taken to reach consistency across all servers: " + str(time.time() - start_time))

    dsl_ctrl.waits(900) # leave the servers running for 15 minutes
except KeyboardInterrupt:
    lc.shutdown()
finally:
    lc.shutdown()