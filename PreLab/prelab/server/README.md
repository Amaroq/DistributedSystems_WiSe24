# Distributed Systems Labs: Server


### Building the Image:

Execute in the project's root directory:
```commandline
docker build -t ds_labs_server server
```

### Starting the server

To start the server (including port mapping):

```commandline
docker run -p 127.0.0.1:8001:80 ds_labs_server
```

The server's api should then be available at http://localhost:8001/.
You should be able to reach it via http://localhost:8001/entries
