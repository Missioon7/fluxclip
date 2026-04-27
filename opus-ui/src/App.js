import React, { useState } from "react";
import axios from "axios";

const API = "https://web-production-9c211.up.railway.app";

function fixVideoUrl(path) {
  if (!path) return "";

  let clean = String(path).replace(/\\/g, "/");

  const uploadsIndex = clean.indexOf("uploads/");
  if (uploadsIndex !== -1) clean = clean.substring(uploadsIndex);

  const outputsIndex = clean.indexOf("outputs/");
  if (outputsIndex !== -1) clean = clean.substring(outputsIndex);

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
        headers: { "Content-Type": "multipart/form-data" },
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
    <div style={{ minHeight: "100vh", background: "#020617", color: "white", padding: "30px" }}>
      <h1>FluxClip 🚀</h1>
      <p>Upload long videos → get viral clips automatically</p>

      <input
        type="file"
        onChange={(e) => setFile(e.target.files[0])}
      />

      <button
        onClick={uploadFile}
        disabled={loading}
        style={{
          marginLeft: "10px",
          padding: "10px 20px",
          background: "#22c55e",
          color: "white",
          border: "none",
          borderRadius: "10px"
        }}
      >
        {loading ? "Processing..." : "Upload Video"}
      </button>

      {jobId && (
        <div style={{ marginTop: "20px" }}>
          <strong>Status:</strong> {status}
          <br />
          Job ID: {jobId}
        </div>
      )}

      {error && (
        <div style={{ color: "red", marginTop: "20px" }}>
          {error}
        </div>
      )}

      {clips.length > 0 && (
        <div style={{ marginTop: "30px" }}>
          <h2>Your Clips</h2>

          {clips.map((clip, index) => {
            const videoUrl = fixVideoUrl(
              clip.video_path || clip.download_url
            );

            return (
              <div
                key={index}
                style={{
                  background: "#1e293b",
                  padding: "20px",
                  marginBottom: "20px",
                  borderRadius: "12px"
                }}
              >
                <h3>Clip #{index + 1}</h3>
                <p><strong>Title:</strong> {clip.title}</p>
                <p><strong>Score:</strong> {clip.score}</p>

                {videoUrl && (
                  <>
                    <video
                      width="400"
                      controls
                      src={videoUrl}
                    />

                    <br />

                    <a
                      href={videoUrl}
                      download
                      style={{ color: "#38bdf8" }}
                    >
                      Download Clip
                    </a>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default App;