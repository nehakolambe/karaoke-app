from forcealign import ForceAlign
import json

# Input paths
audio_path = 'vocals_fixed.wav'
lyrics_path = 'lyrics.txt'
output_json = 'lyrics_vocals_fixed.json'

# Load the original formatted lyrics
with open(lyrics_path, 'r') as f:
    lines = [line.strip().split() for line in f.readlines()]

# Flatten for alignment
flat_transcript_words = [w for line in lines for w in line]

# Create ForceAlign instance
align = ForceAlign(audio_file=audio_path, transcript=' '.join(flat_transcript_words))

# Run alignment
words = align.inference()

# Build aligned output with original words and line numbers
aligned_words = []
w_idx = 0

for line_num, line in enumerate(lines):
    for word in line:
        if w_idx >= len(words):
            break
        aligned_word = words[w_idx]
        aligned_words.append({
            "word": word,
            "start": aligned_word.time_start,
            "end": aligned_word.time_end,
            "line": line_num
        })
        w_idx += 1

# Save result
with open(output_json, "w") as f:
    json.dump(aligned_words, f, indent=2)