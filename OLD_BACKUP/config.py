import os

BASE_DIR = os.getcwd()

def job_dir(job_id):
    path = os.path.join(BASE_DIR, "jobs", job_id)
    os.makedirs(path, exist_ok=True)
    return path