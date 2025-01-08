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
        self.entry_id = entry_id                # transaction stores the id of the entry
        self.method = method                    # transaction stores the method applied, i.e. add, modify, delete
        self.entry_value = entry_value          # transaction stores the value

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

        # not really necessary, but I find it a bit easier to read
        entry_id = transaction.entry_id
        method = transaction.method
        entry_value = transaction.entry_value

        if method == 'add':
            self.indexed_entries[entry_id] = Entry(entry_id, entry_value)       # add the entry
        
        elif method == 'delete':
            if entry_id in self.indexed_entries:
                del self.indexed_entries[entry_id]                              # delete entry from indexed_entries dict
        
        elif method == 'modify':
            self.indexed_entries[entry_id] = Entry(entry_id, entry_value)       # just overwrite entry
        # optional: handle unknown methods?

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
            'cs_current_request': None,
            'reply_count': 0
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

        # task 3 additional attributes/queues
        self.cs_queue = queue.Queue()
        #self.prop_queue = queue.Queue()
        #self.reply_count = 0              # to keep track of received replies
        self.denied_replies =[]             # keep track of denied replies
        #self.cs_current_request = None      # keep track of currently executed request

        self.out_queues = {}
        self.out_threads = {}
        self.reply_queues = {}
        self.reply_threads = {}
        for srv_ip in self.server_list:
            self.out_queues[srv_ip] = queue.Queue()
            self.out_threads[srv_ip] = threading.Thread(target=self.out_worker, daemon=True, args=(srv_ip,)).start()
        
        for srv_ip in self.server_list:
            self.reply_queues[srv_ip] = queue.Queue()
            self.reply_threads[srv_ip] = threading.Thread(target=self.reply_worker, daemon=True, args=(srv_ip,)).start()

        threading.Thread(target=self.cs_worker, daemon=True).start()
        #threading.Thread(target=self.prop_worker, daemon=True).start()

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
    def request_cs(self, transaction):
        print('entering function: request_cs')
        #with self.lock:
        self.status['clock'] += 1
        timestamp = self.status['clock']
        self.status['cs_current_request'] = TimeStamp(timestamp, self.id)
        print(f"Assigned new cs_current_request with ${self.status['cs_current_request'].to_list()}")

        message = {'type': 'request', 'timestamp': self.status['cs_current_request'].to_list(), 'clock': self.status['clock']}
        for srv_ip, srv_queue in self.reply_queues.items():
            if srv_ip != self.ip:
                srv_queue.put(message)

        # wait for all servers to reply before entering critical section
        
        while self.status['reply_count'] < len(self.server_list) -1:
            # enter critical section
            print(f'Waiting for replies')
            print(f'current reply_count', self.status['reply_count'])
            time.sleep(1)
        print(f'replies receveived, entering CS')
        self.critical_section(transaction)
        #else:
         #   print(f'Error: Timeout or error received replies from other servers')
        with self.lock:
            self.status['cs_current_request'] = None
        for denied_reply in self.denied_replies:
            self.reply_queues[denied_reply].put({
                'type': 'reply',
                'timestamp': self.status['clock']
            })
        self.denied_replies.clear()

    def create_entry_request(self):
        try:
            if self.status["crashed"]:
                response.status = 408
                return

            entry_value = request.forms.get('value')

            # TODO: Create a transaction and propagate it later in the CS
            # use current logical timestamps for the transactions

            # copied from labs 2 - might need work as it now includes the timestamp + uuid solution
            timestamp = int(time.time()) # timestamp for order
            id = uuid.uuid4() # unique id
            entry_id = str(timestamp) + str(id) # entry_id is timestamp + uuid
            entry = Entry(entry_id, entry_value)
            
            # create transaction
            transaction = Transaction(entry_id, method='add', entry_value=entry_value)
            self.cs_queue.put(transaction.to_dict())

            return {}
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def update_entry_request(self, entry_id):
        try:
            if self.status["crashed"]:
                response.status = 408
                return

            entry_value = request.forms.get('value')

            # TODO: Create a transaction and propagate it later in the CS
            # use current logical timestamps for the transactions
            
            # am I dumb or is this really just the same behaviour as adding an entry
            # without generating a new id?
            transaction = Transaction(entry_id, method='modify', entry_value=entry_value)
            message = {'transaction': transaction.to_dict()}

            for srv_ip, srv_queue in self.out_queues.items():
                srv_queue.put(message)

            # not sure if necessary, but just to be sure, add locally as well
            with self.lock:
                self.board.apply_transaction(transaction)

            return {}
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def delete_entry_request(self, entry_id):
        try:
            if self.status["crashed"]:
                response.status = 408
                return

            # TODO: Create a transaction and propagate it once in the CS
            # use current logical timestamps for the transactions
            transaction = Transaction(entry_id, method='delete')
            message = {'transaction': transaction.to_dict()}

            for srv_ip, srv_queue in self.out_queues.items():
                srv_queue.put(message)
            with self.lock:
                self.board.apply_transaction(transaction)

            return {}
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def send_message(self, srv_ip, message):
        while True:
            # TODO: add the newest clock value to the message
            with self.lock:
                message['clock'] = self.status['clock']
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
    
    def reply_worker(self, srv_ip):
        while True:
            msg = self.reply_queues[srv_ip].get()
            self.send_message(srv_ip, msg)
            self.reply_queues[srv_ip].task_done()

    def cs_worker(self):
        while True:
            transaction = self.cs_queue.get()
            self.request_cs(transaction)
            self.cs_queue.task_done()

    # This method is called for every message received
    def handle_message(self, message):
        # Note that you might need to use the lock
        print("Received message: ", message, 'on', self.ip)
        if message is None:
            print("Error: Received None for message")
        else:
            # Safely access the keys
            try:
                with self.lock:
                    # Please check the message for a newer timestamp and update your clock accordingly!
                    received_clock = message.get('clock')
                    self.status['clock'] = max(self.status['clock'], received_clock) + 1

                message_type = message.get('type')
                if message_type == 'request':
                    received_timestamp = message['timestamp']
                    request_timestamp = TimeStamp.from_list(received_timestamp)
                    # Compare with cs_current_request
                    if (self.status['cs_current_request'] is None or request_timestamp < self.status['cs_current_request']):
                        # Reply immediately
                        timestamp = request_timestamp.to_list()
                        message = {'type': 'reply', 'clock': self.status['clock'], 'timestamp': timestamp}
                        for srv_ip, srv_queue in self.reply_queues.items():
                            if srv_ip != self.ip:
                                srv_queue.put(message)
                    else:
                        self.denied_replies.append(message['clock'])

                elif message_type == 'reply':
                    #print(self.cs_queue.get()['timestamp'])
                    #if message['timestamp'] == self.cs_queue.get()['timestamp']:
                        self.status['reply_count'] += 1
                elif message_type =='transaction':
                    received_transaction = message.get('transaction')
                    if received_transaction:
                        transaction = Transaction.from_dict(received_transaction)
                        self.board.apply_transaction(transaction)
                elif message_type is None:
                    print(f'[ERROR] Missing type in message')
                    return

                # However, you might want to add this message to a queue to deal with the messages from this point onwards

                # execute the critical section when appropriate
            
            except Exception as e:
                print('[ERROR] ' + str(e))

    def critical_section(self, transaction):
        # TOOD: Implement your critical section here (Task 2)
        # Take a transaction from the queue and propagate this one to all servers (including yourself!)
        print(f'Server ${self.id} entering critical section')
        try:
            #with self.lock:
                '''self.board.apply_transaction(transaction)
                print(f'Transaction applied: {transaction.to_dict()}')

                message = {'type': 'transaction', 'transaction': transaction.to_dict()}
                for srv_ip, srv_queue in self.out_queues.items():
                    if srv_ip != self.ip:  # Do not propagate to self
                        srv_queue.put(message)'''
                transaction_data = self.cs_queue.get()    # give a little headroom in case queue is empty

                #transaction_data = message.get('transaction')
                if not transaction_data:
                    self.cs_queue.task_done()
            
                # convert into transaction object
                transaction = Transaction.from_dict(transaction_data)
                with self.lock:
                    print(f'server {self.id} entering critical section')            # for monitoring purposes
                    self.board.apply_transaction(transaction)
                    print(f'server {self.id} leaving critical section')
                
                prop_message = {'transaction': transaction.to_dict(), 'clock': self.status['clock']}
                # propagate to all servers
                for srv_ip, srv_queue in self.out_queues.items():
                    if srv_ip != self.ip:
                        srv_queue.put(prop_message)

        except Exception as e:
            print(f'[ERROR] Critical section failure: {e}')
        finally:
            print(f"Server {self.id} leaving critical section")



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