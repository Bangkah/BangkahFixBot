FROM python:3.12-slim

RUN pip install --no-cache-dir pytest==8.4.1 \
    && useradd -m -s /bin/bash tester

USER tester
WORKDIR /src
CMD ["pytest", "-q"]
