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
        return sorted(entries)

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
                entry_id = self.status['num_entries']
                entry = Entry(entry_id, entry_value, create_ts=self.clock.copy())
                self.board.add_entry(entry)
                # TODO: Propagate the entry to all other servers?! (based on your Lab 2 solution)
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
                # TODO: Handle with vector clocks

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
                # TODO: Handle with vector clocks

            return {}
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

    def send_message(self, srv_ip, message):
        # TODO: Implement your custom code here, use your solution to lab 1 to send messages between servers reliably
        # - What if the request gets lost?
        # - What if the request is delayed?
        # - What if the response gets lost?
        return self._send_message(srv_ip, message)


    # This method is called for every message received
    def handle_message(self, message):
        # Note that you might need to use the lock
        print("Received message: ", message)

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