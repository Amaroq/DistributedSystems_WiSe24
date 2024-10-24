# coding=utf-8
from bottle import Bottle, request, HTTPError, run, response

from paste import httpserver

import threading
import os
import time
import json
import hashlib


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
        self.indexed_entries = {}

    def add_entry(self, entry):
        self.indexed_entries[entry.id] = entry

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
            "num_entries": 0,
        }

        self.lock = threading.RLock() #use reentry lock for the server

        # Handle CORS
        self.route('/<:re:.*>', method='OPTIONS', callback=self.add_cors_headers)
        self.add_hook('after_request', self.add_cors_headers)

        # Those two http calls simulate crashes, i.e., unavailability of the server
        self.post('/crash', callback=self.crash_request)
        self.post('/recover', callback=self.recover_request)

        # Define REST URIs for the frontend (note that we define multiple update and delete routes right now)
        self.post('/entries', callback=self.create_entry_request)
        self.get('/entries', callback=self.list_entries_request)
        self.put('/entries/<entry_id>', callback=self.update_entry_request)
        self.delete('/entries/<entry_id>', callback=self.delete_entry_request)

        # REST URIs for the later algorithms
        self.post('/message', callback=self.message_request)

        self.board = Board()

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

    def create_entry_request(self):
        try:
            if self.status["crashed"]:
                response.status = 408
                return

            entry_value = request.forms.get('value')
            with self.lock:
                self.status["num_entries"] += 1

                self.board.add_entry(
                    Entry(self.status["num_entries"], entry_value)
                )

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
                pass  # not implemented atm!

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
                pass # not implemented atm!

            return {}
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

    def message_request(self):
        try:
            if self.status["crashed"]:
                # we ignore this message
                response.status = 408
                return

            return None

            # Todo: This is where we will later implement our algorithms
            # we return the result of the handle_message method
            # this allows some RPC functionality (if wanted)
            #return self.handle_message(request.json)
        except Exception as e:
            print("[ERROR] " + str(e))
            raise e

# Sleep a bit to allow logging to be attached
time.sleep(2)

# the server_list contains all server ips of the distributed blackboard
server_list = os.getenv('SERVER_LIST').split(',')
own_id = int(os.getenv('SERVER_ID'))
own_ip = server_list[own_id]

server = Server(own_id, own_ip, server_list)

NUM_THREADS = 10
print("#### Starting Server {} with {}".format(str(own_id), NUM_THREADS))
httpserver.serve(server, host='0.0.0.0', port=80, threadpool_workers=NUM_THREADS,
                 threadpool_options={"spawn_if_under": NUM_THREADS})