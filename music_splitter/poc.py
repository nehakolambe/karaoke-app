import sys

from spleeter.separator import Separator
from spleeter.audio.adapter import AudioAdapter
import os

def split_and_save_instrumental(input_path: str, output_dir: str) -> None:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    sep = Separator('spleeter:2stems')
    audio_loader = AudioAdapter.default()

    print("Reading audio files...")
    waveform, _ = audio_loader.load(input_path)

    print("Separating...")
    separated_audio = sep.separate(waveform)

    accompaniment = separated_audio['accompaniment']

    print("Writing separated audio...")
    output_path = os.path.join(output_dir, 'instrumental.wav')
    audio_loader.save(output_path, accompaniment, sample_rate=44000)

    print(f"Instrumental saved at: {output_path}")

if __name__ == "__main__":
    split_and_save_instrumental('/Users/pratikbhirud/Library/CloudStorage/OneDrive-UCB-O365/CU Boulder/Sem2/Big Data/karaoke-app/music_splitter/temp_input/Luka Chuppi Duniyaa Full Video Song  Kartik Aaryan Kriti Sanon  Akhil  Dhvani B.mp3',
                                'output')