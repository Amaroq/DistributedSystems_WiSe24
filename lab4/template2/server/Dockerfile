FROM python:3.11-alpine
WORKDIR /application

ENV SERVER_LIST="localhost:80"
ENV SERVER_ID="0"

RUN pip install bottle requests paste

COPY ./*.py /application/

CMD ["python", "-u", "./server.py"]