FROM python:3.11

RUN ls -la

COPY . .

RUN pip install --no-cache-dir ipykernel~=6.29.4 \
    && pip install .
