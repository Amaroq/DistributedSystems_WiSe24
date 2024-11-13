# coding=utf-8
from bottle import Bottle, request, HTTPError, run, response

from paste import httpserver

import threading
import os
import time
import json
import hashlib

import requests
import functools

# A simple entry in our board
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

# ------------------------------------------------------------------------------------------------------
# You need to synchronize the access to the board when you use multithreading in the server (e.g. using a Lock)
class Board():

    def __init__(self):
        self.indexed_entries = {} # indexed_entries is defined on initialization

    def add_entry(self, entry):                 # entry is passed to function
        self.indexed_entries[entry.id] = entry  # entry is added to board's own indexed_entry list by id

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
            "num_entries": 0, # we use this to generate ids for the entries
        }

        self.lock = threading.RLock() # use reentry lock for the server

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
        self.put('/entries/<entry_id>', callback=self.update_entry_request)     
        self.delete('/entries/<entry_id>', callback=self.delete_entry_request)

        # REST URIs for the later algorithms
        self.post('/message', callback=self.message_request)                # a new message request is sent to server

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
                        "notes": self.status["notes"]
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
                    "notes": self.status["notes"]
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
    # is called whenever 
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

# You can modify the following methods as you wish
# ------------------------------------------------------------------------------------------------------

    def create_entry_request(self):
        try:
            if self.status["crashed"]:
                response.status = 408
                return

            entry_value = request.forms.get('value')
            with self.lock:
                    create_entry_id = self.status['num_entries'] + 1

            self.send_message(self.server_list[0], {'type': 'add_entry', 'entry_value': entry_value, 'create_entry_id': create_entry_id, 'from_server': self.id})

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
                # TODO: not implemented atm!
            return {}
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def delete_entry_request(self, entry_id):
        try:
            if self.status["crashed"]:
                response.status = 408
                return

            with self.lock:
                print("Deleting entry with id {}".format(entry_id))
                # TODO: not implemented atm!

            return {}
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e



    def send_message(self, srv_ip, message):
        # TODO: Implement your custom code here
        # - What if the request gets lost? (Task 3)
        # - What if the request is delayed? (Task 3)
        # - What if the response gets lost? (optional)
        
        res = self._send_message(srv_ip, message)
        # if message not sent successfully, send again (Task 3b)
        #while (res[0] != True) and (message['type'] == 'propagate'): # check only for propagate
        #if (res[0] != True) and (message['type'] == 'propagate'): # check only for propagate
            #print("send again: ", message)
        while (res[0] != True):
            res = self.send_message(srv_ip, message)
        #if (res[0] == False) and (message['type'] == 'add_entry'): # type add_entry
        #    print("send again add_entry: ", message)
        #    return self.send_message(srv_ip, message)
        
        return res

    # This method is called whenever a message is received
    # Note that this function call will block one of the NUM_THREADS threads that handle the web server
    # so if you intend to block for a long time, you should spawn a new thread, for example (but be careful with locking)
    # We provide a basic implementation for the coordinator:
    #   - If a server wants to add a new entry, it will send an 'add_entry' message to the coordinator
    #   - The coordinator will propagate it to all other servers (including itself)
    #   - If a server receives a 'propagate' message, it will add the entry to the board
    def handle_message(self, message):
        # Note that you might need to use the lock
        # Task 3a
        print("Received message: ", message)

        if 'type' in message:
            type = message['type']

            if type == 'add_entry':

                assert self.id == 0 # ID 0 is coordinator only this server should receive add_entry messages right now
                if self.status['num_entries'] == 0:
                    self.status['create_entry_ids'] = [[] for x in range(len(self.server_list))] # initialize with one empty list per server
                
                entry_value = message['entry_value']
                entry_id = self.status['num_entries'] + 1
                create_entry_id = message['create_entry_id']
                from_server = message['from_server']
                #with self.lock:
                #    entry_id = self.status['num_entries'] + 1 # coordinator generated id which is sent to all servers

                # We can safely propagate here since we always have a single frontend client, right? So no need to lock, right? Right?!
                if create_entry_id not in self.status['create_entry_ids'][from_server]: # check if message is doublicate
                    self.status['create_entry_ids'][from_server].append(create_entry_id)
                    for other in self.server_list:
                        # TODO: Send message to other servers concurrently?
                        self.send_message(other, {'type': 'propagate', 'entry_value': entry_value, 'entry_id': entry_id})

            elif type == 'propagate':
                entry_value = message['entry_value']
                entry_id = message['entry_id'] # get id from coordinator
                # Let's hope this is from the coordinator
                with self.lock:
                    #if entry_id not in self.board.indexed_entries.keys():
                    self.status['num_entries'] += 1
                    entry = Entry(entry_id, entry_value) # use id generated by coordinator
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

