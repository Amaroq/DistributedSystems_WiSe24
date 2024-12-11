# coding=utf-8
from bottle import Bottle, request, HTTPError, run, response

from paste import httpserver

import threading
import os
import time
import json
import hashlib
import uuid
import queue

import requests
import functools

from vector_clock import VectorClock

class Entry:
    def __init__(self, id, value, create_ts, modify_ts=None, delete_ts=None):
        self.id = id
        self.value = value
        self.create_ts = create_ts
        self.modify_ts = modify_ts
        self.delete_ts = delete_ts

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "value": self.value,
            "create_ts": self.create_ts.to_list(),
            "modify_ts": self.modify_ts.to_list() if self.modify_ts is not None else None,
            "delete_ts": self.delete_ts.to_list() if self.delete_ts is not None else None,
        }

    def from_dict(data: dict):
        return Entry(data['id'], data['value'],
                     create_ts=VectorClock.from_list(data['create_ts']),
                     modify_ts=VectorClock.from_list(data['modify_ts']) if data['modify_ts'] else None,
                     delete_ts=VectorClock.from_list(data['delete_ts']) if data['delete_ts'] else None
                 )

    def is_deleted(self):
        # deletion takes simple precedence
        return self.delete_ts is not None

    def __str__(self):
        return str(self.to_dict())

    def __lt__(self, other):
        # TODO: implement the sorting here! Please use the creation vector clock first to preserve causality and then use the entry ID as a tie-breaker,
        return False

