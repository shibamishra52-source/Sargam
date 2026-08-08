FROM python:3.9-slim
RUN apt update && apt upgrade -y
RUN apt install -y git curl python3-pip ffmpeg
RUN pip3 install --upgrade pip
COPY . /app
WORKDIR /app
RUN pip3 install -r requirements.txt
CMD ["python3", "main.py"]
