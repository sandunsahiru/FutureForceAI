# ai-backend/Dockerfile

FROM python:3.10-slim

# Create working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy your .env so python-dotenv can load it at runtime
COPY .env .env

# Copy the rest of your code, including main.py, interviewprep.py, etc.
COPY . .

# (Optional) Set environment variables if you want to override or confirm them here
# ENV GOOGLE_APPLICATION_CREDENTIALS="/app/answer-assistant-447812-c21040a967db.json"
# ENV JWT_SECRET="..."

# Expose port 8000
EXPOSE 8000

# Run Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]