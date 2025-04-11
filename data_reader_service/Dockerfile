# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any necessary dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on (default Flask port is 5000)
EXPOSE 5002

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=development

# Command to run the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=5002"]
