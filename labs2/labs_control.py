import dotenv
import subprocess
import signal
import random
import requests
import threading
import functools
import math
import time

class LabsControl:
    def __init__(self, base_path):
        self.base_path = base_path
        dotenv_path = base_path + '/.env'
        self.env = dotenv.dotenv_values(
            dotenv_path=dotenv_path
        )

        self.sp = None

    def build(self):
        return subprocess.run("docker build -t ds_labs_server {}/server".format(self.base_path), shell=True, check=True).returncode == 0


    def start_scenario(self, num_servers=1, scenario='perfect', scenario_timeout=0):

        if self.sp is not None:
            return
        self.num_servers = num_servers
        self.sp = subprocess.Popen("python {}/labs.py {} {} {}".format(self.base_path, num_servers, scenario, scenario_timeout), shell=True, stdin=subprocess.PIPE, encoding='utf-8')

    def change_scenario(self, s):
        if self.sp:
            self.sp.stdin.write(s + "\n")
            self.sp.stdin.flush()

    def get_server_list(self, num_servers=1):
        server_list = ["localhost:" + str(int(self.env['BASE_SERVER_PORT']) + i) for i in range(num_servers)]
        return server_list

    def shutdown(self):
        if self.sp:
            self.sp.send_signal(signal.SIGINT)
            self.sp.wait()
            self.sp = None


class ServerManager():
    def __init__(self, server_list):
        self.server_list = server_list

    def req(self, srv_id, URI, req='POST', data=None, timeout_s=30):
        srv_ip = self.server_list[srv_id]
        success = False
        try:
            if 'POST' in req:
                # We handle data string as json for now
                headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
                res = requests.post('http://{}{}'.format(srv_ip, URI), data=data, headers=headers,
                                    timeout=timeout_s)
            elif 'GET' in req:
                headers = {'Accept': 'application/json'}
                res = requests.get('http://{}{}'.format(srv_ip, URI), headers=headers, timeout=timeout_s)
                # result can be accessed res.json()
            else:
                res = None

            if res is not None and res.status_code == 200:
                success = True
        except Exception as e:
            print("[ERROR] " + str(e))
            res = None
        return (success, res)

    def post(self, srv_id, URI, data=None, timeout_s=30):
        return self.req(srv_id, URI, 'POST', data, timeout_s)

    def get(self, srv_id, URI):
        return self.req(srv_id, URI, 'GET', None)

    def status(self, id):
        s, r = self.req(id, "/status", 'GET')
        if s:
            return r.json()
        else:
            return None

class CrashManager():
    def __init__(self, sm : ServerManager):
        self.sm = sm
        self.crashed_servers = set() # no server crashed in the beginning

    def crash_server(self, id):
        self.sm.post(id, "/crash")
        self.crashed_servers.add(id)

    def recover_server(self, id):
        self.sm.post(id, "/recover")
        self.crashed_servers.remove(id)

    def get_alive_ids(self):
        return [i for i in range(len(self.sm.server_list)) if i not in self.crashed_servers]

    def get_random_uncrashed_server(self):
        alive_ids = self.get_alive_ids()
        if len(alive_ids) == 1:
            return None
        else:
            return random.choice(alive_ids)

    def get_random_crashed_server(self):
        if len(self.crashed_servers) == 0:
            return None
        else:
            return random.choice(list(self.crashed_servers))

    def crash_random_server(self):
        id = self.get_random_uncrashed_server()
        if id is not None:
            self.crash_server(id)
            return True
        else:
            return False

    def recover_random_server(self):
        id = self.get_random_crashed_server()
        if id is not None:
            self.recover_server(id)
            return True
        else:
            return False

class EntryManager:
    def __init__(self, sm : ServerManager):
        self.sm = sm

    def handle(self, callbacks, in_parallel=False):
        res = None
        if in_parallel:
            res = [None for cb in callbacks]
            threads = []
            for i, cb in enumerate(callbacks):
                def wrapped_cb(idx, cb):
                    res[idx] = cb()

                threads.append(threading.Thread(target=functools.partial(wrapped_cb, i, cb), args=()))

            for t in threads:
                t.start()

            for t in threads:
                t.join()
        else:
            res = [
                cb() for cb in callbacks
            ]
        return res

    def add_entry_to_sever(self, server_id, value):
        return self.sm.post(server_id, '/entries', data={'value': str(value)})

    def get_entries_from_server(self, server_id):
        return self.sm.get(server_id, '/entries')

    def add_entries(self, count, servers, parallel=False):
        def add_entries_cb(server):
            for i in range(count):
                self.add_entry_to_sever(server, random.randint(0, 1000000))

        callbacks = [functools.partial(add_entries_cb, server) for server in servers]
        return self.handle(callbacks, parallel)

