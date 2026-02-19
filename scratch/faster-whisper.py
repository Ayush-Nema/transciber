from faster_whisper import WhisperModel
from datasets import load_dataset
from dotenv import load_dotenv
import os

load_dotenv()

dataset = load_dataset("distil-whisper/librispeech_long", "clean", split="validation")

model_size = "large-v3"

# Run on GPU with FP16
model = WhisperModel(model_size, device="cuda", compute_type="float16", use_auth_token=os.environ["HF_TOKEN"])

# or run on GPU with INT8
# model = WhisperModel(model_size, device="cuda", compute_type="int8_float16")
# or run on CPU with INT8
# model = WhisperModel(model_size, device="cpu", compute_type="int8")

segments, info = model.transcribe(dataset[0]["audio"], beam_size=5)

print("Detected language '%s' with probability %f" % (info.language, info.language_probability))

for segment in segments:
    print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))