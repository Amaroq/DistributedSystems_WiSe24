# Distributed Systems Labs

## Setup

The .env file contains some customizable options.
Install requirements:

```bash
pip3 install -r requirements.txt
```

## Build

```bash
docker build -t ds_labs_server server -f server/Dockerfile && docker build -t ds_labs_frontend frontend -f frontend/Dockerfile
```

## Run

```bash
python3 labs.py <num-servers> <scenario> <scenario timeout (s)>
```

Once all services are started, the frontend should be reachable at the configured FRONTEND_PORT, e.g.: [localhost:8000](http://localhost:8000)

Alternatively, you can also use labs_control.py to interact with the scenario. See `test.py` for an example. You can run this using:

```bash
python3 test.py
```




You can rebuild and restart everything using:

```commandline
docker build -t ds_labs_server server && python3 labs.py <num_servers> <scenario> <scenario_timeout> <scenario> <scenario_timeout> <scenario> <scenario_timeout>
```

## Using Docker Compose

If you encounter problems using the python variant, you can execute a static version with 4 servers using docker compose as
follows (note that this one does only provide the perfect world scenario).

```commandline
docker compose up --build
```