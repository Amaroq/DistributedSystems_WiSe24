import sys
import os
import threading

from dotenv import load_dotenv
import requests
import time

# import server manager as well to get an element from the server_list
from labs_control import LabsControl, DSLTestControl, ServerManager

lc = LabsControl('.')
dsl_ctrl = DSLTestControl(lc)
sm = ServerManager(lc)


NUM_ENTRIES = 10 # You might want to add more entries later to test consistency
NUM_SERVERS = 4
# for task 2: perfect scenario
SCENARIO = 'medium'
# for other tasks: medium scenario
#SCENARIO = 'medium' # 'perfect', 'easy', 'medium', 'hard'

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

    # wait a bit before starting threads
    dsl_ctrl.waits(2)

    # test concurrent messages/entry requests

    def t1():
        dsl_ctrl.add_entries(5,1,parallel=IN_PARALLEL)
        time.sleep(2)

    def t2():
        dsl_ctrl.add_entries(5,1,parallel=IN_PARALLEL)
        time.sleep(2)

    def t3():
        dsl_ctrl.add_entries(5,2,parallel=IN_PARALLEL)
        time.sleep(2)
    
    def t4():
        dsl_ctrl.add_entries(5,2,parallel=IN_PARALLEL)
    
    thread1 = threading.Thread(target=t1)
    thread2 = threading.Thread(target=t2)

    thread1.start()
    thread2.start()

    ################### result of this: ###############
    #   server 0    server 1    server 2    server 3
    #   id  value   id  value   id  value   id  value
    #   41  556629  41  556629  41  556629  41  556629
    #   43  92676   43  92676   43  92676   43  92676
    #   45  160075  45  160075  45  160075  45  160075
    #   47  61645   47  61645   47  61645   47  61645
    #   49  482249  49  482249  49  482249  49  482249
    # >>> data is consistent, but entries get lost (5 missing)
    # >>> ds_labs_server_0: Received message:  {'type': 'add_entry', 'entry_value': '138807'}
    # >>> ds_labs_server_0: Received message:  {'type': 'add_entry', 'entry_value': '556629'}
    # >>> ds_labs_server_0: Received message:  {'type': 'propagate', 'entry_value': '138807', 'entry_id': 41}
    # >>> ds_labs_server_0: Received message:  {'type': 'propagate', 'entry_value': '556629', 'entry_id': 41}
    # >>> only one entry_id is generated for both of the entries, meaning eventhough
    # >>> both values are propagated, the first one gets overwritten by the second one,
    # >>> resulting in the loss of 5/10 entries -> "collision handling"
    # (During one test, 6/10 entries came through, so the actual result might depend
    # on python delays (as GlobalInterpreterLock is a bit weird sometimes))

    dsl_ctrl.waits(2)

    # other tests below; same results
    #thread3 = threading.Thread(target=t3)
    #thread4 = threading.Thread(target=t4)

    #print('Threads created')
    #dsl_ctrl.waits(2)

    #thread3.start()
    #thread4.start()

    #thread3.join()
    #thread4.join()
    
    print('Threads started')

    dsl_ctrl.waits(900) # leave the servers running for 15 minutes
except KeyboardInterrupt:
    lc.shutdown()
finally:
    lc.shutdown()