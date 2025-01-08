# Distributed Systems Labs: Frontend


### Building the Image:

Execute in the project's root directory:
```commandline
docker build -t ds_labs_frontend frontend
```

### Starting the Frontend

To start the frontend (including port mapping):

```commandline
docker run -p 127.0.0.1:8000:80 ds_labs_frontend
```

The frontend should then be available at http://localhost:8000/
