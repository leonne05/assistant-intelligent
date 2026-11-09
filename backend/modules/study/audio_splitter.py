import os
import re
import shutil
import subprocess
import tempfile


class AudioSplitter:
    def __init__(self, segment_seconds=300):
        self.segment_seconds = segment_seconds
        self.timeout_seconds = 1800
        self.max_segments = 60


    def find_ffmpeg(self):

        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

        ffmpeg_path = shutil.which("ffmpeg")

        if ffmpeg_path:
            return ffmpeg_path

        raise RuntimeError("ffmpeg est introuvable : installe-le avec la commande « pip install imageio-ffmpeg ».")


    def split(self, audio_file_name, audio_bytes):

        ffmpeg_path = self.find_ffmpeg()

        with tempfile.TemporaryDirectory() as folder:
            extension = re.sub(r"[^A-Za-z0-9.]", "", os.path.splitext(audio_file_name or "")[1])[:10] or ".audio"
            input_path = os.path.join(folder, "input" + extension)

            with open(input_path, "wb") as input_file:
                input_file.write(audio_bytes)

            command = [
                ffmpeg_path, "-y", "-loglevel", "error",
                "-i", input_path,
                "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "32k",
                "-f", "segment", "-segment_time", str(self.segment_seconds), "-reset_timestamps", "1",
                os.path.join(folder, "part_%03d.mp3"),
            ]

            try:
                result = subprocess.run(command, capture_output=True, timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                raise RuntimeError("Le découpage de l'audio a pris trop de temps.")

            part_names = sorted(name for name in os.listdir(folder) if name.startswith("part_"))

            if result.returncode != 0 or not part_names:
                raise ValueError("Impossible de lire ce fichier audio (format non reconnu ou fichier abîmé).")

            if len(part_names) > self.max_segments:
                raise ValueError("Cet audio est trop long : découpe-le en plusieurs fichiers.")

            parts = []

            for index, part_name in enumerate(part_names, start=1):
                with open(os.path.join(folder, part_name), "rb") as part_file:
                    parts.append((f"partie_{index:03d}.mp3", part_file.read()))

            return parts