#pull the image from docker hub
FROM python:3.12.10-slim

#set the working directionary in container
WORKDIR /01-python-fastapi

# copy the requirements.txt to detination (containers working directory /01-python-fastapi)
COPY requirements.txt .

# installing dependencies in container
RUN pip install -r requirements.txt

# copy all the folders and files from source to destination(current directory to containers working directory)
# COPY <source> <destination>

# why do we have seperate COPY? 
# Docker runs layer by layer and it's cached.. when you run second time lets assume only main.py changed
# Layer1-->FROM python:3.12.10-slim - nochange
# Layer2-->WORKDIR /01-python-fastapi - nochange
# Layer3-->COPY requirements.txt . - nochange
# Layer4-->RUN pip install -r requirements.txt . - nochange
# Layer4-->COPY . . - changed
# only layer 4 re-runs.
# if suppose COPY . . is only one we have still it works but, it considers further layes to re-run
# Layer1-->FROM python:3.12.10-slim - nochange
# Layer2-->WORKDIR /01-python-fastapi - nochange
# Layer3-->COPY . . - changed
# Layer4-->RUN pip install -r requirements.txt . - re-run though no change
# Layer4-->COPY . . - changed
COPY . .

# just for documentation, whomever reads this docker file or run the container, 
# they should be aware that application listens on port 8000
EXPOSE 8000

# on start on container what command to execute
# --host 0.0.0.0 - when you start fastapi application ideally it listens 127.0.0.1 or localhost and cannot access outside container 
# so this application only be accessable within container, so we need to explicitly mention that any ip can reach this
# --port 8000 applications port, while running the docker run command we should explicity map the port (application port) 
# i.e docker run -p 8000:8000 01-python-fastapi
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]



