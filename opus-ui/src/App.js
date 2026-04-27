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
    <div
      style={{
        minHeight: "100vh",
        background:
          "radial-gradient(circle at top left, #1e293b, #020617 55%)",
        color: "white",
        fontFamily: "Inter, Arial, sans-serif",
        padding: "28px",
      }}
    >
      <div style={{ maxWidth: "1180px", margin: "0 auto" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "40px",
          }}
        >
          <div style={{ fontSize: "28px", fontWeight: "900" }}>
            FluxClip ☠️✂️
          </div>

          <div
            style={{
              display: "flex",
              gap: "12px",
              color: "#cbd5e1",
              fontSize: "14px",
            }}
          >
            <span>Dashboard</span>
            <span>Pricing</span>
            <span>Docs</span>
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.1fr 0.9fr",
            gap: "24px",
            marginBottom: "28px",
          }}
        >
          <div
            style={{
              background:
                "linear-gradient(135deg, rgba(34,197,94,0.18), rgba(59,130,246,0.12))",
              border: "1px solid rgba(148,163,184,0.25)",
              borderRadius: "24px",
              padding: "34px",
              boxShadow: "0 25px 80px rgba(0,0,0,0.35)",
            }}
          >
            <div
              style={{
                display: "inline-block",
                background: "rgba(34,197,94,0.15)",
                color: "#86efac",
                padding: "8px 14px",
                borderRadius: "999px",
                fontWeight: "700",
                fontSize: "13px",
                marginBottom: "20px",
              }}
            >
              AI Viral Shorts Engine
            </div>

            <h1
              style={{
                fontSize: "56px",
                lineHeight: "1.05",
                margin: "0 0 18px",
                fontWeight: "950",
              }}
            >
              Turn long videos into viral-ready shorts.
            </h1>

            <p
              style={{
                color: "#cbd5e1",
                fontSize: "18px",
                lineHeight: "1.6",
                maxWidth: "650px",
              }}
            >
              Upload a long video. FluxClip detects viral moments, creates
              shorts, adds captions, scores clips, generates titles, hashtags
              and export-ready packages.
            </p>

            <div
              style={{
                display: "flex",
                gap: "12px",
                marginTop: "28px",
                flexWrap: "wrap",
              }}
            >
              {["Smart Crop", "Captions", "Thumbnails", "Hashtags"].map(
                (item) => (
                  <div
                    key={item}
                    style={{
                      background: "rgba(15,23,42,0.75)",
                      border: "1px solid rgba(148,163,184,0.2)",
                      padding: "10px 14px",
                      borderRadius: "12px",
                      color: "#e2e8f0",
                    }}
                  >
                    ✅ {item}
                  </div>
                )
              )}
            </div>
          </div>

          <div
            style={{
              background: "rgba(15,23,42,0.9)",
              border: "1px solid rgba(148,163,184,0.25)",
              borderRadius: "24px",
              padding: "28px",
              boxShadow: "0 25px 80px rgba(0,0,0,0.35)",
            }}
          >
            <h2 style={{ marginTop: 0 }}>Create New Viral Pack</h2>
            <p style={{ color: "#94a3b8" }}>
              Upload one long-form video to generate AI-selected short clips.
            </p>

            <div
              style={{
                border: "2px dashed rgba(148,163,184,0.35)",
                borderRadius: "18px",
                padding: "28px",
                textAlign: "center",
                background: "rgba(30,41,59,0.65)",
                margin: "24px 0",
              }}
            >
              <div style={{ fontSize: "42px", marginBottom: "12px" }}>🎬</div>
              <input
                type="file"
                onChange={(e) => setFile(e.target.files[0])}
              />
              <p style={{ color: "#cbd5e1", fontSize: "14px" }}>
                {file ? file.name : "MP4, MOV, MKV supported"}
              </p>
            </div>

            <button
              onClick={uploadFile}
              disabled={loading}
              style={{
                width: "100%",
                background: loading
                  ? "#64748b"
                  : "linear-gradient(135deg, #22c55e, #16a34a)",
                color: "white",
                border: "none",
                padding: "16px 20px",
                borderRadius: "14px",
                cursor: loading ? "not-allowed" : "pointer",
                fontWeight: "900",
                fontSize: "16px",
              }}
            >
              {loading ? "Processing..." : "Generate Viral Shorts"}
            </button>

            {jobId && (
              <div
                style={{
                  marginTop: "18px",
                  background: "rgba(30,41,59,0.8)",
                  borderRadius: "14px",
                  padding: "14px",
                  fontSize: "14px",
                }}
              >
                <div>
                  <strong>Status:</strong> {status}
                </div>
                <div style={{ color: "#94a3b8", marginTop: "6px" }}>
                  Job: {jobId}
                </div>
              </div>
            )}
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "16px",
            marginBottom: "28px",
          }}
        >
          {[
            ["⚡", "Fast ASR", "GPU optimized"],
            ["🧠", "Viral Brain", "Hook ranking"],
            ["🎯", "Smart Export", "Captions + titles"],
            ["📦", "Creator Pack", "Download ready"],
          ].map(([icon, title, sub]) => (
            <div
              key={title}
              style={{
                background: "rgba(15,23,42,0.8)",
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: "18px",
                padding: "20px",
              }}
            >
              <div style={{ fontSize: "30px" }}>{icon}</div>
              <h3 style={{ margin: "10px 0 6px" }}>{title}</h3>
              <p style={{ color: "#94a3b8", margin: 0 }}>{sub}</p>
            </div>
          ))}
        </div>

        {loading && (
          <div
            style={{
              background: "rgba(34,197,94,0.12)",
              border: "1px solid rgba(34,197,94,0.35)",
              padding: "22px",
              borderRadius: "18px",
              marginBottom: "28px",
            }}
          >
            <h3>🔥 AI is cooking your viral clips...</h3>
            <p style={{ color: "#cbd5e1" }}>
              Transcribing → Viral Detection → Smart Crop → Captions → Final Shorts
            </p>
          </div>
        )}

        {error && (
          <div
            style={{
              background: "#7f1d1d",
              padding: "18px",
              borderRadius: "16px",
              marginBottom: "24px",
            }}
          >
            {error}
          </div>
        )}

        {clips.length > 0 && (
          <div>
            <h2 style={{ fontSize: "34px" }}>Your Viral Clips</h2>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(330px, 1fr))",
                gap: "20px",
              }}
            >
              {clips.map((clip, index) => {
                const videoUrl = fixVideoUrl(
                  clip.video_path || clip.download_url
                );

                return (
                  <div
                    key={index}
                    style={{
                      background: "rgba(15,23,42,0.9)",
                      border: "1px solid rgba(148,163,184,0.22)",
                      padding: "20px",
                      borderRadius: "22px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: "12px",
                      }}
                    >
                      <h3 style={{ margin: 0 }}>
                        Clip #{clip.clip_number || index + 1}
                      </h3>

                      <span
                        style={{
                          background: "#22c55e",
                          color: "#052e16",
                          padding: "6px 10px",
                          borderRadius: "999px",
                          fontWeight: "900",
                        }}
                      >
                        Score {clip.score}
                      </span>
                    </div>

                    <p>
                      <strong>Title:</strong> {clip.title}
                    </p>
                    <p>
                      <strong>Niche:</strong> {clip.niche}
                    </p>
                    <p>
                      <strong>Duration:</strong> {clip.duration}s
                    </p>

                    <p style={{ color: "#86efac" }}>
                      {Array.isArray(clip.hashtags)
                        ? clip.hashtags.join(" ")
                        : ""}
                    </p>

                    {videoUrl && (
                      <>
                        <video
                          width="100%"
                          controls
                          src={videoUrl}
                          style={{
                            borderRadius: "16px",
                            marginTop: "10px",
                            background: "#000",
                          }}
                        />

                        <a
                          href={videoUrl}
                          download
                          style={{
                            display: "inline-block",
                            marginTop: "14px",
                            background: "#3b82f6",
                            color: "white",
                            padding: "12px 16px",
                            borderRadius: "12px",
                            textDecoration: "none",
                            fontWeight: "900",
                          }}
                        >
                          Download Clip
                        </a>
                      </>
                    )}

                    <div
                      style={{
                        marginTop: "16px",
                        background: "rgba(51,65,85,0.8)",
                        padding: "12px",
                        borderRadius: "14px",
                      }}
                    >
                      <strong>Score Breakdown</strong>
                      <pre style={{ overflowX: "auto" }}>
                        {JSON.stringify(clip.score_breakdown, null, 2)}
                      </pre>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;