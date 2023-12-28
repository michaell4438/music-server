FROM ubuntu:latest
LABEL authors="michael"

# Copy the current directory contents except config/ and playlists/ into the container at /app
COPY . /app
RUN rm -rf /app/config
RUN rm -rf /app/playlists

# Install python3 and pip3
RUN apt-get update && apt-get install -y python3 python3-pip

# Install ffmpeg
RUN apt-get install -y ffmpeg

# Install any needed packages specified in requirements.txt
RUN pip3 install --trusted-host pypi.python.org -r /app/requirements.txt

# Make port 44380 available to the world outside this container
EXPOSE 44380

# Set the working directory to /app
WORKDIR /app

# Run src/main.py when the container launches from the /app directory
CMD ["python3", "src/main.py"]