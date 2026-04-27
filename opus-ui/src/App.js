import React, { useState } from "react";
import axios from "axios";

const API = "http://127.0.0.1:8000";

function fixVideoUrl(path) {
  if (!path) return "";

  let clean = String(path).replace(/\\/g, "/");

  const uploadsIndex = clean.indexOf("uploads/");
  if (uploadsIndex !== -1) {
    clean = clean.substring(uploadsIndex);
  }

  const outputsIndex = clean.indexOf("outputs/");
  if (outputsIndex !== -1) {
    clean = clean.substring(outputsIndex);
  }

  return `${API}/${clean}`;
}

function App() {
  const [file, setFile] = useState(null);
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const pollJob = async (id) => {
    const timer = setInterval(async () => {
      try {
        const res = await axios.get(`${API}/status/${id}`);
        const data = res.data;

        setStatus(data.status || "processing");

        if (data.status === "completed") {
          clearInterval(timer);
          setLoading(false);
          setResult(data.result);
        }

        if (data.status === "failed" || data.status === "error") {
          clearInterval(timer);
          setLoading(false);
          setError(data.error || "Processing failed");
        }
      } catch (err) {
        clearInterval(timer);
        setLoading(false);
        setError("Could not fetch job status");
      }
    }, 3000);
  };

  const uploadFile = async () => {
    if (!file) {
      alert("Select video first");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      setLoading(true);
      setResult(null);
      setError("");
      setStatus("uploading");

      const res = await axios.post(`${API}/upload`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      setJobId(res.data.job_id);
      setStatus("queued");
      pollJob(res.data.job_id);
    } catch (err) {
      console.error(err);
      setLoading(false);
      setError("Upload failed");
    }
  };

  const clips = result?.clips || [];

  return (
    <div
      style={{
        background: "#0f172a",
        minHeight: "100vh",
        color: "white",
        padding: "30px",
        fontFamily: "Arial",
      }}
    >
      <h1 style={{ color: "#22c55e" }}>OPUS AI V3 🚀</h1>
      <p>Create viral clips automatically with AI</p>

      <div
        style={{
          background: "#1e293b",
          padding: "20px",
          borderRadius: "12px",
          marginBottom: "20px",
        }}
      >
        <input type="file" onChange={(e) => setFile(e.target.files[0])} />

        <br />
        <br />

        <button
          onClick={uploadFile}
          disabled={loading}
          style={{
            background: loading ? "#64748b" : "#22c55e",
            color: "white",
            border: "none",
            padding: "12px 20px",
            borderRadius: "8px",
            cursor: loading ? "not-allowed" : "pointer",
            fontWeight: "bold",
          }}
        >
          {loading ? "Processing..." : "Upload & Generate Clips"}
        </button>
      </div>

      {jobId && (
        <div
          style={{
            background: "#1e293b",
            padding: "15px",
            borderRadius: "10px",
            marginBottom: "20px",
          }}
        >
          <p>
            <strong>Job ID:</strong> {jobId}
          </p>
          <p>
            <strong>Status:</strong> {status}
          </p>
        </div>
      )}

      {loading && (
        <div
          style={{
            background: "#1e293b",
            padding: "20px",
            borderRadius: "10px",
            marginBottom: "20px",
          }}
        >
          <h3>🔥 AI is processing your video...</h3>
          <p>Transcribing → Viral detection → Smart crop → Captions → Final clips</p>
        </div>
      )}

      {error && (
        <div
          style={{
            background: "#7f1d1d",
            padding: "15px",
            borderRadius: "10px",
            marginBottom: "20px",
          }}
        >
          {error}
        </div>
      )}

      {clips.length > 0 && (
        <div>
          <h2>Generated Viral Clips</h2>

          {clips.map((clip, index) => {
            const videoUrl = fixVideoUrl(clip.video_path || clip.download_url);

            return (
              <div
                key={index}
                style={{
                  background: "#1e293b",
                  padding: "20px",
                  marginBottom: "20px",
                  borderRadius: "12px",
                }}
              >
                <h3>Clip #{clip.clip_number || index + 1}</h3>

                <p>
                  <strong>Title:</strong> {clip.title}
                </p>

                <p>
                  <strong>Niche:</strong> {clip.niche}
                </p>

                <p>
                  <strong>Score:</strong> {clip.score}
                </p>

                <p>
                  <strong>Duration:</strong> {clip.duration}s
                </p>

                <p>
                  <strong>Hashtags:</strong>{" "}
                  {Array.isArray(clip.hashtags) ? clip.hashtags.join(" ") : ""}
                </p>

                {videoUrl && (
                  <>
                    <video
                      width="320"
                      controls
                      src={videoUrl}
                      style={{
                        borderRadius: "10px",
                        marginTop: "10px",
                      }}
                    />

                    <br />
                    <br />

                    <a
                      href={videoUrl}
                      download
                      style={{
                        background: "#3b82f6",
                        color: "white",
                        padding: "10px 15px",
                        borderRadius: "8px",
                        textDecoration: "none",
                        fontWeight: "bold",
                      }}
                    >
                      Download Clip
                    </a>
                  </>
                )}

                <div
                  style={{
                    marginTop: "15px",
                    background: "#334155",
                    padding: "10px",
                    borderRadius: "8px",
                  }}
                >
                  <strong>Score Breakdown:</strong>
                  <pre>{JSON.stringify(clip.score_breakdown, null, 2)}</pre>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default App;