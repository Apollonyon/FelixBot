# 1. Use a lightweight Python version
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Install system dependencies (FFmpeg is CRITICAL for music)
# We also install git/gcc just in case some python libs need to compile stuff
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy requirements and install Python libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your bot code
COPY . .

# 6. Command to run the bot
CMD ["python", "main.py"]
