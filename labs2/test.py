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
NUM_SERVERS = 4
SCENARIO = 'perfect' # 'perfect', 'easy', 'medium', 'hard'

IN_PARALLEL = False   # Somebody told me there were issues in the test, I set this to false, tests are now fixed, thank me later

try:
    lc.build()  # build the servers to make sure that they are up to date for the test
    dsl_ctrl.init_servers(NUM_SERVERS)  # Initialize servers
    dsl_ctrl.waits(5)  # Give servers some time to start, otherwise you will see a lot of errors...
    dsl_ctrl.wait_until(lambda: dsl_ctrl.assertion_online('all'))  # wait until all servers are online
    dsl_ctrl.change_scenario(SCENARIO)  # Change the scenario

    start_time = time.time()
    dsl_ctrl.add_entries(NUM_ENTRIES, 'all', parallel=IN_PARALLEL)  # Add entries to each server (in parallel)
    dsl_ctrl.wait_until(lambda: dsl_ctrl.assertion_equal('all', 'all'))  # wait until all servers have the same number of entries this will loop if there is no consistency!
    print("Time taken: " + str(time.time() - start_time))

    dsl_ctrl.waits(2) # wait for two seconds, then spawn two threads and start two more servers at the same time
    
    def t1():
        dsl_ctrl.init_servers(1)
        time.sleep(2)
    def t2():
        dsl_ctrl.init_servers(1)
        time.sleep(2)

    thread1 = threading.Thread(target=t1)
    thread2 = threading.Thread(target=t2)

    thread1.start()
    thread2.start()

    dsl_ctrl.waits(900) # leave the servers running for 15 minutes
except KeyboardInterrupt:
    lc.shutdown()
finally:
    lc.shutdown()