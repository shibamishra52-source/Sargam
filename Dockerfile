FROM python:3.10-slim
RUN apt update && apt upgrade -y
RUN apt install -y git curl python3-pip ffmpeg
RUN pip3 install --upgrade pip
