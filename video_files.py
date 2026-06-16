import re
import subprocess
from pathlib import Path


def run_ffmpeg(source_path, start, end, output_path):
    if output_path.exists():
        raise FileExistsError(f"Le fichier existe déjà : {output_path.name}")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-n",
        "-ss",
        f"{start:.6f}",
        "-to",
        f"{end:.6f}",
        "-i",
        str(source_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def next_output_paths(work_dir, prefix, count, ignored_path=None):
    used = set()
    ignored_path = Path(ignored_path) if ignored_path is not None else None
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)\.mp4$", re.IGNORECASE)

    for file_path in work_dir.glob("*.mp4"):
        if ignored_path is not None and file_path == ignored_path:
            continue
        match = pattern.match(file_path.name)
        if match:
            used.add(int(match.group(1)))

    outputs = []
    index = 1
    while len(outputs) < count:
        if index not in used:
            candidate = work_dir / f"{prefix}_{index}.mp4"
            if not candidate.exists() or candidate == ignored_path:
                outputs.append(candidate)
                used.add(index)
        index += 1
    return outputs


def temporary_output_path(final_path):
    index = 1
    while True:
        candidate = final_path.with_name(
            f".{final_path.stem}.cut-tmp-{index}{final_path.suffix}"
        )
        if not candidate.exists():
            return candidate
        index += 1


def video_prefix(path):
    match = re.match(r"(.+)_\d+\.mp4$", path.name, re.IGNORECASE)
    if match:
        return match.group(1)
    return path.stem
