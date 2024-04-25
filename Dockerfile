# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt /app/

# Install the required libraries
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . /app

# Copy the config file into the container
COPY config.json /app/config.json

# Run the Python script when the container launches
CMD ["python", "plex-playlist-fix.py"]