from forcealign import ForceAlign
import json

# Input paths
audio_path = 'vocals.wav'
lyrics_path = 'lyrics.txt'
output_json = 'lyrics_lines.json'

# Load the original formatted lyrics
with open(lyrics_path, 'r') as f:
    raw_lines = [line.strip() for line in f.readlines()]

# Tokenize lines
lines = [line.split() for line in raw_lines]
flat_transcript_words = [w for line in lines for w in line]

# Align using flat transcript
align = ForceAlign(audio_file=audio_path, transcript=' '.join(flat_transcript_words))
aligned_words = align.inference()

# Now rebuild full lines with timing
line_level_lyrics = []
w_idx = 0

for line_num, original_words in enumerate(lines):
    if not original_words:
        continue  # Skip empty lines

    start = None
    end = None
    words_in_line = []

    for word in original_words:
        if w_idx >= len(aligned_words):
            break

        aligned_word = aligned_words[w_idx]
        words_in_line.append(word)
        if start is None:
            start = aligned_word.time_start
        end = aligned_word.time_end
        w_idx += 1

    line_level_lyrics.append({
        "line": " ".join(words_in_line),
        "start": start,
        "end": end
    })

# Save result
with open(output_json, "w") as f:
    json.dump(line_level_lyrics, f, indent=2)

# Optional preview
print(f"Saved {len(line_level_lyrics)} lines to {output_json}")
for line in line_level_lyrics[:3]:
    print(f"[{line['start']:.2f}-{line['end']:.2f}] {line['line']}")