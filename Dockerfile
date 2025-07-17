# Use an official Python base image
FROM python:3.11

# Set the working directory
WORKDIR /app

# Copy app files and requirements
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the Flask app port
EXPOSE 8080

# Run the app with Gunicorn
CMD ["gunicorn", "-w", "10", "-b", "0.0.0.0:8080", "app:app"]
