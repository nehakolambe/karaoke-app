from forcealign import ForceAlign
import json

# Provide path to audio file and corresponding transcript
audio_path = 'static/song1.wav'  # Or './song.mp3'
with open('lyrics1.txt', 'r') as f:
    transcript = f.read()

# Create aligner
align = ForceAlign(audio_file=audio_path, transcript=transcript)

# Run alignment
words = align.inference()

# Save results to lyrics.json
aligned_words = [
    {"word": word.word, "start": word.time_start, "end": word.time_end}
    for word in words
]

with open("lyrics1.json", "w") as f:
    json.dump(aligned_words, f, indent=2)

# Print a preview
for word in aligned_words:
    print(f"[{word['start']:.2f} - {word['end']:.2f}] {word['word']}")