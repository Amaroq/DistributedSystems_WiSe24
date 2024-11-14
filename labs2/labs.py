import json
import os
import sys
import threading
import time

import docker
import requests
from dotenv import load_dotenv
import datetime

load_dotenv()

FRONTEND_PORT = int(os.getenv('FRONTEND_PORT'))
BASE_SERVER_PORT = int(os.getenv('BASE_SERVER_PORT'))
PROXY_PORT = int(os.getenv('PROXY_PORT'))
GROUP_NAME = str(os.getenv('GROUP_NAME'))
DOCKER_LABEL = str(os.getenv('DOCKER_LABEL'))
FRONTEND_IMAGE = str(os.getenv('FRONTEND_IMAGE'))
SERVER_IMAGE = str(os.getenv('SERVER_IMAGE'))
LOG_PROXY = int(os.getenv('LOG_PROXY'))

PROXY_IMAGE = 'shopify/toxiproxy'

num_servers = int(sys.argv[1]) if len(sys.argv) > 1 else 1
scenario_args = sys.argv[2:] if len(sys.argv) > 2 else []

client = docker.from_env()

def attach_logs(container):
    def _print(name, stream):
        for line in stream:
            print(name + ": " + line.decode('utf8').strip())

    t = threading.Thread(target=_print, args=(container.name, container.attach(logs=True, stream=True)))
    t.daemon = True
    t.start()


# Remove any running container instances
def remove():
    # Remove frontend, proxy and individual servers
    try:
        containers = client.containers.list(filters={"label": DOCKER_LABEL}, all=True)
        for container in containers:
            container.remove(force=True)
    except Exception as e:
        print(e)
        pass

    # Remove the network
    try:
        nets = client.networks.list(names=[DOCKER_LABEL + "_net"])
        for net in nets:
            net.remove()
    except Exception as e:
        print(e)
        pass


remove()

# Add the network

network = client.networks.create(DOCKER_LABEL + "_net", driver="bridge")

proxy_ports = {
    '8474': str(PROXY_PORT)
}

external_server_list = []

for server_port in range(BASE_SERVER_PORT, BASE_SERVER_PORT + num_servers):
    proxy_ports[str(server_port)] = str(server_port)
    external_server_list.append("127.0.0.1:" + str(server_port))

external_server_list = ",".join(external_server_list)
proxy_container = client.containers.run(PROXY_IMAGE,
                                        detach=True,
                                        labels={DOCKER_LABEL: 'proxy'},
                                        name=DOCKER_LABEL + '_proxy',
                                        hostname='proxy',
                                        ports=proxy_ports,
                                        environment={
                                            "LOG_LEVEL": "error"
                                        }
                                        )

if LOG_PROXY:
    attach_logs(proxy_container)

network.connect(proxy_container, aliases=['proxy'])

frontend_container = client.containers.run(FRONTEND_IMAGE,
                                           detach=True,
                                           labels={DOCKER_LABEL: 'frontend'},
                                           name=DOCKER_LABEL + '_frontend',
                                           hostname='frontend',
                                           ports={'80': FRONTEND_PORT},
                                           environment={
                                               "SERVER_LIST": external_server_list,
                                               "GROUP_NAME": GROUP_NAME
                                           }
                                           )
attach_logs(frontend_container)

# A dictionary that contains the port mapping (from, to) -> port
conn_pair_ports = {}
port = BASE_SERVER_PORT + num_servers  # the first num_servers are direct proxies that we do not target

for f in range(0, num_servers):
    for t in range(0, num_servers):
        conn_pair_ports[(f, t)] = port
        port += 1


def get_server_list_str(from_server_id):
    sl = []
    for b in range(0, num_servers):
        sl.append("proxy:" + str(conn_pair_ports[(from_server_id, b)]))
    return ",".join(sl)


server_containers = []

for server_id in range(0, num_servers):
    server_name = "server_{}".format(server_id)
    server_container = client.containers.run(SERVER_IMAGE,
                                             detach=True,
                                             labels={DOCKER_LABEL: 'server'},
                                             name=DOCKER_LABEL + '_' + server_name,
                                             hostname=server_name,
                                             environment={
                                                 "SERVER_LIST": get_server_list_str(server_id),
                                                 "SERVER_ID": server_id
                                             }
                                             )
    attach_logs(server_container)
    server_containers.append(server_container)
    network.connect(server_container, aliases=[server_name])

