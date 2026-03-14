# Use the official Apache Airflow image
FROM apache/airflow:2.8.1-python3.10

# Copy the requirements file into the container
COPY requirements.txt /

# Install the Python dependencies
RUN pip install --no-cache-dir -r /requirements.txt