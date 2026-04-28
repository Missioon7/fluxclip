import React, { useState } from "react";
import axios from "axios";

const API = "/api";

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
  const [uploadProgress, setUploadProgress] = useState(0);

  const pollJob = async (id) => {
    const timer = setInterval(async () => {
      try {
        const res = await axios.get(`${API}/status/${id}`, { timeout: 0 });
        const data = res.data;

        console.log("Polling response:", data);

        setStatus(data.status || "processing");

        if (
          data.status === "completed" ||
          data.status === "done" ||
          data.final_clips ||
          data.result ||
          data.clips
        ) {
          clearInterval(timer);
          setLoading(false);
          setUploadProgress(100);

          setResult({
            clips:
              data.result?.clips ||
              data.final_clips ||
              data.clips ||
              [],
          });
        }

        if (data.status === "failed" || data.status === "error") {
          clearInterval(timer);
          setLoading(false);
          setError(data.error || "Processing failed");
        }
      } catch (err) {
        console.log("Polling retry...", err);
      }
    }, 5000);
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
      setJobId("");
      setUploadProgress(0);
      setStatus("uploading");

      const res = await axios.post(`${API}/upload`, formData, {
        timeout: 0,
        maxBodyLength: Infinity,
        maxContentLength: Infinity,
        onUploadProgress: (progressEvent) => {
          if (!progressEvent.total) return;
          const percent = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          setUploadProgress(percent);
        },
      });

      const newJobId = res.data.job_id || res.data.id;

      if (!newJobId) {
        throw new Error("Backend did not return job_id");
      }

      setJobId(newJobId);
      setStatus("queued");
      pollJob(newJobId);
    } catch (err) {
      console.error("Upload error:", err);
      setLoading(false);

      const backendMessage =
        err.response?.data?.detail ||
        err.response?.data?.error ||
        err.message ||
        "Upload failed";

      setError(`Upload failed: ${backendMessage}`);
    }
  };

  const clips = result?.clips || [];

  return (
    <div
      style={{
        minHeight: "100vh",
        background:
          "radial-gradient(circle at top left, #064e3b 0%, #020617 42%, #020617 100%)",
        color: "white",
        fontFamily: "Inter, Arial, sans-serif",
        padding: "28px",
      }}
    >
      <div style={{ maxWidth: "1220px", margin: "0 auto" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "34px",
          }}
        >
          <div style={{ fontSize: "30px", fontWeight: "950" }}>
            FluxClip 🚀✂️
          </div>

          <div
            style={{
              display: "flex",
              gap: "14px",
              color: "#cbd5e1",
              fontSize: "14px",
              alignItems: "center",
            }}
          >
            <span>Dashboard</span>
            <span>Pricing</span>
            <span>Docs</span>
            <span
              style={{
                background: "rgba(34,197,94,0.16)",
                border: "1px solid rgba(34,197,94,0.45)",
                color: "#86efac",
                padding: "8px 12px",
                borderRadius: "999px",
                fontWeight: "800",
              }}
            >
              Cloud Live
            </span>
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
                "linear-gradient(135deg, rgba(34,197,94,0.20), rgba(59,130,246,0.13), rgba(168,85,247,0.10))",
              border: "1px solid rgba(148,163,184,0.28)",
              borderRadius: "28px",
              padding: "38px",
              boxShadow: "0 30px 100px rgba(0,0,0,0.42)",
            }}
          >
            <div
              style={{
                display: "inline-block",
                background: "rgba(34,197,94,0.15)",
                color: "#86efac",
                padding: "8px 14px",
                borderRadius: "999px",
                fontWeight: "800",
                fontSize: "13px",
                marginBottom: "20px",
              }}
            >
              AI Viral Shorts Engine • V6 Cloud
            </div>

            <h1
              style={{
                fontSize: "58px",
                lineHeight: "1.03",
                margin: "0 0 18px",
                fontWeight: "950",
                letterSpacing: "-1.5px",
              }}
            >
              Turn long videos into viral-ready shorts.
            </h1>

            <p
              style={{
                color: "#cbd5e1",
                fontSize: "18px",
                lineHeight: "1.65",
                maxWidth: "680px",
              }}
            >
              Upload a long video. FluxClip detects viral moments, creates
              shorts, adds captions, scores clips, generates titles, hashtags
              and export-ready creator packages.
            </p>

            <div
              style={{
                display: "flex",
                gap: "12px",
                marginTop: "28px",
                flexWrap: "wrap",
              }}
            >
              {["Smart Crop", "Captions", "Thumbnails", "Hashtags", "Cloud Processing"].map(
                (item) => (
                  <div
                    key={item}
                    style={{
                      background: "rgba(15,23,42,0.76)",
                      border: "1px solid rgba(148,163,184,0.22)",
                      padding: "10px 14px",
                      borderRadius: "14px",
                      color: "#e2e8f0",
                      fontWeight: "700",
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
              background: "rgba(15,23,42,0.92)",
              border: "1px solid rgba(148,163,184,0.28)",
              borderRadius: "28px",
              padding: "30px",
              boxShadow: "0 30px 100px rgba(0,0,0,0.42)",
            }}
          >
            <h2 style={{ marginTop: 0, fontSize: "28px" }}>
              Create New Viral Pack
            </h2>
            <p style={{ color: "#94a3b8", lineHeight: "1.6" }}>
              Upload one long-form video to generate AI-selected short clips.
              CPU processing may take time, but the cloud worker keeps running.
            </p>

            <div
              style={{
                border: "2px dashed rgba(148,163,184,0.35)",
                borderRadius: "20px",
                padding: "30px",
                textAlign: "center",
                background: "rgba(30,41,59,0.66)",
                margin: "24px 0",
              }}
            >
              <div style={{ fontSize: "46px", marginBottom: "12px" }}>🎬</div>
              <input
                type="file"
                accept="video/*"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              <p style={{ color: "#cbd5e1", fontSize: "14px" }}>
                {file ? file.name : "MP4, MOV, MKV supported"}
              </p>

              {file && (
                <p style={{ color: "#94a3b8", fontSize: "13px" }}>
                  Size: {(file.size / (1024 * 1024)).toFixed(2)} MB
                </p>
              )}
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
                padding: "17px 20px",
                borderRadius: "16px",
                cursor: loading ? "not-allowed" : "pointer",
                fontWeight: "950",
                fontSize: "16px",
                boxShadow: loading ? "none" : "0 14px 35px rgba(34,197,94,0.28)",
              }}
            >
              {loading ? "Processing in Cloud..." : "Generate Viral Shorts"}
            </button>

            {loading && (
              <div style={{ marginTop: "16px" }}>
                <div
                  style={{
                    height: "10px",
                    background: "rgba(148,163,184,0.22)",
                    borderRadius: "999px",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${uploadProgress}%`,
                      height: "100%",
                      background: "linear-gradient(135deg, #22c55e, #16a34a)",
                    }}
                  />
                </div>
                <p style={{ color: "#cbd5e1", fontSize: "13px" }}>
                  Upload progress: {uploadProgress}%
                </p>
              </div>
            )}

            {(jobId || status) && (
              <div
                style={{
                  marginTop: "18px",
                  background: "rgba(30,41,59,0.84)",
                  border: "1px solid rgba(148,163,184,0.18)",
                  borderRadius: "16px",
                  padding: "15px",
                  fontSize: "14px",
                }}
              >
                <div>
                  <strong>Status:</strong> {status}
                </div>
                {jobId && (
                  <div style={{ color: "#94a3b8", marginTop: "6px" }}>
                    Job: {jobId}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: "16px",
            marginBottom: "28px",
          }}
        >
          {[
            ["Creator SaaS", "Built for YouTubers, editors and short-form creators"],
            ["24/7 Cloud", "Runs on GCP even when your laptop is off"],
            ["Viral DNA", "Hook detection, ranking, captions and export pack"],
          ].map(([title, sub]) => (
            <div
              key={title}
              style={{
                background: "rgba(15,23,42,0.84)",
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: "20px",
                padding: "24px",
                textAlign: "center",
              }}
            >
              <h2 style={{ margin: 0, fontSize: "24px" }}>{title}</h2>
              <p style={{ color: "#94a3b8", marginBottom: 0 }}>{sub}</p>
            </div>
          ))}
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
            ["⚡", "Fast ASR", "GPU-ready pipeline"],
            ["🧠", "Viral Brain", "Hook ranking"],
            ["🎯", "Smart Export", "Captions + titles"],
            ["📦", "Creator Pack", "Download ready"],
          ].map(([icon, title, sub]) => (
            <div
              key={title}
              style={{
                background: "rgba(15,23,42,0.84)",
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: "20px",
                padding: "22px",
              }}
            >
              <div style={{ fontSize: "32px" }}>{icon}</div>
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
              padding: "24px",
              borderRadius: "20px",
              marginBottom: "28px",
            }}
          >
            <h3>🔥 FluxClip Cloud AI is processing your content...</h3>
            <p style={{ color: "#cbd5e1", lineHeight: "1.6" }}>
              Uploading → Transcribing → Hook Detection → Viral Ranking → Smart
              Crop → Captions → Export Pack
            </p>
            <p style={{ color: "#94a3b8", marginBottom: 0 }}>
              Keep this page open. Long videos can take time on CPU, but backend
              processing continues on the cloud server.
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
              whiteSpace: "pre-wrap",
            }}
          >
            {error}
          </div>
        )}

        {clips.length > 0 && (
          <div>
            <h2 style={{ fontSize: "36px" }}>Your Viral Clips</h2>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(330px, 1fr))",
                gap: "20px",
              }}
            >
              {clips.map((clip, index) => {
                const videoUrl = fixVideoUrl(
                  clip.video_path || clip.download_url || clip.url
                );

                return (
                  <div
                    key={index}
                    style={{
                      background: "rgba(15,23,42,0.92)",
                      border: "1px solid rgba(148,163,184,0.22)",
                      padding: "20px",
                      borderRadius: "24px",
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
                          fontWeight: "950",
                        }}
                      >
                        Score {clip.score || "AI"}
                      </span>
                    </div>

                    <p>
                      <strong>Title:</strong> {clip.title || "Viral short clip"}
                    </p>
                    <p>
                      <strong>Niche:</strong> {clip.niche || "Auto-detected"}
                    </p>
                    <p>
                      <strong>Duration:</strong> {clip.duration || "short"}s
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
                            fontWeight: "950",
                          }}
                        >
                          Download Clip
                        </a>
                      </>
                    )}

                    <div
                      style={{
                        marginTop: "16px",
                        background: "rgba(51,65,85,0.82)",
                        padding: "12px",
                        borderRadius: "14px",
                      }}
                    >
                      <strong>Score Breakdown</strong>
                      <pre style={{ overflowX: "auto" }}>
                        {JSON.stringify(clip.score_breakdown || {}, null, 2)}
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