class DSLTestControl():

    def __init__(self, lc: LabsControl):
        self.lc = lc

    def init_servers(self, count):
        print(f"initing {count} servers")
        self.lc.shutdown()
        self.lc.start_scenario(num_servers=count, scenario_timeout=0)

        self.sm = ServerManager(self.lc.get_server_list(count))
        self.cm = CrashManager(self.sm)
        self.em = EntryManager(self.sm)

    def parse_server_args(self, servers):
        if servers == 'all' or servers == '100%':
            return list(range(self.lc.num_servers))
        # if servers is just a number, it is an absolute number of random servers
        elif isinstance(servers, str) and servers[-1] == '%':
            # select a random subset of nodes
            num_servers = math.ceil(float(servers[:-1]) / self.lc.num_servers)
            return random.sample(range(self.lc.num_servers), num_servers)
        elif isinstance(servers, list):
            # the servers are already given as a list, we just remove duplicates
            uniq = []
            for s in servers:
                s = int(s)
                if s not in uniq:
                    uniq.append(s)
            return uniq
        elif isinstance(servers, int):
            # servers is a single number
            num_servers = int(servers)
            return random.sample(range(self.lc.num_servers), num_servers)
        else:
            raise ValueError(f"Invalid server argument {servers}")

    def parse_percentage(self, percentage):

        if percentage == 'all':
            percentage = '100%'

        if type(percentage) == int:
            num_required = percentage
        else:
            num_required = math.ceil(int(percentage[:-1])*0.01 * self.lc.num_servers)

        num_required = min(self.lc.num_servers, num_required)

        return num_required

    def change_scenario(self, name):
        print(f"Scenario {name}")
        self.lc.change_scenario(name)

    def crash_servers(self, servers):
        print(f"Crashing servers {servers}")
        for s in self.parse_server_args(servers):
            self.cm.crash_server(s)

    def recover_servers(self, servers):
        print(f"Recovering servers {servers}")

        for s in self.parse_server_args(servers):
            self.cm.recover_server(s)

    def assertion_online(self, servers):
        print(f"assertion_online servers {servers}")
        return all([self.sm.status(s) is not None for s in self.parse_server_args(servers)])

    def assertion_equal(self, percentage, servers):
        print(f"assertion_equal servers {servers}")

        all_hashes = [self.sm.status(s)['hash'] for s in range(self.lc.num_servers)]

        num_required = self.parse_percentage(percentage)

        suc = True
        for s in self.parse_server_args(servers):
            ref_hash = all_hashes[s]

            if all_hashes.count(ref_hash) < num_required:
                suc = False
                break

        print(f"assertion_equal result {suc}")
        return suc

    def assertion_equal_length(self, percentage, servers):
        print(f"assertion_equal_length servers {servers}")

        all_lens = [self.sm.status(s)['hash'] for s in range(self.lc.num_servers)]

        num_required = self.parse_percentage(percentage)

        for s in self.parse_server_args(servers):
            ref_len = all_lens[s]

            if all_lens.count(ref_len) < num_required:
                return False
        return True

    def wait_until(self, assertion):
        print(f"Waiting until {assertion}")
        start_time = time.time()
        while not assertion():
            #print("Sleeping!")
            time.sleep(0.1) # sleep for 100 ms to not overwhelm the servers...
        end_time = time.time()
        print(f"Waited for {end_time - start_time:.2f} seconds")  # todo Log time!

    def waits(self, secs):
        print(f"Wait for {secs} seconds")
        time.sleep(secs)

    def log_assertion(self, start_time, end_time, succ):
        print(f"Assertion took {end_time - start_time:.2f} seconds")
        print(f"Assertion {'succeeded' if succ else 'failed'}")

    def add_entries(self, count, servers, parallel=False):
        print(f"Adding {count} entries to servers {servers} {'in parallel' if parallel else ''}")
        self.em.add_entries(count, self.parse_server_args(servers), parallel)

    def update_entries(self, entries, servers, parallel=False):
        print(f"Updating {entries} of entries on servers {servers} {'in parallel' if parallel else ''}")
        print("Not yet implemented")
        # NOT YET IMPLEMENTED, sorry!

if __name__ == "__main__":

    lc = LabsControl('.')
    try:
        lc.build()
        lc.start_scenario(num_servers=2, scenario_timeout=5)
        import time
        time.sleep(10) # we need to wait until the initial scenario timed out!
        lc.change_scenario('easy')
        time.sleep(5)
        lc.change_scenario('off')
        time.sleep(5)
        lc.change_scenario('easy')
        time.sleep(30)
    finally:
        lc.shutdown()
