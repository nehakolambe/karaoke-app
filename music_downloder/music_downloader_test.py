import pika
import json

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel = connection.channel()
channel.queue_declare(queue="download-jobs")

message = json.dumps({"song_id": "665379", "song_name": "Love me like you do", "artist_name": "Ellie Goulding" })
channel.basic_publish(
    exchange='',
    routing_key='download-jobs',
    body=message
)

print("Sent job for 665379")