# Create proxies

# Create external proxies as well
for server_id in range(0, num_servers):
    to_server_name = "server_{}".format(server_id)
    server_port = BASE_SERVER_PORT + server_id

    data = {'listen': "0.0.0.0:" + str(server_port), 'upstream': to_server_name + ":80",
            'name': "ext_" + to_server_name}
    ret = requests.post('http://127.0.0.1:' + str(PROXY_PORT) + '/proxies', data=json.dumps(data).encode("utf-8"))

conn_pair_proxies_names = {}
conn_pair_proxies_data = {}
for (f, t) in conn_pair_ports:
    from_server_name = "server_{}".format(f)
    to_server_name = "server_{}".format(t)
    p = conn_pair_ports[(f, t)]

    name = from_server_name + "_to_" + to_server_name
    data = {'listen': "0.0.0.0:" + str(p), 'upstream': to_server_name + ":80", 'name': name}
    conn_pair_proxies_names[(f, t)] = name
    conn_pair_proxies_data[(f, t)] = data

    ret = requests.post('http://127.0.0.1:' + str(PROXY_PORT) + '/proxies', data=json.dumps(data).encode("utf-8"))


def print_proxies():
    res = requests.get('http://127.0.0.1:' + str(PROXY_PORT) + '/proxies')
    print(res.json())


# Some scenarios
def clear():
    requests.post('http://127.0.0.1:' + str(PROXY_PORT) + '/reset')


def add_partition(num_partitions=2):
    for (f, t) in conn_pair_ports:
        # if they are not in the same "half" we disable their connections
        # note that this still allows connections to itself and symmetrically disables (t,f)
        if (f - t) % num_partitions != 0:
            data = conn_pair_proxies_data[(f, t)]
            data['enabled'] = False
            requests.post('http://127.0.0.1:' + str(PROXY_PORT) + '/proxies/' + conn_pair_proxies_names[(t, f)], json=data)

def remove_partition():
    for (f, t) in conn_pair_ports:
        # if they are not in the same "half" we disable their connections
        # note that this still allows connections to itself and symmetrically disables (t,f)
        data = conn_pair_proxies_data[(f, t)]
        data['enabled'] = True
        requests.post('http://127.0.0.1:' + str(PROXY_PORT) + '/proxies/' + conn_pair_proxies_names[(t, f)], json=data)


def add_loss(direction='upstream', p=0.1):
    for (f, t) in conn_pair_ports:
        if f != t:
            data = {
                'type': 'limit_data',
                'stream': direction,
                'toxicity': p,
                'attributes': {
                    'bytes': 0
                }
            }
            res = requests.post(
                'http://127.0.0.1:' + str(PROXY_PORT) + '/proxies/' + conn_pair_proxies_names[(t, f)] + '/toxics',
                json=data)


def add_request_loss(p=0.1):
    add_loss('upstream', p)


def add_response_loss(p=0.1):
    add_loss('downstream', p)


def add_latency(direction='upstream', delay_ms=1000, jitter_ms=500):
    for (f, t) in conn_pair_ports:
        if f != t:
            data = {
                'type': 'latency',
                'stream': direction,
                'toxicity': 1.0,
                'attributes': {
                    'latency': delay_ms,
                    'jitter': jitter_ms,
                }
            }
            res = requests.post(
                'http://127.0.0.1:' + str(PROXY_PORT) + '/proxies/' + conn_pair_proxies_names[(t, f)] + '/toxics',
                json=data)


def add_request_latency(delay_ms=1000, jitter_ms=500):
    add_latency('upstream', delay_ms, jitter_ms)


def add_response_latency(delay_ms=1000, jitter_ms=500):
    add_latency('downstream', delay_ms, jitter_ms)


def add_bandwidth(direction='upstream', rate_kb=1000):
    for (f, t) in conn_pair_ports:
        if f != t:
            data = {
                'type': 'bandwidth',
                'stream': direction,
                'toxicity': 1.0,
                'attributes': {
                    'rate': rate_kb
                }
            }

            res = requests.post(
                'http://127.0.0.1:' + str(PROXY_PORT) + '/proxies/' + conn_pair_proxies_names[(t, f)] + '/toxics',
                json=data)


