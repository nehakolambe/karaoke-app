import pika
import json

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel = connection.channel()
channel.queue_declare(queue="lyrics-jobs")

message = json.dumps({"song_id": "665379"})
channel.basic_publish(
    exchange='',
    routing_key='lyrics-jobs',
    body=message
)

print("Sent job for 665379")