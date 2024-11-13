#### Task 3
#### a)
Because ids are generated at every individual server, if messages arrive in a different order, the same entry will be saved with different ids.

#### b)
Since the coordinator sends every message to every server exactly once, whenever messages do not arrive at all, entries will be saved in one server and not another.

#### c)
Because ids are generated at every individual server, if messages arrive more than once, they will also be saved more than once in that server.

#### Solutions:
#### a) and c)
To avoid both different ids for the same entry and saving entries more than once with different ids, the coordinator generates one id for an entry and includes it in the propagation message.

```python
# critical section start
                with self.lock:
                    entry_id = self.status['num_entries'] + 1 # coordinator generated id which is sent to all servers
                # critical section end
```


#### b)
To prevent messages from not arriving, check if the message was sent successfully (and in case it was not, send it again)
```python
def send_message(self, srv_ip, message):
    res = self._send_message(srv_ip, message)
            while (res[0] != True):
                res = self.send_message(srv_ip, message)        
            return res
```

#### Task 4
To handle delayed and lost requests messages are re-sent until successful. To avoid saving entries in repeated add_entry-messages more than once, 
they are send with an additional id and the server-id they are sent from
```python
with self.lock:
                    create_entry_id = self.status['num_entries'] + 1

            self.send_message(self.server_list[0], {'type': 'add_entry', 'entry_value': entry_value, 'create_entry_id': create_entry_id, 'from_server': self.id})
```
The coordinator saves these ids on an individual list for each server and compares them to the ids of incoming add_entry-messages to avoid propagating the same entry more than once.
```python
if type == 'add_entry':

                assert self.id == 0 # ID 0 is coordinator only this server should receive add_entry messages right now
                if self.status['num_entries'] == 0:
                    self.status['create_entry_ids'] = [[] for x in range(len(self.server_list))] # initialize with one empty list per server
                
                entry_value = message['entry_value']
                # critical section start
                with self.lock:
                    entry_id = self.status['num_entries'] + 1 # coordinator generated id which is sent to all servers
                # critical section end
                create_entry_id = message['create_entry_id']
                from_server = message['from_server']
                # We can safely propagate here since we always have a single frontend client, right? So no need to lock, right? Right?!
                if create_entry_id not in self.status['create_entry_ids'][from_server]: # check if message is doublicate
                    self.status['create_entry_ids'][from_server].append(create_entry_id)
                    for other in self.server_list:
                        # TODO: Send message to other servers concurrently?
                        self.send_message(other, {'type': 'propagate', 'entry_value': entry_value, 'entry_id': entry_id})
```

Because the messages are re-sent until successfully received, a server (not the coordinator) can recover after a crash.
While FIFO is not guaranteed in this approach, there is still consistency due to the checking of ids to identify duplicates and to varify that the messages have been successfully sent.