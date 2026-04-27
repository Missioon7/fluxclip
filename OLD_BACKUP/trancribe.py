import whisper
import torch

def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model("small", device=device)
    return model, device


def transcribe(model, audio_path, device):
    return model.transcribe(
        audio_path,
        language=None,
        fp16=(device == "cuda"),
        temperature=0.0,
        condition_on_previous_text=False
    )