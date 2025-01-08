# coding=utf-8
import queue

from bottle import Bottle, request, HTTPError, run, response

from paste import httpserver

import threading
import os
import time
import json
import hashlib
import uuid
import requests

from blockchain import Blockchain

class Transaction:
    def __init__(self, entry_id: str, method='add', entry_value=None):
        self.entry_id = entry_id
        self.method = method
        self.entry_value = entry_value

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "method": self.method,
            "entry_value": self.entry_value
        }

    def from_dict(data: dict):
        return Transaction(data['entry_id'], data['method'], data['entry_value'])

    def __hash__(self):
        return hash(self.to_dict())

class Entry:
    def __init__(self, id, value):
        self.id = id
        self.value = value

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "value": self.value
        }

    def from_dict(data: dict):
        return Entry(data['id'], data['value'])

    def __str__(self):
        return str(self.to_dict())

# this is only used for Ricart and Agrawala now!
class TimeStamp:
    def __init__(self, lamport_timestamp: int, tie_breaker = None):
        self.lamport_timestamp = lamport_timestamp
        self.tie_breaker = tie_breaker

    def __lt__(self, other):
        if (self.lamport_timestamp < other.lamport_timestamp):
            return True

        if (other.lamport_timestamp < self.lamport_timestamp):
            return False

        if (self.tie_breaker < other.tie_breaker):
            return True

    def from_list(entries : list):
        return TimeStamp(entries[0], entries[1])

    def to_list(self) -> list:
        return [self.lamport_timestamp, self.tie_breaker]

# ------------------------------------------------------------------------------------------------------
# You need to synchronize the access to the board when you use multithreading in the server (e.g. using a Lock)
class Board():

    def __init__(self):
        self.indexed_entries = {}

    def apply_transaction(self, transaction):
        # TODO: Implement me
        # just apply the transaction without regarding timestamps
        # this means: ignore deletion if an entry exists, just add the entry if it does not exist (even if it got deleted before!)
        transaction_method = transaction['method']
        print(f'received transaction: {transaction}')
        if transaction_method == 'add':
            self.indexed_entries[transaction['entry_id']] = Entry(transaction['entry_id'], transaction['entry_value'])
        elif transaction_method == 'modify':
            self.indexed_entries[transaction['entry_id']] = Entry(transaction['entry_id'], transaction['entry_value'])
        elif transaction_method == 'delete':
            del self.indexed_entries[transaction['entry_id']]

    # relevant for Optional tasks
    def reset_state(self, transactions=None):
        # first we reset our state
        self.indexed_entries = {}

        if transactions is not None:
            # then we apply all transactions in their given order
            for transaction in transactions:
                self.apply_transaction(transaction)

    def get_ordered_entries(self):
        ordered_indices = sorted(list(self.indexed_entries.keys()))
        return [self.indexed_entries[k] for k in ordered_indices]

