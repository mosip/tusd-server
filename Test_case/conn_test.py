# this one test case file 


from tusclient import client
import os
import time

# 1. Define your local tusd files endpoint
server_url = "http://localhost:8080/files/"

# 2. Path to a local dummy test file you want to upload
file_path = "test_telemetry.json"

# Create a dummy payload if it doesn't exist
with open(file_path, "w") as f:
    # Using time.time_ns() ensures every single payload has a 100% unique fingerprint for Vector
    f.write(f'{{"test_metric": "packet_success", "value": 100, "timestamp": {time.time_ns()}}}\n')

print(f"Starting upload of {file_path} to {server_url}...")

try:
    # 3. Initialize the tus client
    my_client = client.TusClient(server_url)

    # 4. Create the uploader instance pointing to your file
    # We pass the file_path directly instead of an open file stream for a cleaner upload call
    # with open(file_path, "rb") as f:
    #     uploader = my_client.uploader(file_stream=f, chunk_size=1024 * 1024)  # 1MB chunks
    uploader = my_client.uploader(file_path, chunk_size=2048)  # Smaller chunk size for small JSON files
    uploader.upload()

    print("✅ Upload Successfully Completed!")
    print(f"Stored Tus File URL: {uploader.url}")

except Exception as e:
    print(f"\n❌ Upload failed: {e}")