# ------------------------------------------------------------------------------------------------------
# You need to synchronize the access to the board when you use multithreading in the server (e.g. using a Lock)
class Board():

    def __init__(self):
        self.indexed_entries = {}

    def add_entry(self, entry):
        # TODO: Check if the entry exists already and apply update
        self.indexed_entries[entry.id] = entry

    def get_ordered_entries(self):
        entries = [e for e in list(self.indexed_entries.values()) if
                   not e.is_deleted()]  # we filter out deleted items as they should not appear for the clients
        # we then return the sorted entries
        #return sorted(entries)
        
        # Task 3 sort entries based on vector clocks
        sorted_entries = sorted(entries, key=lambda x: (x.create_ts, x.id))
        return sorted_entries

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
            "num_entries": 0, # we use this to generate ids for the entries, TODO: Use lab 2 solution to generate unique ids
        }
        
        # handle outgoing messages (lab 2)
        self.queue_out = queue.Queue()
        threading.Thread(target=self.propagate, daemon=True).start()

        self.lock = threading.RLock()  # use reentry lock for the server
        self.clock = VectorClock(n=len(self.server_list))

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
                        "clock": self.clock.to_list()
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
                    "clock": self.clock.to_list()
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
                self.status['num_entries'] += 1
                #entry_id = self.status['num_entries']
                unique_id = uuid.uuid4()
                entry_id = str(unique_id)
                with self.lock:                                 # lock incrementing own clock just in case multithreaded stuff is happening
                    self.clock.increment(self.id)               # increment own clock (because an event happened)
                create_ts = create_ts=self.clock.copy()         # copy current clock value to create_ts
                entry = Entry(entry_id, entry_value, create_ts) # create new entry with create_ts
                self.board.add_entry(entry)                     # add new entry to board
                # TODO: Propagate the entry to all other servers?! (based on your Lab 2 solution)
                for other in self.server_list:
                    message = (other, {'type': 'propagate', 'entry_value': entry_value, 'entry_id': entry_id, 'timestamp': create_ts.to_list(), 'sent_from': self.id})
                    self.queue_out.put(message)
                # TODO: Handle with vector clocks (but make sure that you lock your threads for the clock access)

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
            with self.lock:
                print("Updating entry with id {} to value {}".format(entry_id, entry_value))
                entry = self.board.indexed_entries.get(entry_id)
                print(entry)
                if entry is None or entry.is_deleted():                                 # check if entry exists first
                    return {'error': 'entry does not exist or has been deleted.'}       # return error if entry doesn't exist
                self.clock.increment(self.id)                                           # increment own clock on update event
                entry.value = entry_value                                               # update entry value
                entry.modify_ts = self.clock.copy()                                     # update modify timestamp to current own clock
                #print(entry)
                for other in self.server_list:                                          # propagate to other servers
                    message = (other, {
                        'type': 'modify',
                        'entry_id': entry.id,
                        'entry_value': entry_value,
                        'timestamp': entry.modify_ts.to_list(),
                        'sent_from': self.id
                    })
                    self.queue_out.put(message)

            return {}
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def delete_entry_request(self, entry_id):
        try:
            if self.status["crashed"]:
                response.status = 408
                return
            entry = self.board.indexed_entries.get(entry_id)
            if entry is None or entry.is_deleted():                                     # check if entry exists first
                    return {'error': 'entry does not exist or has been deleted.'}       # return error if entry doesn't exist
            with self.lock:
                print("Deleting entry with id {}".format(entry_id))
                
                self.clock.increment(self.id)                           # increase own clock
                entry.delete_ts = self.clock.copy()                     # add current clock to entry as delete_ts
                self.board.add_entry(entry)                             # add updated entry to board
            
                for other in self.server_list:
                    message = (other, {
                        'type': 'delete',
                        'entry_id': entry_id,
                        'timestamp': entry.delete_ts.to_list(),
                        'sent_from': self.id
                    })
                    self.queue_out.put(message)

            return {}
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    # send propagation messages from outgoing queue (lab 2)
    def propagate(self):
        while True:
            message = self.queue_out.get()
            result = self.send_message(message[0], message[1])
            if result[0] == False:
                self.queue_out.put(message)
    
    def send_message(self, srv_ip, message):
        # TODO: Implement your custom code here, use your solution to lab 1 to send messages between servers reliably
        # - What if the request gets lost?
        # - What if the request is delayed?
        # - What if the response gets lost?
        return self._send_message(srv_ip, message)


    # This method is called for every message received (lab 2)
    def handle_message(self, message):
        # Note that you might need to use the lock
        print("Received message: ", message)
        type = message['type']
        
        # propagation message: add entry to board  Task 2
        if type == 'propagate':
                entry_value = message['entry_value']
                entry_id = message['entry_id']
                if len(message['timestamp']) == len(self.clock.to_list()):                      # check if both clocks are same length (same number of servers for both clocks)
                    entry_timestamp = VectorClock.from_list(entries = message['timestamp'])     # parse vc
                    with self.lock:                                                             # lock for incrementing
                        #entry_timestamp.increment(self.id)
                        if not self.id == message['sent_from']:
                            self.clock.increment(self.id)                                       # increment own clock
                        self.clock.update(entry_timestamp)                                      # update own clock
                        self.status['num_entries'] += 1
                        entry = Entry(entry_id, entry_value, entry_timestamp)
                        self.board.add_entry(entry)

        elif type == 'modify':
            entry_id = message['entry_id']
            modify_ts = VectorClock.from_list(entries = message['timestamp'])
            entry_value = message['entry_value']
            entry = self.board.indexed_entries.get(entry_id)
            if entry is None or entry.is_deleted():
                return {'error': 'entry does not exist or has been deleted.'}
            with self.lock:
                if not self.id == message['sent_from']:
                    self.clock.increment(self.id)
                if entry.modify_ts is None or entry.modify_ts < modify_ts:
                    self.clock.update(modify_ts)
                    entry.value = entry_value
                    entry.modify_ts = modify_ts
                    self.board.add_entry(entry)
        
        elif type == 'delete':
            entry_id = message['entry_id']
            delete_ts = VectorClock.from_list(entries = message['timestamp'])
            entry = self.board.indexed_entries.get(entry_id)
            if entry is None or entry.is_deleted():
                return {'error': 'entry does not exist or has been deleted.'}
            with self.lock:
                if not self.id == message['sent_from']:
                    self.clock.increment(self.id)                               # entry already deleted on self
                if entry.delete_ts is None or entry.delete_ts < delete_ts:
                    entry.delete_ts = delete_ts
                    self.board.add_entry(entry)

        else:
            print("Received weird message?")

        return {}

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