# ------------------------------------------------------------------------------------------------------
class Server(Bottle):

    def __init__(self, ID, IP, server_list):
        super(Server, self).__init__()
        self.id = int(ID)
        self.ip = str(IP)
        self.server_list = server_list

        self.status = {
            "crashed": False,
            "notes": "",
            "num_entries": 0, # TODO: Use lab 2 solution to generate unique ids
            "clock": 0, # the lamport timestamp!
            'left_cs': True,        # set to true by default, changes when requests sent, changes again after cs has been executed (triggering cs_repl_worker)
            'reply_count': 0,
            'waiting': False
        }

        self.lock = threading.RLock()  # use reentry lock for the server

        # Handle CORS
        self.route('/<:re:.*>', method='OPTIONS', callback=self.add_cors_headers)
        self.add_hook('after_request', self.add_cors_headers)

        # Those two http calls simulate crashes, i.e., unavailability of the server
        self.post('/crash', callback=self.crash_request)
        self.post('/recover', callback=self.recover_request)
        self.get('/status', callback=self.status_request)

        # Define REST URIs for the frontend (note that we define multiple update and delete routes right now)
        self.post('/entries', callback=self.create_entry_request)
        self.get('/entries', callback=self.list_entries_request)
        self.post('/entries/<entry_id>', callback=self.update_entry_request)
        self.post('/entries/<entry_id>/delete', callback=self.delete_entry_request)

        # REST URIs for our algorithms
        self.post('/message', callback=self.message_request)

        self.board = Board()

        self.denied_requests = []

        self.out_queues = {}    # only for transactions, not for replies/requests
        self.out_threads = {}
        for srv_ip in self.server_list:
            self.out_queues[srv_ip] = queue.Queue()
            self.out_threads[srv_ip] = threading.Thread(target=self.out_worker, daemon=True, args=(srv_ip,)).start()

        self.cs_req_queues = {}
        self.cs_req_threads = {}
        for srv_ip in self.server_list:
            self.cs_req_queues[srv_ip] = queue.Queue()
            self.cs_req_threads[srv_ip] = threading.Thread(target=self.cs_req_worker, daemon=True, args=(srv_ip,)).start()
        
        self.cs_repl_queues = {}
        self.cs_repl_threads = {}
        for srv_ip in self.server_list:
            self.cs_repl_queues[srv_ip] = queue.Queue()
            self.cs_repl_threads[srv_ip] = threading.Thread(target=self.cs_repl_worker, daemon=True, args=(srv_ip,)).start()

        self.cs_queue = queue.Queue()

        self.blockchain = Blockchain() # only relevant for optional task

    # Please try to avoid modifying the following methods
    # ------------------------------------------------------------------------------------------------------
    def add_cors_headers(self):
        """
        You need to add some headers to each request.
        Don't use the wildcard '*' for Access-Control-Allow-Origin in production.
        """
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'PUT, GET, POST, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

    def list_entries_request(self):
        # DONT use me for server to server stuff as this is also available when crashed. Please implement another method for that (which also handles the crashed state!)
        try:

            with self.lock:
                ordered_entries = self.board.get_ordered_entries()
                dict_entries = list(map(lambda entry: entry.to_dict(), ordered_entries))

                return {
                    "entries": dict_entries,
                    "server_status": {
                        "len": len(ordered_entries),
                        "hash": hashlib.sha256((json.dumps(tuple(dict_entries)).encode('utf-8'))).hexdigest(),
                        "crashed": self.status["crashed"],
                        "notes": self.status["notes"],
                        "clock": self.status["clock"]
                    }  # we piggyback here allowing for a simple frontend implementation
                }
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def status_request(self):
        # DONT use me for server to server stuff as this is also available when crashed. Please implement another method for that (which also handles the crashed state!)
        try:

            with self.lock:
                ordered_entries = self.board.get_ordered_entries()
                dict_entries = list(map(lambda entry: entry.to_dict(), ordered_entries))
                return {
                    "len": len(ordered_entries),
                    "hash": hashlib.sha256((json.dumps(tuple(dict_entries)).encode('utf-8'))).hexdigest(),
                    "crashed": self.status["crashed"],
                    "notes": self.status["notes"],
                    "clock": self.status["clock"]
                }
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def crash_request(self):
        try:
            if not self.status["crashed"]:
                self.status["crashed"] = True
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def recover_request(self):
        try:
            if self.status["crashed"]:
                self.status["crashed"] = False
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    # This route is called whenever there is a new message for this server, you should handle everything in self.handle_message
    def message_request(self):
        try:
            if self.status["crashed"]:
                # we ignore this message
                response.status = 408
                return None
            try:
                # Please modify handle_message to return a response
                return self.handle_message(request.json)
            except Exception as e:
                print("[ERROR] " + str(e))
                return None
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    # This method sends a message to another server
    # Note that it will not send a message when the server is crashed
    # Do not modify this method if not necessary
    def _send_message(self, srv_ip, message):
        if self.status["crashed"]:
            return False  # when we are crashed we do not send messages

        success = False
        data = None
        res = None

        # We handle data string as json for now
        # We always POST this message
        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
        try:
            res = requests.post('http://{}/message'.format(srv_ip), data=json.dumps(message), headers=headers,
                                timeout=1)  # timeout should stay at 1 sec

            # result can be accessed res.json()
            if res.status_code == 200:
                data = res.json()
            if res.status_code == 200 or res.status_code == 204:
                success = True
        except Exception as e:
            print("[ERROR] " + str(e))

        return (success, data, res)

