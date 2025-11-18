#!/bin/bash
# RabbitMQ initialization script for development queues

set -e

echo "Waiting for RabbitMQ to start..."
sleep 10

# Create exchanges
rabbitmqadmin declare exchange name=photo-detection-exchange type=topic durable=true

# Create priority queues
rabbitmqadmin declare queue name=companycam-photos-high-priority-dev durable=true \
  arguments='{"x-message-ttl":1209600000,"x-dead-letter-exchange":"photo-detection-dlx"}'

rabbitmqadmin declare queue name=companycam-photos-normal-priority-dev durable=true \
  arguments='{"x-message-ttl":1209600000,"x-dead-letter-exchange":"photo-detection-dlx"}'

rabbitmqadmin declare queue name=companycam-photos-low-priority-dev durable=true \
  arguments='{"x-message-ttl":1209600000,"x-dead-letter-exchange":"photo-detection-dlx"}'

# Create dead letter exchange
rabbitmqadmin declare exchange name=photo-detection-dlx type=fanout durable=true

# Create dead letter queues
rabbitmqadmin declare queue name=companycam-photos-high-priority-dlq-dev durable=true
rabbitmqadmin declare queue name=companycam-photos-normal-priority-dlq-dev durable=true
rabbitmqadmin declare queue name=companycam-photos-low-priority-dlq-dev durable=true

# Bind queues to exchanges
rabbitmqadmin declare binding source=photo-detection-exchange \
  destination=companycam-photos-high-priority-dev routing_key=photo.high

rabbitmqadmin declare binding source=photo-detection-exchange \
  destination=companycam-photos-normal-priority-dev routing_key=photo.normal

rabbitmqadmin declare binding source=photo-detection-exchange \
  destination=companycam-photos-low-priority-dev routing_key=photo.low

# Bind DLQ to dead letter exchange
rabbitmqadmin declare binding source=photo-detection-dlx \
  destination=companycam-photos-high-priority-dlq-dev

rabbitmqadmin declare binding source=photo-detection-dlx \
  destination=companycam-photos-normal-priority-dlq-dev

rabbitmqadmin declare binding source=photo-detection-dlx \
  destination=companycam-photos-low-priority-dlq-dev

echo "RabbitMQ queues and exchanges configured successfully!"
