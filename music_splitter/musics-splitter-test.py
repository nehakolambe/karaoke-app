import pika
import json

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel = connection.channel()
channel.queue_declare(queue="split-jobs")

message = json.dumps({"song_id": "test123"})
channel.basic_publish(
    exchange='',
    routing_key='split-jobs',
    body=message
)

print("Sent job for test123")