# You can modify the following methods as you wish (but please keep the crashed exception handling)
# ------------------------------------------------------------------------------------------------------

    def create_entry_request(self):
        try:
            if self.status["crashed"]:
                response.status = 408
                return

            entry_value = request.forms.get('value')
            with self.lock:
                self.status['clock'] += 1
            clock = self.status['clock']
            entry_id = str(uuid.uuid4())

            transaction_data = Transaction(entry_id, 'add', entry_value)
            transaction = transaction_data.to_dict()
            timestamp = TimeStamp(clock, self.id)
            self.status['waiting'] = True
            message = {'type': 'request', 'transaction': transaction, 'timestamp': timestamp.to_list(), 'clock': clock}
            print('prepared message for sending: ', message)
            message['from'] = self.id
            #msg_counter = 0
            for srv_ip, srv_queue in self.cs_req_queues.items():
                if srv_ip != self.ip:
                    #message['from'] = msg_counter
                    print(f'Adding message to queue for {srv_ip}: {message}')
                    srv_queue.put(message)
                #msg_counter += 1
            self.cs_queue.put(transaction)

            return True
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def update_entry_request(self, entry_id):
        try:
            if self.status["crashed"]:
                response.status = 408
                return

            entry_value = request.forms.get('value')
            with self.lock:
                self.status['clock'] += 1
            clock = self.status['clock']
            transaction_data = Transaction(entry_id, 'modify', entry_value)
            transaction = transaction_data.to_dict()
            timestamp = TimeStamp(clock, self.id)
            self.status['waiting'] = True
            message = {'type': 'request', 'transaction': transaction, 'timestamp': timestamp.to_list(), 'clock': clock}
            print('prepared message for sending: ', message)
            message['from'] = self.id
            #msg_counter = 0
            for srv_ip, srv_queue in self.cs_req_queues.items():
                if srv_ip != self.ip:
                    #message['from'] = msg_counter
                    print(f'Adding message to queue for {srv_ip}: {message}')
                    srv_queue.put(message)
                #msg_counter += 1
            self.cs_queue.put(transaction)

            return True
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def delete_entry_request(self, entry_id):
        try:
            if self.status["crashed"]:
                response.status = 408
                return
            with self.lock:
                self.status['clock'] += 1
            clock = self.status['clock']

            transaction_data = Transaction(entry_id, 'delete', entry_value=None)
            transaction = transaction_data.to_dict()
            timestamp = TimeStamp(clock, self.id)
            self.status['waiting'] = True
            message = {'type': 'request', 'transaction': transaction, 'timestamp': timestamp.to_list(), 'clock': clock}
            print('prepared message for sending: ', message)
            message['from'] = self.id
            #msg_counter = 0
            for srv_ip, srv_queue in self.cs_req_queues.items():
                if srv_ip != self.ip:
                    #message['from'] = msg_counter
                    print(f'Adding message to queue for {srv_ip}: {message}')
                    srv_queue.put(message)
                #msg_counter += 1
            self.cs_queue.put(transaction)

            return True

            return {}
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def send_message(self, srv_ip, message):
        while True:
            # TODO: add the newest clock value to the message
            message['clock'] = max(self.status['clock'], message['clock'])
            success, data, res = self._send_message(srv_ip, message)
            if success:
                break
            else:
                print("Failed to send message to server: ", srv_ip)
                time.sleep(0.1)

    def out_worker(self, srv_ip):
        while True:
            msg = self.out_queues[srv_ip].get()
            self.send_message(srv_ip, msg)
            self.out_queues[srv_ip].task_done()

    def cs_req_worker(self, srv_ip):
        while True:
            try:
                msg = self.cs_req_queues[srv_ip].get()
                print(f'cs_req_worker processing message for {srv_ip}: {msg}')
                self.send_message(srv_ip, msg)
                self.cs_req_queues[srv_ip].task_done()
                print('sent a message to: ',srv_ip)
            except Exception as e:
                print(f'Error in cs_req_worker for {srv_ip}: {e}')
    
    def cs_repl_worker(self, srv_ip):
        #while self.status['left_cs']:
            #if not queue.Empty:
        while True:
            if not self.cs_repl_queues[srv_ip].empty():
                try:
                    msg = self.cs_repl_queues[srv_ip].get()
                    self.send_message(srv_ip, msg)
                    self.cs_repl_queues[srv_ip].task_done()
                except Exception as e:
                    print(f'Error in cs_repl_worker for {srv_ip}: {e}')

    # This method is called for every message received
    def handle_message(self, message):
        # Note that you might need to use the lock
        with self.lock:
            self.status['clock'] += 1
            print("Received message: ", message)
            self.status['clock'] = max(message['clock'], self.status['clock'])
        timestamp = TimeStamp(self.status['clock'],self.id)
        message_type = message['type']
        received_timestamp = TimeStamp.from_list(message['timestamp'])
        
        if message_type == 'request':
            print(f'received_timestamp: {TimeStamp.to_list(received_timestamp)}')
            print(f'own timestamp: {TimeStamp.to_list(timestamp)}')
            if received_timestamp < timestamp or (received_timestamp == timestamp and message['timestamp'][1] < self.id) or self.status['waiting'] == False:
                print('received timestamp smaller than own timestamp')
                reply = {'type':'reply', 'timestamp':timestamp.to_list(), 'clock':self.status['clock']}
                msg_counter = 0
                msg_from = message['from']
                print(f'message from: {msg_from}')
                for srv_ip, srv_queue in self.cs_repl_queues.items():
                    if msg_counter == message['from']:
                        srv_queue.put(reply)
                        print(f'put reply out there: {reply}')
                    msg_counter += 1
            else:
                self.denied_requests.append(message)
        
        elif message_type == 'reply':
            with self.lock:
                self.status['reply_count'] += 1
                reply_count = self.status['reply_count']
                print(f'reply_count: {reply_count}')
                if self.critical_section():
                    self.status['waiting'] = False
        elif message_type == 'transaction':
            received_transaction = Transaction(message['entry_id'],message['method'],message['entry_value'])
            if received_transaction:
                transaction = Transaction.to_dict(received_transaction)
                with self.lock:
                    self.board.apply_transaction(transaction)

        # However, you might want to add this message to a queue to deal with the messages from this point onwards

        # execute the critical section when appropriate
        return {}

    def critical_section(self):
        # TOOD: Implement your critical section here (Task 2)
        # Take a transaction from the queue and propagate this one to all servers (including yourself!)
        
        if self.status['reply_count'] == len(self.server_list) -1:
            print(f'entering critical section')
            with self.lock:
                transaction = self.cs_queue.get()
                #transaction = Transaction.from_dict(message['transaction'])
                entry_id = transaction['entry_id']
                entry_value = transaction['entry_value']
                method = transaction['method']
                self.board.apply_transaction(transaction)
                timestamp = TimeStamp(self.status['clock'], self.id).to_list()
                prop_message = {'type': 'transaction', 'method': method, 'entry_id': entry_id, 'entry_value': entry_value, 'clock': self.status['clock'], 'timestamp':timestamp}
                for srv_ip, srv_queue in self.out_queues.items():
                        if srv_ip != self.ip:
                            srv_queue.put(prop_message)
                self.cs_queue.task_done()
            self.status['reply_count'] = 0
            for denied_reply in self.denied_requests:
                msg_from = denied_reply['from']
                msg_counter = 0
                for srv_ip, srv_queue in self.cs_repl_queues.items():
                    if msg_counter == denied_reply['from']:
                        srv_queue.put(denied_reply)
                    msg_counter += 1
                #self.cs_repl_queues[denied_reply].put(denied_reply)
            return True
        else:
            return False




# Sleep a bit to allow logging to be attached
time.sleep(2)

# the server_list contains all server ips of the distributed blackboard
server_list = os.getenv('SERVER_LIST').split(',')
own_id = int(os.getenv('SERVER_ID'))
own_ip = server_list[own_id]

server = Server(own_id, own_ip, server_list)

NUM_THREADS = 10
print("#### Starting Server {} with {} threads".format(str(own_id), NUM_THREADS))
httpserver.serve(server, host='0.0.0.0', port=80, threadpool_workers=NUM_THREADS,
                 threadpool_options={"spawn_if_under": NUM_THREADS})
