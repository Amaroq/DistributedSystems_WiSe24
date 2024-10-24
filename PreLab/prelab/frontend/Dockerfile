FROM python:3.11-alpine


ENV GROUP_NAME="Unnamed Group"
ENV SERVER_LIST="localhost:8001,localhost:8002"
EXPOSE 80


RUN pip install bottle requests paste

COPY src /application/src
COPY frontend.py /application

WORKDIR /application

CMD ["python", "-u", "./frontend.py"]