def add_request_bandwidth(rate_kb=1000):
    add_bandwidth('upstream', rate_kb)

def add_response_bandwidth(rate_kb=1000):
    add_bandwidth('downstream', rate_kb)


def add_timeout(p=0.1, timeout_ms=60000):
    for (f, t) in conn_pair_ports:
        if f != t:
            data = {
                'type': 'timeout',
                'stream': 'upstream',
                'toxicity': p,
                'attributes': {
                    'timeout': timeout_ms
                }
            }
            res = requests.post(
                'http://127.0.0.1:' + str(PROXY_PORT) + '/proxies/' + conn_pair_proxies_names[(t, f)] + '/toxics',
                json=data)


# Unrealistic conditions, no loss, no timeouts, reorderings unlikely
def scenario_perfect(p=0.2):
    clear()


# Requests might be lost entirely
def scenario_easy(p=0.2):
    scenario_perfect()
    add_request_loss(p)

# We have latencies on the request side, reorderings likely, requests might be lost
def scenario_medium(p=0.2):
    scenario_easy(p)
    add_request_bandwidth()
    add_response_bandwidth()
    add_request_latency()

# We have latencies on both sides, reorderings likely, requests and responses might be lost, bandwidths are limited
def scenario_hard(p=0.2):
    scenario_medium(p)

    add_response_loss(p)
    add_response_latency()

    add_request_bandwidth()
    add_response_bandwidth()

# Define Partitioned scenarios
def scenario_perfect_partitioned(p=0.2, num_partitions=2):
    scenario_perfect(p)
    add_partition(num_partitions=num_partitions)

def scenario_easy_partitioned(p=0.2, num_partitions=2):
    scenario_easy(p)
    add_partition(num_partitions=num_partitions)

def scenario_medium_partitioned(p=0.2, num_partitions=2):
    scenario_medium(p)
    add_partition(num_partitions=num_partitions)

def scenario_hard_partitioned(p=0.2, num_partitions=2):
    scenario_hard(p)
    add_partition(num_partitions=num_partitions)

scenarios = {
    "perfect": scenario_perfect,
    "easy": scenario_easy,
    "medium": scenario_medium,
    "hard": scenario_hard,
    "perfect_partitioned": scenario_perfect_partitioned,
    "easy_partitioned": scenario_easy_partitioned,
    "medium_partitioned": scenario_medium_partitioned,
    "hard_partitioned": scenario_hard_partitioned,
}

def extract_scenarios_with_timeouts(scenario_args):
    scs = []

    while len(scenario_args) > 0:
        if len(scenario_args) == 1:
            scs.append((scenario_args[0], None))
            break
        else:
            scs.append((scenario_args[0], int(scenario_args[1])))
            scenario_args = scenario_args[2:]

    # we always add the perfect scenario with no timeout in the end
    scs.append(('perfect', None))
    return scs


run_scenarios = extract_scenarios_with_timeouts(scenario_args)


for (s, t) in run_scenarios:
    if t:
        print("Running scenario {} for {} seconds".format(s, t))
    else:
        print("Running scenario {} forever".format(s, t))

print("CTRL-C to shutdown...")
try:
    current_scenario = None
    for (s, t) in run_scenarios:

        if s not in scenarios:
            print("Scenario {} not found!".format(s))
            continue

        if current_scenario is None or s != current_scenario:
            print("Welcome to the {} scenario".format(s))
            # we remove existing partitions
            remove_partition()
            scenarios[s]()
            current_scenario = s

        if t is not None:
            timeout_ts = datetime.datetime.now() + datetime.timedelta(seconds=t)
        else:
            timeout_ts = None

        if timeout_ts is not None:
            while timeout_ts >= datetime.datetime.now():
                time.sleep(0.1)

    # extract scenarios from stdin after iterating through all argument scenarios
    for line in sys.stdin:
        s = line.rstrip('\n')

        if s not in scenarios:
            print("Scenario {} not found!".format(s))
            continue

        if current_scenario is None or s != current_scenario:
            print("Welcome to the {} scenario".format(s))
            # we remove existing partitions
            remove_partition()
            scenarios[s]()
            current_scenario = s


except KeyboardInterrupt:
    pass

print("Shutting down...")
remove()
print("Finished")