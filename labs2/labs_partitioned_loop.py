# run test_partitioned 5 times for each number of servers
# for each run: write into the test_partitioned_log.json:
    # test <i>, <scenario>
    # write the time it took to run test_partitioned.py into test_partitioned_log.json
# after 5 runs for one number of servers:
    # change to the next number of servers
# end, when number of servers == 10

import sys
import os
import threading

from dotenv import load_dotenv
import requests
import time
from datetime import datetime

from labs_control import LabsControl, DSLTestControl

lc = LabsControl('.')
dsl_ctrl = DSLTestControl(lc)

log_path = 'logs/test_partitions_log_' + datetime.now().strftime("%m-%d-%Y%-H-%M-%S") + '.csv'

with open(log_path, 'a') as file:
                    file.write('number of servers,number of entries,time to reach consistency in partitions,time until consistency on servers,test number,scenario\n')

for i in range (0,2): # to test functionality, only try perfect and easy for now
    NUM_ENTRIES = 10 # You might want to add more entries later to test consistency
    scenario_list = ['perfect', 'easy', 'medium', 'hard']
    SCENARIO = scenario_list[i]
    SCENARIO_PARTITIONED = SCENARIO + '_partitioned'
    IN_PARALLEL = True

    for j in range (2,10): # increase number of servers (max on this machine is 4 servers)
        #time.sleep(2) # sleep for a bit until all connections are properly reset
        if j == 2:
            PARTITIONS = [[0],[1]]
        elif j == 3:
            PARTITIONS = [[0,2],[1]]
        elif j == 4:
            PARTITIONS = [[0,2],[1,3]]
        elif j == 5:
            PARTITIONS = [[0,2,4],[1,3]]
        elif j == 6:
            PARTITIONS = [[0,2,4],[1,3,5]]
        elif j == 7:
            PARTITIONS = [[0,2,4,6],[1,3,5]]
        elif j == 8:
            PARTITIONS = [[0,2,4,6],[1,3,5,7]]
        elif j == 9:
            PARTITIONS = [[0,2,4,6,8],[1,3,6,7]]
        elif j == 10:
            PARTITIONS = [[0,2,4,6,8],[1,3,6,7,9]]
        NUM_SERVERS = j # you can scale this up but need to change the partitions to test as well

        for n in range(1,6): # increase number of entries SET TO 4 FOR 10,20,30 entries
            NUM_ENTRIES = NUM_ENTRIES * n # test for 10, 20 and 30
            k = 1
            while (k <= 3): # SET TO 3 FOR THREE TESTS
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
                    
                    with open(log_path, 'a') as file:
                        #file.write('servers: ' + str(NUM_SERVERS) + ', scenario: ' + str(SCENARIO) + str(k) + 'th test\n')
                        #file.write('Time taken to reach consistency in partitions: ' + str(time.time() - start_time) + '\n')
                        file.write(str(NUM_SERVERS) + ',' + str(NUM_ENTRIES) + ',' + str(time.time() - start_time))

                    print("Time taken to reach consistency in partitions: " + str(time.time() - start_time)) # write this to log file

                    #dsl_ctrl.waits(60)  # add this to check for consistency manually

                    start_time = time.time()
                    dsl_ctrl.change_scenario(SCENARIO)  # Change the scenario back to the original one
                    dsl_ctrl.wait_until(lambda: dsl_ctrl.assertion_equal('all', 'all'))  # wait until all servers have the same number of entries this will loop if there is no consistency!

                    with open(log_path, 'a') as file:
                        #file.write('Time taken to reach consistency across all servers: ' + str(time.time() - start_time) + '\n')
                        file.write(', ' +  str(time.time() - start_time) + ',' + str(k) + ',' + str(SCENARIO) + '\n')
                    
                    print("Time taken to reach consistency across all servers: " + str(time.time() - start_time))

                    #dsl_ctrl.waits(900) # leave the servers running for 15 minutes
                    dsl_ctrl.waits(2) # leave running for 2 seconds, then shutdown and go to next iteration
                except KeyboardInterrupt:
                    lc.shutdown()
                finally:
                    lc.shutdown()
                #time.sleep(2) # sleep for a bit until all connections are properly reset
                k = k+1
            NUM_ENTRIES = 10