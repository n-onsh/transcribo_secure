Directory structure:
└── machinelearningzh-audio-transcription/
    ├── README.md
    ├── LICENSE
    ├── compose.yaml
    ├── dockerfile
    ├── main.py
    ├── pyproject.toml
    ├── requirements-mps.txt
    ├── requirements.txt
    ├── run_gui.bat
    ├── run_transcribo.bat
    ├── run_worker.bat
    ├── startup.sh
    ├── uv.lock
    ├── worker.py
    ├── .dockerignore
    ├── .env_example
    ├── _img/
    │   └── ui1.PNG
    ├── data/
    │   ├── bootstrap_content.txt
    │   ├── const.py
    │   └── logo.txt
    ├── docker_aargau/
    │   ├── README.md
    │   ├── bootup.sh
    │   └── dockerfile
    ├── help/
    │   ├── editor_buttons.PNG
    │   ├── player.PNG
    │   └── segment.PNG
    └── src/
        ├── help.py
        ├── srt.py
        ├── transcription.py
        ├── util.py
        └── viewer.py


Files Content:

================================================
File: README.md
================================================
# Audio Transcription Tool «TranscriboZH»
**Transcribe any audio or video file. Edit and view your transcripts in a standalone HTML editor.**

![GitHub License](https://img.shields.io/github/license/machinelearningzh/audio-transcription)
[![PyPI - Python](https://img.shields.io/badge/python-v3.10+-blue.svg)](https://github.com/machinelearningZH/audio-transcription)
[![GitHub Stars](https://img.shields.io/github/stars/machinelearningZH/audio-transcription.svg)](https://github.com/machinelearningZH/audio-transcription/stargazers)
[![GitHub Issues](https://img.shields.io/github/issues/machinelearningZH/audio-transcription.svg)](https://github.com/machinelearningZH/audio-transcription/issues)
[![GitHub Issues](https://img.shields.io/github/issues-pr/machinelearningZH/audio-transcription.svg)](https://img.shields.io/github/issues-pr/machinelearningZH/audio-transcription) 
[![Current Version](https://img.shields.io/badge/version-1.0-green.svg)](https://github.com/machinelearningZH/audio-transcription)
<a href="https://github.com/astral-sh/ruff"><img alt="linting - Ruff" class="off-glb" loading="lazy" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json"></a>


<img src="_img/ui1.PNG" alt="editor" width="1000"/>

<details>

<summary>Contents</summary>

- [Setup Instructions](#setup-instructions)
    - [Hardware requirements](#hardware-requirements)
    - [Installation](#installation)
    - [Running the Application](#running-the-application)
    - [Configuration](#configuration)
- [Project Information](#project-information)
    - [What does the application do?](#what-does-the-application-do)
- [Project team](#project-team)
- [Feedback and Contributions](#feedback-and-contributions)
- [Disclaimer](#disclaimer)

</details>

## Setup Instructions
### Hardware requirements
- We strongly recommend using a CUDA-compatible graphics card, as transcription on a CPU is extremely slow.
    - https://developer.nvidia.com/cuda-gpus
- If you are using a graphics card, you need at least 8GB VRAM. Performance is better with 16GB VRAM.
- 8GB RAM
 
### Installation
- Ensure you have a compatible NVIDIA driver and CUDA Version installed: https://pytorch.org/
- Install ffmpeg
    - Windows: https://phoenixnap.com/kb/ffmpeg-windows
    - Linux (Ubuntu): `sudo apt install ffmpeg`
- Install conda
    - Windows:
        - Install [Anaconda](https://docs.anaconda.com/free/anaconda/install/) or [Miniconda](https://docs.conda.io/projects/miniconda/en/latest/).
    - Linux (Ubuntu):
        - `mkdir -p ~/miniconda3`
        - `wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh`
        - `bash ~/miniconda3/miniconda.sh -u`
        - `rm ~/miniconda3/miniconda.sh`
        - Close and re-open your current shell.
- Create a new Python environment, e.g.: `conda create --name transcribo python=3.10`
- Activate your new environment: `conda activate transcribo`
- Clone this repo.
- Install packages:
    - Check the installed cuda version: `nvcc --version`
    - Run the following command with your specific cuda version. **This example is for cuda version 11.8, edit the command for your installed version**.
    - `conda install pytorch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 pytorch-cuda=11.8 -c pytorch -c nvidia`
    - `pip install -r requirements.txt`
    - MacOS 
      - Don't do the above, but:
        ```
        conda install pytorch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2  -c pytorch 
        pip install -r requirements.txt 
        pip install -r requirements-mps.txt
        pip install --force --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cpu # when pytorch 2.6/7 is released, this line can be removed
        pip install --force-reinstall -v "numpy==1.26.3"` # hopefully also not needed in the future
        ```
      - And set `DEVICE = "mps"` in your `.env` file
      - You don't need to uninstall onnxruntime in the next step
- Make sure, that the onnxruntime-gpu package is installed. Otherwise uninstall onnxruntime and install onnxruntime-gpu (if in doubt, just reinstall onnxruntime-gpu)
    - `pip uninstall onnxruntime`
    - `pip install --force-reinstall onnxruntime-gpu`
    - `pip install --force-reinstall -v "numpy==1.26.3"`
- Create a Huggingface access token
    - Accept [pyannote/segmentation](https://huggingface.co/pyannote/segmentation)) user conditions
    - Accept [pyannote/speaker-diarization-3.0](https://huggingface.co/pyannote/speaker-diarization) user conditions
    - Create access token at [hf.co/settings/tokens](https://hf.co/settings/tokens) with read and write permissions.
- Create a `.env` file and add your access token. See the file `.env_example`.
```
    HF_AUTH_TOKEN = ...
```
- Edit all the variables of `.env_example` in your `.env` file for your specific configuration. Make sure that your `.env` file is in your `.gitignore`.

### Installation with Docker
- Install docker (on Windows use WSL2 backend)
- Run `docker-compose up -d --build`

### Running the Application
Start the worker and frontend scripts:
- Linux / MacOS
    - `tmux new -s transcribe_worker`
    - `conda activate transcribo`
    - Linux:
      - `python worker.py`
    - MacOS:
      - The MPS/MLX implementation of all this has some massive memory leaks, so we do restart the worker after every transcription. Patches to prevent this are welcome.
      - `while true; do python worker.py; done`
    - Exit tmux session with `CTRL-B` and `D`.
    - `tmux new -s transcribe_frontend`
    - `conda activate transcribo`
    - `python main.py`
    - You can restore your sessions with `tmux attach -t transcribe_worker` and `tmux attach -t transcribe_frontend`
- Windows
    - See `run_gui.bat`, `run_transcribo.bat` and `run_worker.bat`
    - Make sure not to run the worker script multiple times. If more than one worker script is running, it will consume too much VRAM and significantly slow down the system.

### Configuration
|   | Description |
|---|---|
| ONLINE | Boolean. If TRUE, exposes the frontend in your network. For https, you must provide a SSL cert and key file. See the [nicegui](https://nicegui.io/documentation/section_configuration_deployment) documentation for more information |
| SSL_CERTFILE | String. The file path to the SSL cert file |
| SSL_KEYFILE | String. The file path to the SSL key file |
| STORAGE_SECRET | String. Secret key for cookie-based identification of users |
| ROOT | String. path to main.py and worker.py |
| WINDOWS | Boolean. Set TRUE if you are running this application on Windows. |
| DEVICE | String. 'cuda' if you are using a GPU. 'cpu' otherwise. |
| ADDITIONAL_SPEAKERS | Integer. Number of additional speakers provied in the editor |
| BATCH_SIZE | Integer. Batch size for Whisper inference. Recommended batch size is 4 with 8GB VRAM and 32 with 16GB VRAM. |


## Project Information
This application provides advanced transcription capabilities for confidential audio and video files using the state-of-the-art Whisper v3 large model (non-quantized). It offers top-tier transcription quality without licensing or usage fees, even for Swiss German.

### What does the application do?
- State-of-the-Art Transcription: Powered by Whisper v3 large model, ensuring high accuracy and reliability.
- Cost-Free: No license or usage-related costs, making it an affordable solution for everyone.
- High Performance: Transcribe up to 15 times faster than real-time, ensuring efficient processing.
- High-Quality Transcriptions: Exceptional transcription quality for English and local languages, with substantial accuracy for Swiss German.
- Speaker Diarisation: Automatic identification and differentiation of speakers within the audio.
- Multi-File Upload: Easily upload and manage multiple files for transcription.
- Predefined vocabulary: Define the spelling of ambiguous words and names.
- Transcript Export Options: Export transcriptions in various formats:
    - Text file
    - SRT file (for video subtitles)
    - Synchronized viewer with integrated audio or video
- Integrated Editing: Edit transcriptions directly within the application, synchronously linked with the source video or audio. The editor is open-source and requires no installation.
    - General Text Editing Functions: Standard text editing features for ease of use.
    - Segments: Add or remove speech segments.
    - Speaker Naming: Assign names to identified speakers for clarity.
    - Power User Shortcuts: Keyboard shortcuts for enhanced navigation and control (start, stop, forward, backward, etc.).




## Project team
This project is a collaborative effort of these people of the cantonal administration of Zurich:

- **Stephan Walder** - [Leiter Digitale Transformation, Oberstaatsanwaltschaft Kanton Zürich](https://www.zh.ch/de/direktion-der-justiz-und-des-innern/staatsanwaltschaft/Oberstaatsanwaltschaft-des-Kantons-Zuerich.html)
- **Dominik Frefel** - [Team Data, Statistisches Amt](https://www.zh.ch/de/direktion-der-justiz-und-des-innern/statistisches-amt/data.html)
- **Patrick Arnecke** - [Team Data, Statistisches Amt](https://www.zh.ch/de/direktion-der-justiz-und-des-innern/statistisches-amt/data.html)
  
## Feedback and Contributions
Please share your feedback and let us know how you use the app in your institution. You can [write an email](mailto:datashop@statistik.zh.ch) or share your ideas by opening an issue or a pull requests.

Please note, we use [Ruff](https://docs.astral.sh/ruff/) for linting and code formatting with default settings.

## Disclaimer
This transcription software (the Software) incorporates the open-source model Whisper Large v3 (the Model) and has been developed according to and with the intent to be used under Swiss law. Please be aware that the EU Artificial Intelligence Act (EU AI Act) may, under certain circumstances, be applicable to your use of the Software. You are solely responsible for ensuring that your use of the Software as well as of the underlying Model complies with all applicable local, national and international laws and regulations. By using this Software, you acknowledge and agree (a) that it is your responsibility to assess which laws and regulations, in particular regarding the use of AI technologies, are applicable to your intended use and to comply therewith, and (b) that you will hold us harmless from any action, claims, liability or loss in respect of your use of the Software.


================================================
File: LICENSE
================================================
MIT License

Copyright (c) 2024 AI + Machine Learning Canton of Zurich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


================================================
File: compose.yaml
================================================
services:
  transcriber:
    image: yanick/audiotranscription:latest
    build:
      dockerfile: dockerfile
      context: .
      platforms:
        - linux/amd64
        - linux/arm64
    restart: unless-stopped
    ports:
      - 8080:8080
    volumes:
      - hugging_face_cache:/root/.cache/huggingface
    develop:
      watch:
        - path: faster_whisper_server
          action: rebuild
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: ["gpu"]
volumes:
  hugging_face_cache:

================================================
File: dockerfile
================================================
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
RUN apt-get update && \
    apt-get install -y ffmpeg software-properties-common
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ADD . /app
WORKDIR /app
RUN uv sync --frozen
RUN chmod +x ./startup.sh
ENTRYPOINT uv run bash ./startup.sh

================================================
File: main.py
================================================
import os
import time
import shutil
import zipfile
import datetime
import base64
from os import listdir
from os.path import isfile, join, normpath, basename, dirname
from functools import partial
from dotenv import load_dotenv
from nicegui import ui, events, app

from data.const import LANGUAGES, INVERTED_LANGUAGES
from src.util import time_estimate
from src.help import (
    help as help_page,
)  # Renamed to avoid conflict with built-in help function

# Load environment variables
load_dotenv()

# Configuration
ONLINE = os.getenv("ONLINE") == "True"
STORAGE_SECRET = os.getenv("STORAGE_SECRET")
ROOT = os.getenv("ROOT")
WINDOWS = os.getenv("WINDOWS") == "True"
SSL_CERTFILE = os.getenv("SSL_CERTFILE")
SSL_KEYFILE = os.getenv("SSL_KEYFILE")

if WINDOWS:
    os.environ["PATH"] += os.pathsep + "ffmpeg/bin"
    os.environ["PATH"] += os.pathsep + "ffmpeg"

BACKSLASHCHAR = "\\"
user_storage = {}


def read_files(user_id):
    """Read in all files of the user and set the file status if known."""
    user_storage[user_id]["file_list"] = []
    in_path = join(ROOT, "data", "in", user_id)
    out_path = join(ROOT, "data", "out", user_id)
    error_path = join(ROOT, "data", "error", user_id)

    if os.path.exists(in_path):
        for f in listdir(in_path):
            if isfile(join(in_path, f)) and f != "hotwords.txt" and f != "language.txt":
                file_status = [
                    f,
                    "Datei in Warteschlange. Geschätzte Wartezeit: ",
                    0.0,
                    0,
                    os.path.getmtime(join(in_path, f)),
                ]
                if isfile(join(out_path, f + ".html")):
                    file_status[1] = "Datei transkribiert"
                    file_status[2] = 100.0
                    file_status[3] = 0
                else:
                    estimated_time, _ = time_estimate(join(in_path, f), ONLINE)
                    if estimated_time == -1:
                        estimated_time = 0
                    file_status[3] = estimated_time

                user_storage[user_id]["file_list"].append(file_status)

        files_in_queue = []
        for u in user_storage:
            for f in user_storage[u].get("file_list", []):
                if (
                    "updates" in user_storage[u]
                    and len(user_storage[u]["updates"]) > 0
                    and user_storage[u]["updates"][0] == f[0]
                ):
                    f = user_storage[u]["updates"]
                if f[2] < 100.0:
                    files_in_queue.append(f)

        for file_status in user_storage[user_id]["file_list"]:
            estimated_wait_time = sum(f[3] for f in files_in_queue if f[4] < file_status[4])
            if file_status[2] < 100.0:
                wait_time_str = str(datetime.timedelta(seconds=round(estimated_wait_time + file_status[3])))
                file_status[1] += wait_time_str

    if os.path.exists(error_path):
        for f in listdir(error_path):
            if isfile(join(error_path, f)) and not f.endswith(".txt"):
                text = "Transkription fehlgeschlagen"
                error_file = join(error_path, f + ".txt")
                if isfile(error_file):
                    with open(error_file, "r") as txtf:
                        content = txtf.read()
                        if content:
                            text = content
                file_status = [f, text, -1, 0, os.path.getmtime(join(error_path, f))]
                if f not in user_storage[user_id]["known_errors"]:
                    user_storage[user_id]["known_errors"].add(f)
                user_storage[user_id]["file_list"].append(file_status)

    user_storage[user_id]["file_list"].sort()


async def handle_upload(e: events.UploadEventArguments, user_id):
    """Save the uploaded file to disk."""
    in_path = join(ROOT, "data", "in", user_id)
    out_path = join(ROOT, "data", "out", user_id)
    error_path = join(ROOT, "data", "error", user_id)

    os.makedirs(in_path, exist_ok=True)
    os.makedirs(out_path, exist_ok=True)

    file_name = e.name

    # Clean up error files if re-uploading
    if os.path.exists(error_path):
        if file_name in user_storage[user_id]["known_errors"]:
            user_storage[user_id]["known_errors"].remove(file_name)
        error_file = join(error_path, file_name)
        error_txt_file = error_file + ".txt"
        if os.path.exists(error_file):
            os.remove(error_file)
        if os.path.exists(error_txt_file):
            os.remove(error_txt_file)

    # Ensure unique file names
    original_file_name = file_name
    for i in range(1, 10001):
        if isfile(join(in_path, file_name)):
            name, ext = os.path.splitext(original_file_name)
            file_name = f"{name}_{i}{ext}"
        else:
            break
    else:
        ui.notify("Zu viele Dateien mit dem gleichen Namen.")
        return

    # Save hotwords if provided
    hotwords_content = app.storage.user.get(f"{user_id}_vocab", "").strip()
    hotwords_file = join(in_path, "hotwords.txt")
    if hotwords_content:
        with open(hotwords_file, "w") as f:
            f.write(hotwords_content)
    elif isfile(hotwords_file):
        os.remove(hotwords_file)

    # Save the selected language
    language = app.storage.user.get(f"{user_id}_language", "").strip()
    language_file = join(in_path, "language.txt")
    if language:
        with open(language_file, "w") as f:
            f.write(language)
    else:
        with open(language_file, "w") as f:
            f.write("de")

    # Save the uploaded file
    with open(join(in_path, file_name), "wb") as f:
        f.write(e.content.read())


def handle_reject(e: events.GenericEventArguments):
    ui.notify("Ungültige Datei. Es können nur Audio/Video-Dateien unter 12GB transkribiert werden.")


def handle_added(e: events.GenericEventArguments, user_id, upload_element, refresh_file_view):
    """After a file was added, refresh the GUI."""
    upload_element.run_method("removeUploadedFiles")
    refresh_file_view(user_id=user_id, refresh_queue=True, refresh_results=False)


def prepare_download(file_name, user_id):
    """Add offline functions to the editor before downloading."""
    out_user_dir = join(ROOT, "data", "out", user_id)
    full_file_name = join(out_user_dir, file_name + ".html")

    with open(full_file_name, "r", encoding="utf-8") as f:
        content = f.read()

    update_file = full_file_name + "update"
    if os.path.exists(update_file):
        with open(update_file, "r", encoding="utf-8") as f:
            new_content = f.read()
        start_index = content.find("</nav>") + len("</nav>")
        end_index = content.find("var fileName = ")
        content = content[:start_index] + new_content + content[end_index:]

        with open(full_file_name, "w", encoding="utf-8") as f:
            f.write(content)

        os.remove(update_file)

    content = content.replace(
        "<div>Bitte den Editor herunterladen, um den Viewer zu erstellen.</div>",
        '<a href="#" id="viewer-link" onclick="viewerClick()" class="btn btn-primary">Viewer erstellen</a>',
    )
    if "var base64str = " not in content:
        video_file_path = join(out_user_dir, file_name + ".mp4")
        with open(video_file_path, "rb") as video_file:
            video_base64 = base64.b64encode(video_file.read()).decode("utf-8")

        video_content = f"""
var base64str = "{video_base64}";
var binary = atob(base64str);
var len = binary.length;
var buffer = new ArrayBuffer(len);
var view = new Uint8Array(buffer);
for (var i = 0; i < len; i++) {{
    view[i] = binary.charCodeAt(i);
}}

var blob = new Blob([view], {{ type: "video/MP4" }});
var url = URL.createObjectURL(blob);

var video = document.getElementById("player");

setTimeout(function() {{
  video.pause();
  video.setAttribute('src', url);
}}, 100);
</script>
"""
        content = content.replace("</script>", video_content)

    final_file_name = full_file_name + "final"
    with open(final_file_name, "w", encoding="utf-8") as f:
        f.write(content)


async def download_editor(file_name, user_id):
    prepare_download(file_name, user_id)
    final_file_name = join(ROOT, "data", "out", user_id, file_name + ".htmlfinal")
    ui.download(src=final_file_name, filename=f"{os.path.splitext(file_name)[0]}.html")


async def download_srt(file_name, user_id):
    srt_file = join(ROOT, "data", "out", user_id, file_name + ".srt")
    ui.download(src=srt_file, filename=f"{os.path.splitext(file_name)[0]}.srt")


async def open_editor(file_name, user_id):
    out_user_dir = join(ROOT, "data", "out", user_id)
    full_file_name = join(out_user_dir, file_name + ".html")
    with open(full_file_name, "r", encoding="utf-8") as f:
        content = f.read()

    video_path = f"/data/{user_id}/{file_name}.mp4"
    content = content.replace(
        '<video id="player" width="100%" style="max-height: 320px" src="" type="video/MP4" controls="controls" position="sticky"></video>',
        f'<video id="player" width="100%" style="max-height: 320px" src="{video_path}" type="video/MP4" controls="controls" position="sticky"></video>',
    )
    content = content.replace(
        '<video id="player" width="100%" style="max-height: 250px" src="" type="video/MP4" controls="controls" position="sticky"></video>',
        f'<video id="player" width="100%" style="max-height: 250px" src="{video_path}" type="video/MP4" controls="controls" position="sticky"></video>',
    )

    user_storage[user_id]["content"] = content
    user_storage[user_id]["full_file_name"] = full_file_name
    ui.open(editor, new_tab=True)


async def download_all(user_id):
    zip_file_path = join(ROOT, "data", "out", user_id, "transcribed_files.zip")
    with zipfile.ZipFile(zip_file_path, "w", allowZip64=True) as myzip:
        for file_status in user_storage[user_id]["file_list"]:
            if file_status[2] == 100.0:
                prepare_download(file_status[0], user_id)
                final_html = join(ROOT, "data", "out", user_id, file_status[0] + ".htmlfinal")
                myzip.write(final_html, arcname=file_status[0] + ".html")
    ui.download(zip_file_path)


def delete_file(file_name, user_id, refresh_file_view):
    paths_to_delete = [
        join(ROOT, "data", "in", user_id, file_name),
        join(ROOT, "data", "error", user_id, file_name),
        join(ROOT, "data", "error", user_id, file_name + ".txt"),
    ]
    suffixes = ["", ".txt", ".html", ".mp4", ".srt", ".htmlupdate", ".htmlfinal"]
    for suffix in suffixes:
        paths_to_delete.append(join(ROOT, "data", "out", user_id, file_name + suffix))

    for path in paths_to_delete:
        if os.path.exists(path):
            os.remove(path)

    refresh_file_view(user_id=user_id, refresh_queue=True, refresh_results=True)


def listen(user_id, refresh_file_view):
    """Periodically check if a file is being transcribed and calculate its estimated progress."""
    worker_user_dir = join(ROOT, "data", "worker", user_id)

    if os.path.exists(worker_user_dir):
        for f in listdir(worker_user_dir):
            if isfile(join(worker_user_dir, f)):
                parts = f.split("_")
                if len(parts) < 3:
                    continue
                estimated_time = float(parts[0])
                start = float(parts[1])
                file_name = "_".join(parts[2:])
                progress = min(0.975, (time.time() - start) / estimated_time)
                estimated_time_left = round(max(1, estimated_time - (time.time() - start)))

                in_file = join(ROOT, "data", "in", user_id, file_name)
                if os.path.exists(in_file):
                    user_storage[user_id]["updates"] = [
                        file_name,
                        f"Datei wird transkribiert. Geschätzte Bearbeitungszeit: {datetime.timedelta(seconds=estimated_time_left)}",
                        progress * 100,
                        estimated_time_left,
                        os.path.getmtime(in_file),
                    ]
                else:
                    os.remove(join(worker_user_dir, f))
                refresh_file_view(
                    user_id=user_id,
                    refresh_queue=True,
                    refresh_results=(user_storage[user_id].get("file_in_progress") != file_name),
                )
                user_storage[user_id]["file_in_progress"] = file_name
                return

        # No files being processed
        if user_storage[user_id].get("updates"):
            user_storage[user_id]["updates"] = []
            user_storage[user_id]["file_in_progress"] = None
            refresh_file_view(user_id=user_id, refresh_queue=True, refresh_results=True)
        else:
            refresh_file_view(user_id=user_id, refresh_queue=True, refresh_results=False)


def update_hotwords(user_id):
    if "textarea" in user_storage[user_id]:
        app.storage.user[f"{user_id}_vocab"] = user_storage[user_id]["textarea"].value


def update_language(user_id):
    if "language" in user_storage[user_id]:
        app.storage.user[f"{user_id}_language"] = INVERTED_LANGUAGES[user_storage[user_id]["language"].value]


@ui.page("/editor")
async def editor():
    """Prepare and open the editor for online editing."""

    async def handle_save(full_file_name):
        content = ""
        for i in range(100):
            content_chunk = await ui.run_javascript(
                f"""
var content = String(document.documentElement.innerHTML);
var start_index = content.indexOf('<!--start-->') + '<!--start-->'.length;
content = content.slice(start_index, content.indexOf('var fileName = ', start_index))
content = content.slice(content.indexOf('</nav>') + '</nav>'.length, content.length)
return content.slice({i * 500_000}, {(i + 1) * 500_000});
""",
                timeout=60.0,
            )
            content += content_chunk
            if len(content_chunk) < 500_000:
                break

        update_file = full_file_name + "update"
        with open(update_file, "w", encoding="utf-8") as f:
            f.write(content.strip())

        ui.notify("Änderungen gespeichert.")

    user_id = str(app.storage.browser.get("id", "local")) if ONLINE else "local"

    out_user_dir = join(ROOT, "data", "out", user_id)
    app.add_media_files(f"/data/{user_id}", out_user_dir)
    user_data = user_storage.get(user_id, {})
    full_file_name = user_data.get("full_file_name")

    if full_file_name:
        ui.on("editor_save", lambda e: handle_save(full_file_name))
        ui.add_body_html("<!--start-->")

        content = user_data.get("content", "")
        update_file = full_file_name + "update"
        if os.path.exists(update_file):
            with open(update_file, "r", encoding="utf-8") as f:
                new_content = f.read()
            start_index = content.find("</nav>") + len("</nav>")
            end_index = content.find("var fileName = ")
            content = content[:start_index] + new_content + content[end_index:]

        content = content.replace(
            '<a href ="#" id="viewer-link" onClick="viewerClick()" class="btn btn-primary">Viewer erstellen</a>',
            "<div>Bitte den Editor herunterladen, um den Viewer zu erstellen.</div>",
        )
        content = content.replace(
            '<a href="#" id="viewer-link" onclick="viewerClick()" class="btn btn-primary">Viewer erstellen</a>',
            "<div>Bitte den Editor herunterladen, um den Viewer zu erstellen.</div>",
        )
        ui.add_body_html(content)

        ui.add_body_html(
            """
<script language="javascript">
    var origFunction = downloadClick;
    downloadClick = function downloadClick() {
        emitEvent('editor_save');
    }
</script>
"""
        )
    else:
        ui.label("Session abgelaufen. Bitte öffne den Editor erneut.")


@ui.page("/")
async def main_page():
    """Main page of the application."""

    def refresh_file_view(user_id, refresh_queue, refresh_results):
        num_errors = len(user_storage[user_id]["known_errors"])
        read_files(user_id)
        if refresh_queue:
            display_queue.refresh(user_id=user_id)
        if refresh_results or num_errors < len(user_storage[user_id]["known_errors"]):
            display_results.refresh(user_id=user_id)

    @ui.refreshable
    def display_queue(user_id):
        for file_status in sorted(user_storage[user_id]["file_list"], key=lambda x: (x[2], -x[4], x[0])):
            if user_storage[user_id].get("updates") and user_storage[user_id]["updates"][0] == file_status[0]:
                file_status = user_storage[user_id]["updates"]
            if 0 <= file_status[2] < 100.0:
                ui.markdown(f"<b>{file_status[0].replace('_', BACKSLASHCHAR + '_')}:</b> {file_status[1]}")
                ui.linear_progress(value=file_status[2] / 100, show_value=False, size="10px").props("instant-feedback")
                ui.separator()

    @ui.refreshable
    def display_results(user_id):
        any_file_ready = False
        for file_status in sorted(user_storage[user_id]["file_list"], key=lambda x: (x[2], -x[4], x[0])):
            if user_storage[user_id].get("updates") and user_storage[user_id]["updates"][0] == file_status[0]:
                file_status = user_storage[user_id]["updates"]
            if file_status[2] >= 100.0:
                ui.markdown(f"<b>{file_status[0].replace('_', BACKSLASHCHAR + '_')}</b>")
                with ui.row():
                    ui.button(
                        "Editor herunterladen (Lokal)",
                        on_click=partial(download_editor, file_name=file_status[0], user_id=user_id),
                    ).props("no-caps")
                    ui.button(
                        "Editor öffnen (Server)",
                        on_click=partial(open_editor, file_name=file_status[0], user_id=user_id),
                    ).props("no-caps")
                    ui.button(
                        "SRT-Datei",
                        on_click=partial(download_srt, file_name=file_status[0], user_id=user_id),
                    ).props("no-caps")
                    ui.button(
                        "Datei entfernen",
                        on_click=partial(
                            delete_file,
                            file_name=file_status[0],
                            user_id=user_id,
                            refresh_file_view=refresh_file_view,
                        ),
                        color="red-5",
                    ).props("no-caps")
                    any_file_ready = True
                ui.separator()
            elif file_status[2] == -1:
                ui.markdown(f"<b>{file_status[0].replace('_', BACKSLASHCHAR + '_')}:</b> {file_status[1]}")
                ui.button(
                    "Datei entfernen",
                    on_click=partial(
                        delete_file,
                        file_name=file_status[0],
                        user_id=user_id,
                        refresh_file_view=refresh_file_view,
                    ),
                    color="red-5",
                ).props("no-caps")
                ui.separator()
        if any_file_ready:
            ui.button(
                "Alle Dateien herunterladen",
                on_click=partial(download_all, user_id=user_id),
            ).props("no-caps")

    def display_files(user_id):
        read_files(user_id)
        with ui.card().classes("border p-4").style("width: min(60vw, 700px);"):
            display_queue(user_id=user_id)
            display_results(user_id=user_id)

    if ONLINE:
        user_id = str(app.storage.browser.get("id", ""))
    else:
        user_id = "local"

    user_storage[user_id] = {
        "uploaded_files": set(),
        "file_list": [],
        "content": "",
        "content_filename": "",
        "file_in_progress": None,
        "known_errors": set(),
    }

    in_user_tmp_dir = join(ROOT, "data", "in", user_id, "tmp")
    if os.path.exists(in_user_tmp_dir):
        shutil.rmtree(in_user_tmp_dir)

    read_files(user_id)

    with ui.column():
        with ui.header(elevated=True).style("background-color: #0070b4;").props("fit=scale-down").classes("q-pa-xs-xs"):
            ui.image(join(ROOT, "data", "banner.png")).style("height: 90px; width: 443px;")
        with ui.row():
            with ui.column():
                with ui.card().classes("border p-4"):
                    with ui.card().style("width: min(40vw, 400px)"):
                        upload_element = (
                            ui.upload(
                                multiple=True,
                                on_upload=partial(handle_upload, user_id=user_id),
                                on_rejected=handle_reject,
                                label="Dateien auswählen",
                                auto_upload=True,
                                max_file_size=12_000_000_000,
                                max_files=100,
                            )
                            .props('accept="video/*, audio/*, .zip"')
                            .tooltip("Dateien auswählen")
                            .classes("w-full")
                            .style("width: 100%;")
                        )
                        upload_element.on(
                            "uploaded",
                            partial(
                                handle_added,
                                user_id=user_id,
                                upload_element=upload_element,
                                refresh_file_view=refresh_file_view,
                            ),
                        )

                ui.label("")
                ui.timer(
                    2,
                    partial(listen, user_id=user_id, refresh_file_view=refresh_file_view),
                )
                user_storage[user_id]["language"] = ui.select(
                    [LANGUAGES[key] for key in LANGUAGES],
                    value="deutsch",
                    on_change=partial(update_language, user_id),
                    label="Gesprochene Sprache",
                ).style("width: min(40vw, 400px)")
                with (
                    ui.expansion("Vokabular", icon="menu_book")
                    .classes("w-full no-wrap")
                    .style("width: min(40vw, 400px)") as expansion
                ):
                    user_storage[user_id]["textarea"] = ui.textarea(
                        label="Vokabular",
                        placeholder="Zürich\nUster\nUitikon",
                        on_change=partial(update_hotwords, user_id),
                    ).classes("w-full h-full")
                    hotwords = app.storage.user.get(f"{user_id}_vocab", "").strip()
                    if hotwords:
                        user_storage[user_id]["textarea"].value = hotwords
                        expansion.open()
                with (
                    ui.expansion("Informationen", icon="help_outline")
                    .classes("w-full no-wrap")
                    .style("width: min(40vw, 400px)")
                ):
                    ui.label("Diese Prototyp-Applikation wurde vom Statistischen Amt Kanton Zürich entwickelt.")
                ui.button(
                    "Anleitung öffnen",
                    on_click=lambda: ui.open(help_page, new_tab=True),
                ).props("no-caps")

            display_files(user_id=user_id)


if __name__ in {"__main__", "__mp_main__"}:
    if ONLINE:
        ui.run(
            port=8080,
            title="TranscriboZH",
            storage_secret=STORAGE_SECRET,
            favicon=join(ROOT, "data", "logo.png"),
        )

        # run command with ssl certificate
        # ui.run(port=443, reload=False, title="TranscriboZH", ssl_certfile=SSL_CERTFILE, ssl_keyfile=SSL_KEYFILE, storage_secret=STORAGE_SECRET, favicon=ROOT + "logo.png")
    else:
        ui.run(
            title="Transcribo",
            host="127.0.0.1",
            port=8080,
            storage_secret=STORAGE_SECRET,
            favicon=join(ROOT, "data", "logo.png"),
        )


================================================
File: pyproject.toml
================================================
[project]
name = "transcribo"
version = "1.0.0"
description = "Transcribe any audio or video file. Edit and view your transcripts in a standalone HTML editor."
requires-python = "==3.12.7"
dependencies = [
    "torch==2.5.0+cu124",
    "torchaudio==2.5.0+cu124",
    "onnxruntime-gpu==1.18.1",
    "numpy==1.26.3",
    "ffmpeg_python==0.2.0",
    "nicegui==1.4.29",
    "pandas==2.2.2",
    "pyannote.audio==3.1.1",
    "pyannote.core==5.0.0",
    "pyannote.database==5.0.1",
    "pyannote.metrics==3.2.1",
    "pyannote.pipeline==3.0.1",
    "python-dotenv==1.0.1",
    "whisperx==3.1.5",
    "speechbrain==0.5.16",
]

[tool.uv.sources]
torch = { index = "pytorch" }
torchaudio = { index = "pytorch" }
onnxruntime-gpu = { index = "onnx" }

[[tool.uv.index]]
name = "pytorch"
url = "https://download.pytorch.org/whl/cu124"
explicit = true

[[tool.uv.index]]
name = "onnx"
url = "https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/"
explicit = true


# https://docs.astral.sh/ruff/configuration/
[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = ["ALL"]
ignore = [
    "FIX",
    "TD", # disable todo warnings
    "ERA",  # allow commented out code

    "ANN003", # missing kwargs
    "ANN101", # missing self type
    "B006",
    "B008",
    "COM812", # trailing comma
    "D10",  # disabled required docstrings
    "D401",
    "EM102",
    "FBT001",
    "FBT002",
    "PLR0913",
    "PLR2004", # magic
    "RET504",
    "RET505",
    "RET508",
    "S101", # allow assert
    "S104",
    "S603", # subprocess untrusted input
    "SIM102",
    "T201", # print
    "TRY003",
    "W505",
    "ISC001", # recommended to disable for formatting
    "INP001",
    "PT018",
    "G004", # logging f string
]

[tool.ruff.lint.isort]
force-sort-within-sections = true

[tool.ruff.format]
# Like Black, use double quotes for strings.
quote-style = "double"
# Like Black, indent with spaces, rather than tabs.
indent-style = "space"
# Like Black, respect magic trailing commas.
skip-magic-trailing-comma = false
# Like Black, automatically detect the appropriate line ending.
line-ending = "auto"

[tool.basedpyright]
typeCheckingMode = "standard"
pythonVersion = "3.11"
pythonPlatform = "Linux"
# https://github.com/DetachHead/basedpyright?tab=readme-ov-file#pre-commit-hook
venvPath = "."
venv = ".venv"

================================================
File: requirements-mps.txt
================================================
mlx_whisper==0.4.1
torch==2.5.1
torchaudio==2.5.1
torchvision==0.20.1

================================================
File: requirements.txt
================================================
ffmpeg_python==0.2.0
nicegui==1.4.29
pandas==2.2.2
pyannote.audio==3.1.1
pyannote.core==5.0.0
pyannote.database==5.0.1
pyannote.metrics==3.2.1
pyannote.pipeline==3.0.1
python-dotenv==1.0.1
whisperx==3.2.0
speechbrain==0.5.16
numpy==1.26.3
pydub==0.25.1



================================================
File: run_gui.bat
================================================
call conda activate Transcribo
cd C:/Python/audio-transcription
python main.py
pause

================================================
File: run_transcribo.bat
================================================
cd C:/Python/audio-transcription
start /MIN run_worker.bat
start /MIN run_gui.bat

================================================
File: run_worker.bat
================================================
call conda activate Transcribo
cd C:/Python/audio-transcription
python worker.py
pause

================================================
File: startup.sh
================================================
#!/bin/bash

# Start the first process
python worker.py &

# Start the second process
python main.py &

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?

================================================
File: worker.py
================================================
import os
import shutil
import time
import fnmatch
import types
import ffmpeg
import torch
import whisperx
import zipfile
import logging

from os.path import isfile, join, normpath, basename, dirname
from dotenv import load_dotenv
from pyannote.audio import Pipeline

from src.viewer import create_viewer
from src.srt import create_srt
from src.transcription import transcribe, get_prompt
from src.util import time_estimate, isolate_voices

# Load environment variables
load_dotenv()

# Configuration
ONLINE = os.getenv("ONLINE") == "True"
DEVICE = os.getenv("DEVICE")
ROOT = os.getenv("ROOT")
WINDOWS = os.getenv("WINDOWS") == "True"
BATCH_SIZE = int(os.getenv("BATCH_SIZE"))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if WINDOWS:
    os.environ["PATH"] += os.pathsep + "ffmpeg/bin"
    os.environ["PATH"] += os.pathsep + "ffmpeg"
    os.environ["PYANNOTE_CACHE"] = join(ROOT, "models")
    os.environ["HF_HOME"] = join(ROOT, "models")


def report_error(file_name, file_name_error, user_id, text=""):
    logger.error(text)
    error_dir = join(ROOT, "data", "error", user_id)
    os.makedirs(error_dir, exist_ok=True)
    error_file = file_name_error + ".txt"
    with open(error_file, "w") as f:
        f.write(text)
    shutil.move(file_name, file_name_error)


def oldest_files(folder):
    matches = []
    times = []
    for root, _, filenames in os.walk(folder):
        for filename in fnmatch.filter(filenames, "*.*"):
            file_path = join(root, filename)
            matches.append(file_path)
            times.append(os.path.getmtime(file_path))
    return [m for _, m in sorted(zip(times, matches))]


def transcribe_file(file_name, multi_mode=False, multi_mode_track=None, audio_files=None, language="de"):
    data = None
    estimated_time = 0
    progress_file_name = ""

    file = basename(file_name)
    user_id = normpath(dirname(file_name)).split(os.sep)[-1]
    file_name_error = join(ROOT, "data", "error", user_id, file)
    file_name_out = join(ROOT, "data", "out", user_id, file + ".mp4")

    # Clean up worker directory
    if not multi_mode:
        worker_user_dir = join(ROOT, "data", "worker", user_id)
        if os.path.exists(worker_user_dir):
            try:
                shutil.rmtree(worker_user_dir)
            except OSError as e:
                logger.error(f"Could not remove folder: {worker_user_dir}. Error: {e}")

    # Create output directory
    if not multi_mode:
        output_user_dir = join(ROOT, "data", "out", user_id)
        os.makedirs(output_user_dir, exist_ok=True)

    # Estimate run time
    try:
        time.sleep(2)
        estimated_time, run_time = time_estimate(file_name, ONLINE)
        if run_time == -1:
            report_error(file_name, file_name_error, user_id, "Datei konnte nicht gelesen werden")
            return data, estimated_time, progress_file_name
    except Exception as e:
        logger.exception("Error estimating run time")
        report_error(file_name, file_name_error, user_id, "Datei konnte nicht gelesen werden")
        return data, estimated_time, progress_file_name

    if not multi_mode:
        worker_user_dir = join(ROOT, "data", "worker", user_id)
        os.makedirs(worker_user_dir, exist_ok=True)
        progress_file_name = join(worker_user_dir, f"{estimated_time}_{int(time.time())}_{file}")
        try:
            with open(progress_file_name, "w") as f:
                f.write("")
        except OSError as e:
            logger.error(f"Could not create progress file: {progress_file_name}. Error: {e}")

    # Check if file has a valid audio stream
    try:
        if not ffmpeg.probe(file_name, select_streams="a")["streams"]:
            report_error(
                file_name,
                file_name_error,
                user_id,
                "Die Tonspur der Datei konnte nicht gelesen werden",
            )
            return data, estimated_time, progress_file_name
    except ffmpeg.Error as e:
        logger.exception("ffmpeg error during probing")
        report_error(
            file_name,
            file_name_error,
            user_id,
            "Die Tonspur der Datei konnte nicht gelesen werden",
        )
        return data, estimated_time, progress_file_name

    # Process audio
    if not multi_mode:
        # Convert and filter audio
        exit_status = os.system(
            f'ffmpeg -y -i "{file_name}" -filter:v scale=320:-2 -af "lowpass=3000,highpass=200" "{file_name_out}"'
        )
        if exit_status == 256:
            exit_status = os.system(
                f'ffmpeg -y -i "{file_name}" -c:v copy -af "lowpass=3000,highpass=200" "{file_name_out}"'
            )
        if not exit_status == 0:
            logger.exception("ffmpeg error during audio processing")
            file_name_out = file_name  # Fallback to original file

    else:
        file_name_out = file_name

    # Load hotwords
    hotwords = []
    hotwords_file = join(ROOT, "data", "in", user_id, "hotwords.txt")
    if isfile(hotwords_file):
        with open(hotwords_file, "r") as h:
            hotwords = h.read().splitlines()

    # Transcribe
    try:
        data = transcribe(
            file_name_out,
            model,
            diarize_model,
            DEVICE,
            None,
            add_language=(
                False if DEVICE == "mps" else True
            ),  # on MPS is rather slow and unreliable, but you can try with setting this to true
            hotwords=hotwords,
            multi_mode_track=multi_mode_track,
            language=language,
        )
    except Exception as e:
        logger.exception("Transcription failed")
        report_error(file_name, file_name_error, user_id, "Transkription fehlgeschlagen")

    return data, estimated_time, progress_file_name


if __name__ == "__main__":
    WHISPER_DEVICE = "cpu" if DEVICE == "mps" else DEVICE
    if WHISPER_DEVICE == "cpu":
        compute_type = "float32"
    else:
        compute_type = "float16"

    # Load models
    whisperx_model = (
        "tiny.en" if DEVICE == "mps" else "large-v3"
    )  # we can load a really small one for mps, because we use mlx_whisper later and only need whisperx for diarization and alignment
    if ONLINE:
        model = whisperx.load_model(whisperx_model, WHISPER_DEVICE, compute_type=compute_type)
    else:
        model = whisperx.load_model(
            whisperx_model,
            WHISPER_DEVICE,
            compute_type=compute_type,
            download_root=join("models", "whisperx"),
        )

    model.model.get_prompt = types.MethodType(get_prompt, model.model)
    diarize_model = Pipeline.from_pretrained(
        "pyannote/speaker-diarization", use_auth_token=os.getenv("HF_AUTH_TOKEN")
    ).to(torch.device(DEVICE))

    # Create necessary directories
    for directory in ["data/in/", "data/out/", "data/error/", "data/worker/"]:
        os.makedirs(join(ROOT, directory), exist_ok=True)

    disclaimer = (
        "This transcription software (the Software) incorporates the open-source model Whisper Large v3 "
        "(the Model) and has been developed according to and with the intent to be used under Swiss law. "
        "Please be aware that the EU Artificial Intelligence Act (EU AI Act) may, under certain circumstances, "
        "be applicable to your use of the Software. You are solely responsible for ensuring that your use of "
        "the Software as well as of the underlying Model complies with all applicable local, national and "
        "international laws and regulations. By using this Software, you acknowledge and agree (a) that it is "
        "your responsibility to assess which laws and regulations, in particular regarding the use of AI "
        "technologies, are applicable to your intended use and to comply therewith, and (b) that you will hold "
        "us harmless from any action, claims, liability or loss in respect of your use of the Software."
    )
    logger.info(disclaimer)
    logger.info("Worker ready")

    while True:
        try:
            files_sorted_by_date = oldest_files(join(ROOT, "data", "in"))
        except Exception as e:
            logger.exception("Error accessing input directory")
            time.sleep(1)
            continue

        for file_name in files_sorted_by_date:
            file = basename(file_name)
            user_id = normpath(dirname(file_name)).split(os.sep)[-1]

            if file == "hotwords.txt" or file == "language.txt":
                continue

            file_name_viewer = join(ROOT, "data", "out", user_id, file + ".html")

            # Skip files that have already been processed
            if not isfile(file_name) or isfile(file_name_viewer):
                continue

            language_file = join(ROOT, "data", "in", user_id, "language.txt")
            if isfile(language_file):
                with open(language_file, "r") as h:
                    language = h.read()
            else:
                language = "de"

            # Check if it's a zip file
            if file_name.lower().endswith(".zip"):
                try:
                    zip_extract_dir = join(ROOT, "data", "worker", "zip")
                    shutil.rmtree(zip_extract_dir, ignore_errors=True)
                    os.makedirs(zip_extract_dir, exist_ok=True)

                    with zipfile.ZipFile(file_name, "r") as zip_ref:
                        zip_ref.extractall(zip_extract_dir)

                    multi_mode = True
                    data_parts = []
                    estimated_time = 0
                    data = []
                    file_parts = []

                    # Collect files from zip
                    for root, _, filenames in os.walk(zip_extract_dir):
                        audio_files = [fn for fn in filenames if fnmatch.fnmatch(fn, "*.*")]
                        for filename in audio_files:
                            file_path = join(root, filename)
                            est_time_part, _ = time_estimate(file_path, ONLINE)
                            estimated_time += est_time_part

                    progress_file_name = join(
                        ROOT,
                        "data",
                        "worker",
                        user_id,
                        f"{estimated_time}_{int(time.time())}_{file}",
                    )
                    with open(progress_file_name, "w") as f:
                        f.write("")

                    isolate_voices([join(root, filename) for filename in audio_files])

                    # Transcribe each file
                    for track, filename in enumerate(audio_files):
                        file_path = join(root, filename)
                        file_parts.append(f'-i "{file_path}"')
                        data_part, _, _ = transcribe_file(file_path, multi_mode=True, multi_mode_track=track, language=language)
                        data_parts.append(data_part)

                    # Merge data
                    while any(data_parts):
                        earliest = min(
                            [(i, dp[0]) for i, dp in enumerate(data_parts) if dp],
                            key=lambda x: x[1]["start"],
                            default=(None, None),
                        )
                        if earliest[0] is None:
                            break

                        data.append(earliest[1])
                        data_parts[earliest[0]].pop(0)

                    # Merge audio files
                    output_audio = join(ROOT, "data", "worker", "zip", "tmp.mp4")
                    ffmpeg_input = " ".join(file_parts)
                    ffmpeg_cmd = f'ffmpeg {ffmpeg_input} -filter_complex amix=inputs={len(file_parts)}:duration=first "{output_audio}"'
                    os.system(ffmpeg_cmd)

                    # Process merged audio
                    file_name_out = join(ROOT, "data", "out", user_id, file + ".mp4")
                    exit_status = os.system(
                        f'ffmpeg -y -i "{output_audio}" -filter:v scale=320:-2 -af "lowpass=3000,highpass=200" "{file_name_out}"'
                    )
                    if exit_status == 256:
                        exit_status = os.system(
                            f'ffmpeg -y -i "{output_audio}" -c:v copy -af "lowpass=3000,highpass=200" "{file_name_out}"'
                        )
                    if not exit_status == 0:
                        logger.exception("ffmpeg error during audio processing")
                        file_name_out = output_audio  # Fallback to original fileue)

                    shutil.rmtree(zip_extract_dir, ignore_errors=True)
                except Exception as e:
                    logger.exception("Transcription failed for zip file")
                    report_error(
                        file_name,
                        join(ROOT, "data", "error", user_id, file),
                        user_id,
                        "Transkription fehlgeschlagen",
                    )
                    continue
            else:
                # Single file transcription
                data, estimated_time, progress_file_name = transcribe_file(file_name, language=language)

            if data is None:
                continue

            # Generate outputs
            try:
                file_name_out = join(ROOT, "data", "out", user_id, file + ".mp4")

                srt = create_srt(data)
                viewer = create_viewer(data, file_name_out, True, False, ROOT, language)

                file_name_srt = join(ROOT, "data", "out", user_id, file + ".srt")
                with open(file_name_viewer, "w", encoding="utf-8") as f:
                    f.write(viewer)
                with open(file_name_srt, "w", encoding="utf-8") as f:
                    f.write(srt)

                logger.info(f"Estimated Time: {estimated_time}")
            except Exception as e:
                logger.exception("Error creating editor")
                report_error(
                    file_name,
                    join(ROOT, "data", "error", user_id, file),
                    user_id,
                    "Fehler beim Erstellen des Editors",
                )

            if progress_file_name and os.path.exists(progress_file_name):
                os.remove(progress_file_name)
            if DEVICE == "mps":
                print("Exiting worker to prevent memory leaks with MPS...")
                exit(0)  # Due to memory leak problems, we restart the worker after each transcription

            break  # Process one file at a time

        time.sleep(1)


================================================
File: .dockerignore
================================================
.venv

================================================
File: .env_example
================================================
HF_AUTH_TOKEN = "hf_putyourtokenhere"
ONLINE = True
SSL_CERTFILE = "path/to/certfile"
SSL_KEYFILE = "path/to/keyfile"
ROOT = ""
WINDOWS = False
DEVICE = "cuda"
ADDITIONAL_SPEAKERS = 4
STORAGE_SECRET = "this is my secret"
BATCH_SIZE = 4

================================================
File: data/const.py
================================================
# Source: https://github.com/openai/whisper/discussions/928

data_leaks = {
    "en": [
        " www.mooji.org",
    ],
    "nl": [
        " Ondertitels ingediend door de Amara.org gemeenschap",
        " Ondertiteld door de Amara.org gemeenschap",
        " Ondertiteling door de Amara.org gemeenschap",
    ],
    "de": [
        " Untertitelung aufgrund der Amara.org-Community Untertitel im Auftrag des ZDF für funk, 2017",
        " Untertitel von Stephanie Geiges",
        " Untertitel der Amara.org-Community",
        " Untertitel im Auftrag des ZDF, 2017",
        " Untertitel im Auftrag des ZDF, 2020",
        " Untertitel im Auftrag des ZDF, 2018",
        " Untertitel im Auftrag des ZDF, 2021",
        " Untertitelung im Auftrag des ZDF, 2021",
        " Copyright WDR 2021",
        " Copyright WDR 2020",
        " Copyright WDR 2019",
        " SWR 2021",
        " SWR 2020",
    ],
    "fr": [
        " Sous-titres réalisés para la communauté d'Amara.org",
        " Sous-titres réalisés par la communauté d'Amara.org",
        " Sous-titres fait par Sous-titres par Amara.org",
        " Sous-titres réalisés par les SousTitres d'Amara.org",
        " Sous-titres par Amara.org",
        " Sous-titres par la communauté d'Amara.org",
        " Sous-titres réalisés pour la communauté d'Amara.org",
        " Sous-titres réalisés par la communauté de l'Amara.org",
        " Sous-Titres faits par la communauté d'Amara.org",
        " Sous-titres par l'Amara.org",
        " Sous-titres fait par la communauté d'Amara.org Sous-titrage ST' 501",
        " Sous-titrage ST'501",
        " Cliquez-vous sur les sous-titres et abonnez-vous à la chaîne d'Amara.org",
        " ?? par SousTitreur.com",
    ],
    "it": [
        " Sottotitoli creati dalla comunità Amara.org",
        " Sottotitoli di Sottotitoli di Amara.org",
        " Sottotitoli e revisione al canale di Amara.org",
        " Sottotitoli e revisione a cura di Amara.org",
        " Sottotitoli e revisione a cura di QTSS",
        " Sottotitoli e revisione a cura di QTSS.",
        " Sottotitoli a cura di QTSS",
    ],
    "es": [
        " Subtítulos realizados por la comunidad de Amara.org",
        " Subtitulado por la comunidad de Amara.org",
        " Subtítulos por la comunidad de Amara.org",
        " Subtítulos creados por la comunidad de Amara.org",
        " Subtítulos en español de Amara.org",
        " Subtítulos hechos por la comunidad de Amara.org",
        " Subtitulos por la comunidad de Amara.org Más información www.alimmenta.com",
        " www.mooji.org",
    ],
    "gl": [" Subtítulos realizados por la comunidad de Amara.org"],
    "pt": [
        " Legendas pela comunidade Amara.org",
        " Legendas pela comunidade de Amara.org",
        " Legendas pela comunidade do Amara.org",
        " Legendas pela comunidade das Amara.org",
        " Transcrição e Legendas pela comunidade de Amara.org",
    ],
    "la": [" Sottotitoli creati dalla comunità Amara.org", " Sous-titres réalisés para la communauté d'Amara.org"],
    "ln": [" Sous-titres réalisés para la communauté d'Amara.org"],
    "pl": [
        " Napisy stworzone przez spolecznosc Amara.org",
        " Napisy wykonane przez spolecznosc Amara.org",
        " Zdjecia i napisy stworzone przez spolecznosc Amara.org",
        " napisy stworzone przez spolecznosc Amara.org",
        " Tlumaczenie i napisy stworzone przez spolecznosc Amara.org",
        " Napisy stworzone przez spolecznosci Amara.org",
        " Tlumaczenie stworzone przez spolecznosc Amara.org",
        " Napisy robione przez spolecznosc Amara.org www.multi-moto.eu",
    ],
    "ru": [" ???????? ????????? ?.???????? ????????? ?.???????"],
    "tr": [
        " Yorumlariniziza abone olmayi unutmayin.",
    ],
    "su": [" Sottotitoli creati dalla comunità Amara.org"],
    "zh": ["???Amara.org????", "?????Amara.org????"],
}

# Source: https://github.com/openai/whisper/blob/main/whisper/tokenizer.py

LANGUAGES = {
    "de": "deutsch",
    "fr": "französisch",
    "it": "italienisch",
    "en": "english",
    "zh": "chinese",
    "es": "spanish",
    "ru": "russian",
    "ko": "korean",
    "ja": "japanese",
    "pt": "portuguese",
    "tr": "turkish",
    "pl": "polish",
    "ca": "catalan",
    "nl": "dutch",
    "ar": "arabic",
    "sv": "swedish",
    "id": "indonesian",
    "hi": "hindi",
    "fi": "finnish",
    "vi": "vietnamese",
    "he": "hebrew",
    "uk": "ukrainian",
    "el": "greek",
    "ms": "malay",
    "cs": "czech",
    "ro": "romanian",
    "da": "danish",
    "hu": "hungarian",
    "ta": "tamil",
    "no": "norwegian",
    "th": "thai",
    "ur": "urdu",
    "hr": "croatian",
    "bg": "bulgarian",
    "lt": "lithuanian",
    "la": "latin",
    "mi": "maori",
    "ml": "malayalam",
    "cy": "welsh",
    "sk": "slovak",
    "te": "telugu",
    "fa": "persian",
    "lv": "latvian",
    "bn": "bengali",
    "sr": "serbian",
    "az": "azerbaijani",
    "sl": "slovenian",
    "kn": "kannada",
    "et": "estonian",
    "mk": "macedonian",
    "br": "breton",
    "eu": "basque",
    "is": "icelandic",
    "hy": "armenian",
    "ne": "nepali",
    "mn": "mongolian",
    "bs": "bosnian",
    "kk": "kazakh",
    "sq": "albanian",
    "sw": "swahili",
    "gl": "galician",
    "mr": "marathi",
    "pa": "punjabi",
    "si": "sinhala",
    "km": "khmer",
    "sn": "shona",
    "yo": "yoruba",
    "so": "somali",
    "af": "afrikaans",
    "oc": "occitan",
    "ka": "georgian",
    "be": "belarusian",
    "tg": "tajik",
    "sd": "sindhi",
    "gu": "gujarati",
    "am": "amharic",
    "yi": "yiddish",
    "lo": "lao",
    "uz": "uzbek",
    "fo": "faroese",
    "ht": "haitian creole",
    "ps": "pashto",
    "tk": "turkmen",
    "nn": "nynorsk",
    "mt": "maltese",
    "sa": "sanskrit",
    "lb": "luxembourgish",
    "my": "myanmar",
    "bo": "tibetan",
    "tl": "tagalog",
    "mg": "malagasy",
    "as": "assamese",
    "tt": "tatar",
    "haw": "hawaiian",
    "ln": "lingala",
    "ha": "hausa",
    "ba": "bashkir",
    "jw": "javanese",
    "su": "sundanese",
    "yue": "cantonese",
}

INVERTED_LANGUAGES = {v: k for k, v in LANGUAGES.items()}


================================================
File: data/logo.txt
================================================
data:image/png;base64,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


================================================
File: docker_aargau/README.md
================================================
A big thank you to the people at AI + Machine Learning Canton of Zurich for this wonderful tool. We at the courts of the canton of Aargau love it.

As a small improvement, we wanted to share our dockerized version with you. Both files need to be in the project root and the .env file needs to be set up if you want to use it.

================================================
File: docker_aargau/bootup.sh
================================================
# Copyright (c) 2024 Gerichte Kanton Aargau

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated 
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to 
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to 
# whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the 
# Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR 
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE 
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR 
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
# DEALINGS IN THE SOFTWARE.

hap run python worker.py
hap run python main.py
hap status
hap logs 2
hap logs 1 -f

================================================
File: docker_aargau/dockerfile
================================================
# Copyright (c) 2024 Gerichte Kanton Aargau

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated 
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to 
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to 
# whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the 
# Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR 
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE 
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR 
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
# DEALINGS IN THE SOFTWARE.

FROM python:3.10

ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/lib/x86_64-linux-gnu/

WORKDIR /usr/src/app
COPY . .

RUN apt-get update
RUN apt-get install ffmpeg wget -y

RUN wget https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/cuda-keyring_1.1-1_all.deb
RUN dpkg -i cuda-keyring_1.1-1_all.deb

RUN apt-get update

RUN apt-get -y install cudnn9-cuda-12

RUN pip3 install torch torchvision torchaudio
RUN pip3 install -r requirements.txt
RUN pip3 uninstall onnxruntime --yes
RUN pip3 install --force-reinstall onnxruntime-gpu
RUN pip3 install --force-reinstall -v "numpy==1.26.3"

RUN pip3 install ffprobe
RUN pip3 install hapless

CMD [ "bash", "./bootup.sh" ]

================================================
File: src/help.py
================================================
import os
from nicegui import ui
from dotenv import load_dotenv


load_dotenv()

ONLINE = os.getenv("ONLINE") == "True"
ROOT = os.getenv("ROOT")


@ui.page("/help")
def help():
    with ui.column():
        with ui.header(elevated=True).style("background-color: #0070b4;").props(
            "fit=scale-down"
        ).classes("q-pa-xs-xs"):
            ui.image(ROOT + "data/banner.png").style("height: 90px; width: 443px;")
        with ui.expansion("Dateien hochladen", icon="upload_file").classes(
            "w-full no-wrap"
        ).style("width: min(80vw, 800px)"):
            ui.markdown(
                '''Du kannst eine oder mehrere Dateien zum Transkribieren hochladen. Drücke dazu auf den "+"-Knopf oder ziehe die Dateien in den Upload-Bereich. Das Transkriptionsmodell (Whisper) von Transcribo kann die meisten gängigen Video- und Audio-Dateiformate verarbeiten. Eine Liste aller unterstützten Formate findest du hier: [ffmpeg.org](https://www.ffmpeg.org/general.html#Supported-File-Formats_002c-Codecs-or-Features)
                
Beim Hochladen einer ZIP-Datei werden die Audio-Spuren der darin enthaltenen Dateien kombiniert.
                '''
            )
            ui.image(ROOT + "help/upload.png").style("width: min(40vw, 400px)")
        with ui.expansion("Editor öffnen und speichern", icon="open_in_new").classes(
            "w-full no-wrap"
        ).style("width: min(80vw, 800px)"):
            ui.markdown(
                """Der Editor kann entweder lokal oder auf dem Server geöffnet werden. Wenn du den Editor auf dem Server öffnest, werden deine Änderungen dort gespeichert und das initiale Transkript wird überschrieben. Wenn du den Editor lokal öffnest, wird eine Editor-Datei in deinem Download-Ordner abgelegt. Jedes Mal, wenn du auf "speichern" klickst, wird eine neue Editor-Datei in deinem Download-Ordner erzeugt. Dadurch hast du alle deine Änderungen auf deinem Gerät und behältst alte Versionen."""
            )
            ui.image(ROOT + "help/open.png").style("width: min(40vw, 400px)")
            ui.markdown(
                "Achtung: Transcribo speichert nicht automatisch, bitte oft zwischenspeichern!"
            )
            ui.image(ROOT + "help/editor_buttons_save.png").style(
                "width: min(40vw, 400px)"
            )
        with ui.expansion("Editor Grundfunktionen", icon="edit").classes(
            "w-full no-wrap"
        ).style("width: min(80vw, 800px)"):
            ui.markdown("""#####Sprachsegmente
Im Editor ist das Transkript in einzelne Sprachsegmente aufgetrennt. Ein Sprachsegment umfasst in etwa das, was ein Sprecher zwischen zwei Pausen gesagt hat. Wir trennen sie so auf, damit man den Sprecher für jedes Segment einzeln anpassen kann. Beim Export des Textes oder beim Erstellen eines Viewers werden die Sprachsegmente desselben Sprechers wieder zusammengefügt.

Mit den gekennzeichneten Knöpfen kann ein Sprachsegment hinzugefügt oder entfernt werden.""")
            ui.image(ROOT + "help/segment_add_delete.png").style(
                "width: min(40vw, 400px)"
            )
            ui.markdown("""#####Sprecher
Sprecher können im Editor auf der linken Seite unbenannt werden.""")
            ui.image(ROOT + "help/editor_buttons_speaker.png").style(
                "width: min(40vw, 400px)"
            )
            ui.markdown("Bei jedem Sprachsegment kann der Sprecher geändert werden.")
            ui.image(ROOT + "help/segment_speaker.png").style("width: min(40vw, 400px)")
            ui.markdown("""#####Wiedergabe
Die Wiedergabegeschwindigkeit einer Aufnahme kann im Player angepasst werden.""")
            ui.image(ROOT + "help/player_speed.png").style("width: min(40vw, 400px)")
            ui.markdown("""#####Zeitverzögerung
Wenn du auf ein Sprachsegment klickst, springt das Video an die entsprechende Stelle. Falls du nicht direkt beim Segment beginnen möchtest, kannst du auf der linken Seite eine Verzögerungszeit angeben.""")
        with ui.expansion("Editor Tastenkombinationen", icon="keyboard").classes(
            "w-full no-wrap"
        ).style("width: min(80vw, 800px)"):
            ui.markdown("""Du kannst die folgenden Tastenkombinationen im Editor verwenden.\n
**Tabulator:** Zum nächsten Sprachsegment springen\n
**Shift + Tabulator:** Zum vorhergehenden Sprachsegment springen\n
**Ctrl + Pfeiltasten:** Von Wort zu Wort springen\n
**Shift + Ctrl + Pfeiltasten:** Wörter markieren\n
**Ctrl + Space:** Video Start/Stop (funktioniert zur Zeit nur im offline Editor)""")
        with ui.expansion("Fremdsprachen", icon="translate").classes(
            "w-full no-wrap"
        ).style("width: min(80vw, 800px)"):
            ui.markdown(
                'Transcribo markiert alle Sprachsegmente, die weder auf Deutsch, Schweizerdeutsch oder Englisch sind, als "Fremdsprache". Du kannst falsch erkannte Sprachsegmente korrigieren.'
            )
            ui.image(ROOT + "help/segment_language.png").style(
                "width: min(40vw, 400px)"
            )
            ui.markdown(
                "Beim Export als Textdatei oder Viewer kannst du auswählen, ob Fremdsprachen entfernt werden sollen."
            )
            ui.image(ROOT + "help/editor_buttons_language.png").style(
                "width: min(40vw, 400px)"
            )
        with ui.expansion("Viewer", icon="visibility").classes("w-full no-wrap").style(
            "width: min(80vw, 800px)"
        ):
            ui.markdown("Im Editor kannst du einen Viewer erstellen.")
            ui.image(ROOT + "help/editor_buttons_viewer.png").style(
                "width: min(40vw, 400px)"
            )
            ui.markdown(
                "Der Viewer zeigt aufeinanderfolgende Sprachsegmente des gleichen Sprechers kompakt an. In Klammern hinter dem Namen des Sprechenden wird der Zeitstempel des ersten Sprachsegments angezeigt. Der Viewer ermöglicht es, das Transkript übersichtlich zu lesen und mit der Aufnahme zu vergleichen. Der Text kann nicht mehr bearbeitet werden."
            )
            ui.image(ROOT + "help/viewer.png").style("width: min(40vw, 400px)")
        with ui.expansion("Textexport", icon="description").classes(
            "w-full no-wrap"
        ).style("width: min(80vw, 800px)"):
            ui.markdown(
                "Als Alternative zum Viewer kann das Transkript auch als Rohtext exportiert werden. Aufeinanderfolgende Sprachsegmente des gleichen Sprechers werden dabei ebenfalls kombiniert."
            )
            ui.image(ROOT + "help/editor_buttons_text.png").style(
                "width: min(40vw, 400px)"
            )
        with ui.expansion("Datenspeicherung", icon="save").classes(
            "w-full no-wrap"
        ).style("width: min(80vw, 800px)"):
            if ONLINE:
                ui.markdown(
                    "Wenn du eine Datei hochlädst, kannst du später wieder auf das fertige Transkript zugreifen. Dafür musst du mit demselben Windows-Useraccount, am selben Rechner und mit demselben Browser auf Transcribo zugreifen. Alle deine Transkripte bleiben erhalten, sofern du sie nicht selbst löschst. Wenn du jedoch 30 Tage lang nicht auf Transcribo zugreifst, werden deine Transkripte entfernt. Bitte lade den Editor herunter, um deine Transkripte langfristig zu speichern."
                )
            else:
                ui.markdown(
                    "Wenn du eine Datei hochlädst, kannst du später wieder auf das fertige Transkript zugreifen. Dafür musst du mit demselben Windows-Useraccount, am selben Rechner und mit demselben Browser auf Transcribo zugreifen. Alle deine Transkripte bleiben erhalten, sofern du sie nicht selbst löschst."
                )
        with ui.expansion("Vokabular", icon="menu_book").classes(
            "w-full no-wrap"
        ).style("width: min(80vw, 800px)"):
            ui.markdown(
                'Im Menü "Vokabular" kannst du Wörter zum bestehenden Vokabular hinzufügen. Das hilft zum Beispiel, selten verwendete Namen oder Bezeichnungen besser zu transkribieren. Du kannst die Wörter durch Leerzeichen getrennt oder zeilenweise angeben.'
            )


================================================
File: src/srt.py
================================================
import datetime, copy


def create_srt(data):
    data_srt = []
    max_length = 60
    hard_max_length = 80

    # Try to split segments into sub-segments of max. max_length characters.
    # Segments shorter than max_length characters are not changed.
    for segment in data:
        segment["text"] = segment["text"]
        text = segment["text"].strip()
        length = len(text.replace(" ", ""))
        if length < max_length:
            data_srt.append(copy.deepcopy(segment))
        else:
            target_number_of_splits = int(length / (max_length)) + 1
            target_length = length / target_number_of_splits
            word_index = 0

            while word_index < len(segment["words"]):
                new_segment = {"start": -1, "end": -1, "words": [], "text": ""}
                while word_index < len(segment["words"]):
                    # Add a word to the current new_segment.
                    if (
                        new_segment["start"] == -1
                        and "start" in segment["words"][word_index]
                    ):
                        new_segment["start"] = segment["words"][word_index]["start"]
                    if "end" in segment["words"][word_index]:
                        new_segment["end"] = segment["words"][word_index]["end"]

                    new_segment["words"].append(
                        copy.deepcopy(segment["words"][word_index])
                    )
                    new_segment["text"] += segment["words"][word_index]["word"] + " "

                    # Check if word_index is a good position to start a new segment.
                    word_index += 1
                    current_length = len(new_segment["text"].replace(" ", ""))
                    # If hard_max_length will be reached after the next word, start a new segment.
                    if word_index >= len(segment["words"]) or hard_max_length < (
                        current_length + len(segment["words"][word_index]["word"])
                    ):
                        break
                    # Do not start a new segment towards the end.
                    if word_index + 2 > len(segment["words"]):
                        continue
                    # Allow early starting of a new segment if the current word contains ','/'»' or the next word contains 'und'/'oder'/'«'.
                    if current_length > target_length * 0.5 and (
                        "," in segment["words"][word_index - 1]["word"]
                        or "«" in segment["words"][word_index]["word"]
                        or "»" in segment["words"][word_index - 1]["word"]
                        or "und" in segment["words"][word_index]["word"]
                        or "oder" in segment["words"][word_index]["word"]
                    ):
                        break
                    if abs(target_length - current_length) < abs(
                        target_length
                        - (current_length + len(segment["words"][word_index]["word"]))
                    ):
                        break
                data_srt.append(copy.deepcopy(new_segment))

    # Try to increase display times of segments to 13 characters per second if possible.
    for i, segment in enumerate(data_srt):
        length = len(segment["text"].replace(" ", ""))
        display_time = segment["end"] - segment["start"]

        if (
            i + 1 < len(data_srt)
            and (length / 13) < display_time
            and data_srt[i + 1]["start"] > segment["end"]
        ):
            optimal_time_increase = display_time - (length / 13)
            segment["end"] = min(
                data_srt[i + 1]["start"], segment["end"] + optimal_time_increase
            )

    text = ""
    for i, segment in enumerate(data_srt):
        text += str(i + 1) + "\n"
        text += (
            "{:0>8}".format(str(datetime.timedelta(seconds=int(segment["start"]))))
            + ","
            + str(int(segment["start"] % 1 * 1000)).ljust(3, "0")
            + " --> "
            + "{:0>8}".format(str(datetime.timedelta(seconds=int(segment["end"]))))
            + ","
            + str(int(segment["end"] % 1 * 1000)).ljust(3, "0")
            + "\n"
        )

        segment_text = segment["text"].strip()
        length = len(segment_text.replace(" ", ""))
        if length > 40:
            segment_tokens = segment_text.split(" ")
            segment_tokens_lengths = [len(token) for token in segment_tokens]
            new_line_position = 0
            best_difference = 10000
            for index in range(len(segment_tokens_lengths)):
                difference = abs(
                    sum(segment_tokens_lengths[index:])
                    - sum(segment_tokens_lengths[:index])
                )
                if best_difference > difference:
                    best_difference = difference
                    new_line_position = index
            segment_text = (
                " ".join(segment_tokens[:new_line_position])
                + "\n"
                + " ".join(segment_tokens[new_line_position:])
            )

        text += f"{segment_text}\n\n"

    text = text.replace("ß", "ss")
    return text


================================================
File: src/transcription.py
================================================
import os
import torch
import pandas as pd
import time
import whisperx
from whisperx.audio import SAMPLE_RATE, log_mel_spectrogram, N_SAMPLES

from data.const import data_leaks

DEVICE = os.getenv("DEVICE")


def get_prompt(self, tokenizer, previous_tokens, without_timestamps, prefix):
    prompt = []

    if previous_tokens or prefix:
        prompt.append(tokenizer.sot_prev)
        if prefix:
            hotwords_tokens = tokenizer.encode(" " + prefix.strip())
            if len(hotwords_tokens) >= self.max_length // 2:
                hotwords_tokens = hotwords_tokens[: self.max_length // 2 - 1]
            prompt.extend(hotwords_tokens)
        if prefix and previous_tokens:
            prompt.extend(previous_tokens[-(self.max_length // 2 - 1) :])

    prompt.extend(tokenizer.sot_sequence)

    if without_timestamps:
        prompt.append(tokenizer.no_timestamps)

    return prompt


def detect_language(audio, model):
    model_n_mels = model.model.feat_kwargs.get("feature_size")
    segment = log_mel_spectrogram(
        audio[:N_SAMPLES],
        n_mels=model_n_mels if model_n_mels is not None else 80,
        padding=0 if audio.shape[0] >= N_SAMPLES else N_SAMPLES - audio.shape[0],
    )
    encoder_output = model.model.encode(segment)
    results = model.model.model.detect_language(encoder_output)
    language_token, language_probability = results[0][0]
    language = language_token[2:-2]
    return (language, language_probability)


def transcribe(
    complete_name,
    model,
    diarize_model,
    device,
    num_speaker,
    add_language=False,
    hotwords=[],
    batch_size=4,
    multi_mode_track=None,
    language="de",
):
    torch.cuda.empty_cache()

    # Convert audio given a file path.
    audio = whisperx.load_audio(complete_name)

    start_time = time.time()

    if len(hotwords) > 0:
        model.options = model.options._replace(prefix=" ".join(hotwords))
    print("Transcribing...")
    if DEVICE == "mps":
        import mlx_whisper

        decode_options = {"language": None, "prefix": " ".join(hotwords)}

        result1 = mlx_whisper.transcribe(
            complete_name,
            path_or_hf_repo="mlx-community/whisper-large-v3-mlx",
            **decode_options,
        )
    else:
        result1 = model.transcribe(audio, batch_size=batch_size, language=language)

    print(f"Transcription took {time.time() - start_time:.2f} seconds.")
    if len(hotwords) > 0:
        model.options = model.options._replace(prefix=None)

    # Align whisper output.
    model_a, metadata = whisperx.load_align_model(language_code=result1["language"], device=device)
    start_aligning = time.time()

    print("Aligning...")
    result2 = whisperx.align(
        result1["segments"],
        model_a,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )

    print(f"Alignment took {time.time() - start_aligning:.2f} seconds.")

    if add_language:
        start_language = time.time()
        print("Adding language...")
        for segment in result2["segments"]:
            start = (int(segment["start"]) * 16_000) - 8_000
            end = ((int(segment["end"]) + 1) * 16_000) + 8_000
            segment_audio = audio[start:end]
            if DEVICE == "mps":
                ## This is a workaround to use the whisper model in mps, it doesn't have "detect language" method
                decode_options = {"language": None, "prefix": " ".join(hotwords)}
                language = mlx_whisper.transcribe(
                    segment_audio, path_or_hf_repo="mlx-community/whisper-large-v3-mlx", **decode_options
                )
                segment["language"] = language["language"]
            else:
                detected_language, language_probability = detect_language(segment_audio, model)
                segment["language"] = detected_language if language_probability > 0.85 else language
        print(f"Adding language took {time.time() - start_language:.2f} seconds.")

    # Diarize and assign speaker labels.
    start_diarize = time.time()
    print("Diarizing...")
    audio_data = {
        "waveform": torch.from_numpy(audio[None, :]),
        "sample_rate": SAMPLE_RATE,
    }

    if multi_mode_track is None:
        segments = diarize_model(audio_data, num_speakers=num_speaker)

        diarize_df = pd.DataFrame(segments.itertracks(yield_label=True), columns=["segment", "label", "speaker"])
        diarize_df["start"] = diarize_df["segment"].apply(lambda x: x.start)
        diarize_df["end"] = diarize_df["segment"].apply(lambda x: x.end)
        result3 = whisperx.assign_word_speakers(diarize_df, result2)
    else:
        for segment in result2["segments"]:
            segment["speaker"] = "SPEAKER_" + str(multi_mode_track).zfill(2)
        result3 = result2

    print(f"Diarization took {time.time() - start_diarize:.2f} seconds.")
    print(f"Total time: {time.time() - start_time:.2f} seconds.")
    torch.cuda.empty_cache()
    if DEVICE == "mps":
        torch.mps.empty_cache()
    # Text cleanup.
    cleaned_segments = []
    for segment in result3["segments"]:
        if result1["language"] in data_leaks:
            for line in data_leaks[result1["language"]]:
                if line in segment["text"]:
                    segment["text"] = segment["text"].replace(line, "")
        segment["text"] = segment["text"].strip()

        if len(segment["text"]) > 0:
            cleaned_segments.append(segment)

    return cleaned_segments


================================================
File: src/util.py
================================================
from pydub import AudioSegment
import subprocess
import os

DEVICE = os.getenv("DEVICE")


def isolate_voices(file_paths):
    for index in range(len(file_paths)):
        chunk_length_ms = 100
        chunked = []
        for file in file_paths:
            audio = AudioSegment.from_file(file)
            chunked.append([audio[i : i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)])

        processed_chunks = [
            filter_nondominant_voice([chunks[i] for chunks in chunked], index) for i in range(len(chunked[0]))
        ]

        processed_audio = sum(processed_chunks)
        processed_audio.export(file_paths[index])


def filter_nondominant_voice(segments, index):
    value = segments[index].dBFS
    for i, segment in enumerate(segments):
        if i == index:
            continue
        if segment.dBFS > value:
            return segment - 100
    return segments[index]


def get_length(filename):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            filename,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return float(result.stdout)


def time_estimate(filename, online=True):
    try:
        # For now, we don't predict the wait time for zipped files in the queue.
        if filename[-4:] == ".zip":
            return 1, 1
        run_time = get_length(filename)
        if online:
            if DEVICE == "mps":
                return run_time / 5, run_time
            else:
                return run_time / 10, run_time
        else:
            if DEVICE == "mps":
                return run_time / 3, run_time
            else:
                return run_time / 6, run_time
    except Exception as e:
        print(e)
        return -1, -1


================================================
File: src/viewer.py
================================================
import os
import datetime
from dotenv import load_dotenv


load_dotenv()

ADDITIONAL_SPEAKERS = int(os.getenv("ADDITIONAL_SPEAKERS"))


# function to generate the viewer html-file.
# input data is the segments of the output of whisperx.assign_word_speakers: whisperx.assign_word_speakers(diarize_df, result2)['segments']
# file_path is the path to the audio/video file
def create_viewer(data, file_path, encode_base64, combine_speaker, root, language):
    for segment in data:
        if "speaker" not in segment:
            segment["speaker"] = "unknown"
    file_name = str(os.path.basename(file_path))

    html = header(root)
    html += navbar(root)
    html += video(file_name, encode_base64)
    html += buttons()
    html += meta_data(file_name, encode_base64)
    html += speaker_information(data)
    html += transcript(data, combine_speaker, language)
    html += javascript(data, file_path, encode_base64, file_name)
    return html


def header(root):
    content = ""
    with open(root + "data/bootstrap_content.txt", "r") as f:
        bootstrap_content = f.read()

    content += "<!doctype html>\n<html lang=\"en\">\n<meta http-equiv='Content-Type' content='text/html;charset=UTF-8'>\n<head>\t\n\t<style>\n\t\t@charset \"UTF-8\";/*!\n\t\t * Bootstrap  v5.3.2 (https://getbootstrap.com/)\n\t\t * Copyright 2011-2023 The Bootstrap Authors\n\t\t * Licensed under MIT (https://github.com/twbs/bootstrap/blob/main/LICENSE)\n\t\t"
    content += bootstrap_content + "\n"
    content += '\t\t/*# sourceMappingURL=bootstrap.min.css.map */\n\t\t.sticky-offset {\n\t\t\ttop: 130px;\n\t\t}\n\t\t.segment {\n\t\t\tpadding-right: 8px;\n\t\t}\n\t*[contenteditable]:empty:before{content: "\\feff-";}\n\t</style>\n</head>\n'

    return content


def navbar(root):
    with open(root + "data/logo.txt", "r") as f:
        logo = f.read()
    content = "<body>"
    content += "\n"
    content += f'\t<nav class="navbar sticky-top navbar-light" style="background-color: #0070b4; z-index: 999">\n\t\t<img src="{logo}" width="390" height="105" alt=""></img>\n\t</nav>'
    content += "\n"
    return content


def video(file_name, encode_base64):
    content = '\t<div class="row container justify-content-center align-items-start" style="max-width: 200ch; margin-left: auto; margin-right: auto; margin-bottom: 0px;">\n\t\t<div class="col-md-6 sticky-top sticky-offset" style="width: 40%; z-index: 1; margin-bottom: 0px;"">\n'
    if encode_base64:
        content += f'\t\t\t<div style="padding: 0">\n\t\t\t\t<video id="player" width="100%" style="max-height: 250px" src="" type="video/MP4" controls="controls" position="sticky"></video>\n'
    else:
        content += f'\t\t\t<div>\n\t\t\t\t<video id="player" width="100%" src="{file_name}" type="video/MP4" controls="controls" position="sticky"></video>\n'
    return content


def meta_data(file_name, encode_base64):
    content = '\t\t\t\t<div style="overflow-y: scroll; height: calc(100vh - 450px)">\n'
    content += '\t\t\t\t<div style="margin-top:10px;">\n'
    content += '\t\t\t\t\t<label for="nr">Hashwert</label><span id="hash" class="form-control">0</span>\n'
    content += (
        '\t\t\t\t\t<label for="date">Transkriptionssdatum</label><span contenteditable="true" class="form-control">'
        + str(datetime.date.today().strftime("%d-%m-%Y"))
        + "</span>\n"
    )
    if not encode_base64:
        content += f'\t\t\t\t\t<label for="date">Videodatei</label><span contenteditable="true" class="form-control", id="source">./{file_name}</span>\n'
    content += "\t\t\t\t</div>\n"
    return content


def speaker_information(data):
    content = '\t\t\t\t<div style="margin-top:10px;" class="viewer-hidden">\n'
    speakers = sorted(set([segment["speaker"] for segment in data if segment["speaker"] is not "unknown"]))

    n_speakers = len(speakers)
    for i in range(ADDITIONAL_SPEAKERS):
        speakers.append(str(n_speakers + i).zfill(2))
    speakers.append("unknown")

    for idx, speaker in enumerate(speakers):
        if speaker is not "unknown":
            content += f'\t\t\t\t\t<span contenteditable="true" class="form-control" id="IN_SPEAKER_{str(idx).zfill(2)}" style="margin-top:4px;">Person {speaker[-2:]}</span>\n'
    content += "\t\t\t\t<br><br><br><br><br></div>\n"
    content += "\t\t\t\t</div>\n"
    content += "\t\t\t</div>\n"
    content += "\t\t</div>\n"
    return content


def buttons():
    content = '\t\t\t\t<div style="margin-top:10px;" class="viewer-hidden">\n'
    content += (
        '\t\t\t\t\t<a href ="#" id="viewer-link" onClick="viewerClick()" class="btn btn-primary">Viewer erstellen</a>\n'
    )
    content += '\t\t\t\t\t<a href ="#" id="text-link" onClick="textClick()" class="btn btn-primary">Textdatei exportieren</a>\n'
    content += (
        '\t\t\t\t\t<a href ="#" id="download-link" onClick="downloadClick()" class="btn btn-primary">Speichern</a>\n'
    )
    content += '\t\t\t\t\t<br><span>Verzögerung: </span><span contenteditable="true" id="delay" class="border rounded"></span>\n'
    content += '\t\t\t\t\t<input type="checkbox" id="ignore_lang" value="ignore_lang" style="margin-left: 5px" onclick="changeCheckbox(this)"/>\n'
    content += '\t\t\t\t\t<label for="ignore_lang">Fremdsprachen beim Exportieren entfernen</label>\n'
    content += "\t\t\t\t</div>\n"
    return content


def segment_buttons():
    return "<button style='float: right;' class='btn btn-danger btn-sm' onclick='removeRow(this)'><svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-trash' viewBox='0 0 16 16'><path d='M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z'/><path d='M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z'/></svg></button><button style='float: right;' class='btn btn-primary btn-sm' onclick='addRow(this)'><svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-plus' viewBox='0 0 16 16'><path d='M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4'/></svg></button><button style=\"float: right; margin-right: 20px\" class=\"btn btn-warning btn-sm\" onclick=\"tagFunction(this)\"><svg xmlns=\"http://www.w3.org/2000/svg\" height=\"16px\" viewBox=\"0 -960 960 960\" width=\"16px\" fill=\"#5f6368\"><path d=\"m264-192 30-120H144l18-72h150l42-168H192l18-72h162l36-144h72l-36 144h144l36-144h72l-36 144h156l-18 72H642l-42 168h168l-18 72H582l-30 120h-72l30-120H366l-30 120h-72Zm120-192h144l42-168H426l-42 168Z\"/></svg></button>"


def transcript(data, combine_speaker, language):
    content = '\t\t<div class="col-md-6" style="width: 60%; max-width: 90ch; z-index: 1; margin-left: auto; margin-right: auto">\n'
    content += '\t\t\t<div class="wrapper" style="margin: 0.5rem auto 0; max-width: 80ch;" id="editor">\n'

    speakers = sorted(set([segment["speaker"] for segment in data if segment["speaker"] is not "unknown"]))
    n_speakers = len(speakers)
    for i in range(ADDITIONAL_SPEAKERS):
        speakers.append(str(n_speakers + i).zfill(2))
    speakers.append("unknown")
    speaker_order = []
    table_elements = ""
    last_speaker = None
    for segment in data:
        if segment["speaker"] not in speaker_order and segment["speaker"] is not "unknown":
            speaker_order.append(segment["speaker"])

    for i in range(ADDITIONAL_SPEAKERS):
        speaker_order.append(str(n_speakers + i).zfill(2))
    speaker_order.append("unknown")

    for i, segment in enumerate(data):
        if last_speaker is not None and not segment["speaker"][-1] == last_speaker:
            table_elements += "\t\t\t\t\t</p>\n"
            table_elements += "\t\t\t</div>\n"
        table_elements += "\t\t\t<div>\n"
        if last_speaker is None or not segment["speaker"][-1] == last_speaker:
            table_elements += '\t\t\t\t\t<div style="display: block; margin-bottom: 0.5rem;">\n'
            table_elements += "\t\t\t\t\t"
            table_elements += f'<select onchange="selectChange(this)">\n'
            speaker_idx = speaker_order.index(segment["speaker"])
            for idx, speaker in enumerate(speakers):
                if idx == speaker_idx:
                    if speaker == "unknown":
                        table_elements += f'\t\t\t\t\t\t<option value="{str(idx).zfill(2)}" class="OUT_SPEAKER_{str(idx).zfill(2)}" selected="selected">Person unbekannt</option>\n'
                    else:
                        table_elements += f'\t\t\t\t\t\t<option value="{str(idx).zfill(2)}" class="OUT_SPEAKER_{str(idx).zfill(2)}" selected="selected">Person {str(speaker[-2:]).zfill(2)}</option>\n'
                else:
                    if speaker == "unknown":
                        table_elements += f'\t\t\t\t\t\t<option value="{str(idx).zfill(2)}" class="OUT_SPEAKER_{str(idx).zfill(2)}">Person unbekannt</option>\n'
                    else:
                        table_elements += f'\t\t\t\t\t\t<option value="{str(idx).zfill(2)}" class="OUT_SPEAKER_{str(idx).zfill(2)}">Person {str(speaker[-2:]).zfill(2)}</option>\n'
            table_elements += "\t\t\t\t\t</select>\n"
            table_elements += (
                '\t\t\t\t\t<span contenteditable="true">'
                + str(datetime.timedelta(seconds=round(segment["start"], 0)))
                + "</span>\n"
            )
            if "language" in segment:
                if (language == "de" and segment["language"] in ["de", "en", "nl"]) or language == segment["language"]:
                    table_elements += '\t\t\t\t\t<input type="checkbox" class="language" name="language" value="Fremdsprache" style="margin-left: 5px" onclick="changeCheckbox(this)"/> <label for="language">Fremdsprache</label>\n'
                else:
                    table_elements += '\t\t\t\t\t<input type="checkbox" class="language" name="language" value="Fremdsprache" style="margin-left: 5px" onclick="changeCheckbox(this)" checked="checked" /> <label for="language">Fremdsprache</label>\n'

            table_elements += "\t\t\t\t\t" + segment_buttons() + "\n"
            table_elements += "\t\t\t\t\t</div>\n"
            table_elements += '\t\t\t\t\t<p class="form-control">'
        table_elements += f"<span id=\"{str(i)}\" tabindex=\"{str(i+1)}\" onclick=\"changeVideo({str(i)})\" contenteditable=\"true\" class=\"segment\" title=\"{str(datetime.timedelta(seconds=round(segment['start'], 0)))} - {str(datetime.timedelta(seconds=round(segment['end'],0)))}\">{segment['text'].strip().replace('ß', 'ss')}</span>"
        table_elements += "\n"
        if combine_speaker:
            last_speaker = segment["speaker"][-1]
        else:
            last_speaker = ""

    content += table_elements

    content += "\t\t\t</p></div>\n"
    content += "\t\t</div>\n"
    content += "\t</div>\n"
    content += "</body>\n"
    content += "</html>\n\n"
    return content


def javascript(data, file_path, encode_base64, file_name):
    speakers = sorted(set([segment["speaker"] for segment in data if segment["speaker"] is not "unknown"]))
    n_speakers = len(speakers)
    for i in range(ADDITIONAL_SPEAKERS):
        speakers.append(str(n_speakers + i).zfill(2))
    speakers.append("unknown")

    speakers_array = "var speakers = Array("
    for idx, speaker in enumerate(speakers):
        if speaker is not "unknown":
            speakers_array += f'"IN_SPEAKER_{str(idx).zfill(2)}", '
    if len(speakers) > 1:
        speakers_array = speakers_array[:-2] + ")"
    else:
        speakers_array += ")"
    number_of_speakers = len(set([segment["speaker"] for segment in data if segment["speaker"] is not "unknown"]))
    content = """<script language="javascript">\n"""
    content += f'var fileName = "{file_name.split(".")[0]}"\n'
    content += """var source = Array(null, null, null, null, null)
var outputs = Array(null, null, null, null, null)\n"""
    content += speakers_array + "\n"
    content += f"for(var j = 0; j < speakers.length; j++)" + " {\n"
    content += """\tsource[j] = document.getElementById(speakers[j]);
\toutputs[j] = document.getElementsByClassName("OUT_SPEAKER_" + pad(j, 2));

\tinputHandler = function(e) {
\t\tfor(var i = 0; i < outputs[parseInt(e.target.id.slice(-2))].length; i++) {
\t\t\toutputs[parseInt(e.target.id.slice(-2))][i].innerText = e.target.textContent
\t\t\t//if (e.target.textContent == "") {
\t\t\t\t//outputs[parseInt(e.target.id.slice(-2))][i].innerText = "SPEAKER_" + pad(parseInt(e.target.id.slice(-2)), 2);
\t\t\t//}
\t\t}
\t}

\tsource[j].addEventListener('input', inputHandler);
\tsource[j].addEventListener('propertychange', inputHandler);
}
"""
    if not encode_base64:
        content += """
source_video_field = document.getElementById("source");

inputHandler = function(e) {
    document.getElementById("player").src = e.target.textContent;
}

source_video_field.addEventListener('input', inputHandler);
source_video_field.addEventListener('propertychange', inputHandler);
"""

    content += """
function hashCode(s) {
  var hash = 0,
    i, chr;
  if (s.length === 0) return hash;
  for (i = 0; i < s.length; i++) {
    chr = s.charCodeAt(i);
    hash = ((hash << 5) - hash) + chr;
    hash |= 0; // Convert to 32bit integer
  }
  return hash;
}

var hash_field = document.getElementById("hash");  
hash_field.textContent = hashCode(document.getElementById("editor").textContent)

function handleBeforeInput(e) {
    if (e.inputType === "deleteByCut" || e.inputType === "deleteContentBackward" || e.inputType === "deleteContentForward") {
    } else if (e.data === null && e.dataTransfer) {
        e.preventDefault()
        document.execCommand("insertText", false, e.dataTransfer.getData("text/plain"))
    } else if (e.data === null && e.dataTransfer === null) {
        e.preventDefault()
    }
}

document.getElementsByClassName("wrapper")[0].addEventListener('beforeinput', handleBeforeInput);

var vid = document.getElementsByTagName("video")[0];
vid.ontimeupdate = function() {highlightFunction()};"""
    content += "\n"

    content += "var timestamps = "
    timestamps = "Array("
    for segment in data:
        timestamps += f"Array({segment['start']}, {segment['end']}), "
    if len(data) > 0:
        timestamps = timestamps[:-2] + ");"
    else:
        timestamps += ");"
    content += timestamps
    content += "\n"

    content += """vid.currentTime = 0.0;
highlightFunction();

function pad(num, size) {
    num = num.toString();
    while (num.length < size) num = "0" + num;
    return num;
}

function downloadClick() {
    var content = document.documentElement.innerHTML;
    var path = window.location.pathname;
    var page = path.split("/").pop();
    download(content, "html")
}

function viewerClick() {
    var content = document.documentElement.innerHTML;
    var path = window.location.pathname;
    var page = path.split("/").pop();
    downloadViewer(content, "html")
}

function textClick() {
    var content = document.documentElement.innerHTML;
    var path = window.location.pathname;
    var page = path.split("/").pop();
    downloadText(content, "txt")
}

function download(content, fileType) {
    var link = document.getElementById("download-link");
    var file = new Blob([content], {type: fileType});
    var downloadFile = fileName + "." + fileType;
    link.href = URL.createObjectURL(file);
    link.download = downloadFile;
}

function changeCheckbox(checkbox) {
	console.log(checkbox.getAttribute("checked"))
	if (checkbox.getAttribute("checked") != null) {
		checkbox.removeAttribute("checked")
	} else {
		checkbox.setAttribute("checked", "checked")
	}
}

function downloadViewer(content, fileType) {
    var link = document.getElementById("viewer-link");
	var ignore_lang = document.getElementById("ignore_lang").checked;
	var current_pos=0, current_speaker_start=0, current_speaker_end=0, current_speaker=0, current_end_span=0, next_span_start=0, next_speaker_start=0, next_speaker=0;
	var same_speaker = false;
	
    content = content.replaceAll('contenteditable="true"', 'contenteditable="false"');
    content = content.replaceAll('<p class="form-control">', '<p>');
    content = content.replaceAll('class="viewer-hidden"', 'hidden');
    content = content.replaceAll('class="viewer-disabled"', 'class="form-control" disabled');
    content = content.replaceAll('video.pause();', '');
    
	
	index_script = content.indexOf("<script language")
    content_script = content.substr(index_script, content.length)
	content = content.substr(0, index_script)
	content_header = content.substr(0, content.indexOf('id="editor">') + 'id="editor">'.length)
	content = content.substr(content.indexOf('id="editor">'), content.length)

	content_out = ""
                
	next_speaker_start = content.indexOf('selected="selected">') + 'selected="selected">'.length
	next_speaker_end = content.indexOf('</option>', next_speaker_start)

	
    while(next_speaker_start > 'selected="selected">'.length) {
		if (ignore_lang) {
			var d = document.createElement('html');
			d.innerHTML = content;
			first_element = d.querySelector('.language');
		}
		skip = ignore_lang && (!(first_element == null) && first_element.checked)

		if (!(same_speaker)) {
			if (!skip) {
				current_speaker = content.slice(next_speaker_start, next_speaker_end)
			}
				current_timestamp_start = content.indexOf('<span contenteditable="false">') + '<span contenteditable="false">'.length
				current_timestamp_end = content.indexOf('</span>')
				current_timestamp = content.slice(current_timestamp_start, current_timestamp_end)
			if (!skip) {
				content_out = content_out + '<div class="form-control bg-secondary text-white" disabled style="display: block; margin-top: 0.5rem;">\\n'
				content_out = content_out + current_speaker + ' (' + current_timestamp + ')\\n</div>\\n'
			}
		}
		current_text_start = content.indexOf('<p>', current_timestamp_end)
		current_text_end = content.indexOf('</p>', current_text_start) + '</p>'.length
		current_text = content.slice(current_text_start, current_text_end)
		if (!skip){
			content_out = content_out + current_text.replaceAll('<p>', '<span>').replaceAll('</p>', '</span>') + '\\n'
		}
		content = content.substr(current_text_end, content.length)
		
		next_speaker_start = content.indexOf('selected="selected">') + 'selected="selected">'.length

		if (next_speaker_start > 'selected="selected">'.length) {
			next_speaker_end = content.indexOf('</option>', next_speaker_start)
			same_speaker = (current_speaker === content.slice(next_speaker_start, next_speaker_end))
			current_timestamp_end = next_speaker_end
		}
    }
    var file = new Blob([content_header + '\\n' + content_out + '\\n' + content_script], {type: fileType});
    var downloadFile = fileName + "_viewer." + fileType;
    link.href = URL.createObjectURL(file);
    link.download = downloadFile;
}

function downloadText(content, fileType) {
    var content_out = ''
    var link = document.getElementById("text-link");   
	var ignore_lang = document.getElementById("ignore_lang").checked; 
	var current_pos=0, current_speaker_start=0, current_speaker_end=0, current_speaker=0, current_end_span=0, next_span_start=0, next_speaker_start=0, next_speaker=0;
	var same_speaker = false;
	
    content = content.replaceAll('contenteditable="true"', 'contenteditable="false"');
    content = content.replaceAll('<p class="form-control">', '<p>');
    content = content.replaceAll('class="viewer-hidden"', 'hidden');
    content = content.replaceAll('class="viewer-disabled"', 'class="form-control" disabled');
    content = content.replaceAll('video.pause();', '');
    
	index_script = content.indexOf("<script language")
	content = content.substr(0, index_script)
	content = content.substr(content.indexOf('id="editor">'), content.length)

	content_out = ""
                
	next_speaker_start = content.indexOf('selected="selected">') + 'selected="selected">'.length
	next_speaker_end = content.indexOf('</option>', next_speaker_start)

    while(next_speaker_start > 'selected="selected">'.length) {
		if (ignore_lang) {
			var d = document.createElement('html');
			d.innerHTML = content;
			first_element = d.querySelector('.language');
		}
		skip = ignore_lang && (!(first_element == null) && first_element.checked)

		if (!(same_speaker)) {
			if (!skip) {
				current_speaker = content.slice(next_speaker_start, next_speaker_end)
			}
			current_timestamp_start = content.indexOf('<span contenteditable="false">') + '<span contenteditable="false">'.length
			current_timestamp_end = content.indexOf('</span>')
			current_timestamp = content.slice(current_timestamp_start, current_timestamp_end)
			
			if (!skip) {
				if (content_out.length > 0) {
					content_out = content_out + '\\n\\n'
				}
				content_out = content_out + current_speaker + ' (' + current_timestamp + '):\\n'
			}
		}
		current_text_start = content.indexOf('<p>', current_timestamp_end)
		current_text_end = content.indexOf('</p>', current_text_start) + '</p>'.length
		current_text = content.slice(current_text_start, current_text_end)
		current_text = current_text.replaceAll('<p>', '').replaceAll('</p>', '').replace(/\\u00a0/g, " ");
		current_text = current_text.slice(current_text.indexOf('>') + 1, current_text.indexOf('</span>'))
		if (!skip) {
			content_out = content_out + current_text + ' '
		}

		content = content.substr(current_text_end, content.length)
		
		next_speaker_start = content.indexOf('selected="selected">') + 'selected="selected">'.length

		if (next_speaker_start > 'selected="selected">'.length) {
			next_speaker_end = content.indexOf('</option>', next_speaker_start)
			same_speaker = (current_speaker === content.slice(next_speaker_start, next_speaker_end))
			current_timestamp_end = next_speaker_end
		}
    }

    var file = new Blob([content_out], {type: fileType});
    var downloadFile = fileName + "." + fileType;
    link.href = URL.createObjectURL(file);
    link.download = downloadFile;
}

function selectChange(selectObject) {
    var idx = selectObject.selectedIndex
    selectObject.innerHTML = selectObject.innerHTML.replace('selected="selected"', '')
    selectObject.innerHTML = selectObject.innerHTML.replace('class="OUT_SPEAKER_' + pad(idx, 2) + '"', 'class="OUT_SPEAKER_' + pad(idx, 2) + '" selected="selected"')
}

function highlightFunction() {
    var i = 0;
    while (i < timestamps.length) {
      if (vid.currentTime >= timestamps[i][0] && vid.currentTime < timestamps[i][1]){
		var element = document.getElementById(i.toString())
		if (element) {
			element.style.backgroundColor = "#9ddbff";
			var rect = element.getBoundingClientRect();
			var viewHeight = window.innerHeight
			if (rect.bottom < 40 || rect.top - viewHeight >= -40){
				element.scrollIntoView({ block: "center" });
			}
		}
      } else {
        var element = document.getElementById(i.toString())
		if (element) {
			element.style.backgroundColor = "white";
		}
      }
      i++;
    }
}

function tagFunction(button) {
	var element = button.parentElement
	if (element.style.backgroundColor == "rgb(255, 169, 8)") {
		element.style.backgroundColor = "white";
	} else {
		element.style.backgroundColor = "rgb(255, 169, 8)";
	}
	
}

function insertAfter(referenceNode, newNode) {
  referenceNode.parentNode.insertBefore(newNode, referenceNode.nextSibling);
}

function addRow(button) {
	var previous_row = button.parentElement.parentElement;
	var new_row = document.createElement('div');
	new_row.innerHTML = previous_row.innerHTML
	text_span = new_row.getElementsByClassName("segment")[0]
	text_span.textContent = "Neues Textsegment"
	text_span.removeAttribute('id');
	text_span.removeAttribute('onclick');
    text_span.style.backgroundColor = "white";
	insertAfter(previous_row, new_row);
}

function removeRow(button) {
    if (confirm("Sprachsegment entfernen?\\nDrücke OK um das Sprachsegment zu entfernen.")){
	    button.parentElement.parentElement.remove();
    }
}

document.addEventListener('keydown', (event) => {
    if(event.ctrlKey && event.keyCode == 32) {
		event.preventDefault();
		var v = document.getElementsByTagName("video")[0];
    	if (video.paused) v.play(); 
		else v.pause();
  	}
});

function isNumeric(str) {
  if (typeof str != "string") return false 
  return !isNaN(str) && 
         !isNaN(parseFloat(str))
}

function changeVideo(id) {
    var video = document.getElementsByTagName("video")[0];
	var delayElement = document.getElementById("delay");
    var content = delayElement.innerText;
    content = content.replaceAll('s', '');
	var delay = 0;

	if (isNumeric(content)){
		delay = parseFloat(content)
	}
    video.currentTime = Math.max(timestamps[id][0] - delay, 0);
    video.pause();
}

"""

    content += "</script>"

    return content


