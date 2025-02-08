# Stage 1: Build stage
FROM python:3.11.10 as builder

# Copy code to the build stage
COPY . /app/code

# Set the working directory
WORKDIR /app

# Create a virtual environment and install dependencies
RUN python -m venv venv \
    && venv/bin/pip install --no-cache-dir -r code/requirements.txt -i https://mirrors.tencent.com/pypi/simple/ --extra-index-url https://mirrors.tencent.com/repository/pypi/tencent_pypi/simple

# Stage 2: Runtime stage
FROM python:3.11.10-slim as runtime

RUN apt-get update && apt-get install -y --no-install-recommends curl vim

# Copy the virtual environment and code to the runtime stage
COPY --from=builder /app/venv /app/venv
COPY --from=builder /app/code /app/code

# Set the working directory
WORKDIR /app/code

# Set Python environment variables
ENV C_FORCE_ROOT=1
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

CMD python manage.py migrate
