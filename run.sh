#!/bin/bash
echo "Starting music server"
# If there is no virtual environment, create one
if [ ! -d "./venv" ]
then
    echo "Creating virtual environment"
    python3 -m venv venv
fi

echo "Installing requirements"
./venv/bin/python3 -m pip install -r requirements.txt > /dev/null

# Check if ffmpeg is installed by checking if 'which ffmpeg' returns a path
if ! which ffmpeg > /dev/null
then
    echo "ffmpeg could not be found"
    # If we are on a debian based system, install it
    if [ -f "/etc/debian_version" ]
    then
        echo "Installing ffmpeg"
        sudo apt-get install ffmpeg -y > /dev/null
    else
        echo "Please install ffmpeg and try again"
        exit
    fi
fi

# Run the program
./venv/bin/python3 ./src/main.py

